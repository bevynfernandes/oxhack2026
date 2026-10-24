"""Assemble real company evidence from reviewed mappings and durable source captures."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
import orjson
from pydantic import Field

from oxhack2026.catalog.company import (
    CompanyEvent,
    CompanyMetricObservation,
    CompanyProfile,
    CompanyRelationship,
    CompanySourceSnapshot,
    DecimalValue,
    IntegerValue,
    MetricDefinition,
    SourceEvidence,
)
from oxhack2026.catalog.schemas import Contract, Identifier, PublicUrl, TimeWindow
from oxhack2026.ingest.capture import (
    CaptureRequest,
    HttpCapture,
    capture_get,
    freeze_run,
)
from oxhack2026.ingest.github_releases import collect_releases
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.datasets import DatasetBundle
from oxhack2026.storage.local import atomic_write, file_lock
from oxhack2026.storage.publication import LocalDatasetStore


class FundingSeed(Contract):
    """Human-reviewed primary announcement; amount/date are claims, not truth labels."""

    company_id: Identifier
    url: PublicUrl
    announcement_date: date
    amount_usd: Annotated[str, Field(pattern=r"^[0-9]+(?:\.[0-9]{1,2})?$")]
    required_text: Annotated[
        tuple[Annotated[str, Field(min_length=3)], ...], Field(min_length=1)
    ]
    description: Annotated[str, Field(min_length=1, max_length=1000)]


class CompanyBuildSettings(Contract):
    """Frozen source/cohort configuration; changing it requires new run/snapshot IDs."""

    run_id: Identifier
    snapshot_id: Identifier
    npm_dataset_version: Identifier
    code_revision: Identifier
    cohort_version: Identifier
    measurement_end: datetime
    maximum_github_pages: Annotated[int, Field(ge=1, le=100)] = 10
    companies: Annotated[tuple[FundingSeed, ...], Field(min_length=1)]


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _definitions() -> tuple[MetricDefinition, ...]:
    specs = (
        (
            "npm_downloads_30d_v1",
            "traction",
            "SDK downloads, 30 days",
            "downloads",
            "integer",
            "product",
            3,
            None,
        ),
        (
            "npm_downloads_previous_30d_v1",
            "traction",
            "SDK downloads, previous 30 days",
            "downloads",
            "integer",
            "product",
            35,
            None,
        ),
        (
            "github_stable_releases_90d_v1",
            "execution",
            "SDK stable releases, 90 days",
            "releases",
            "integer",
            "repository",
            7,
            None,
        ),
        (
            "reported_funding_round_usd_v1",
            "market_financing",
            "Selected reported financing round",
            "USD",
            "decimal",
            "company",
            365,
            "USD",
        ),
        (
            "revenue_12m_usd_v1",
            "commercial",
            "Revenue, trailing 12 months",
            "USD",
            "decimal",
            "company",
            90,
            "USD",
        ),
        (
            "operating_cashflow_12m_usd_v1",
            "commercial",
            "Operating cash flow, trailing 12 months",
            "USD",
            "decimal",
            "company",
            90,
            "USD",
        ),
        (
            "active_paying_customers_v1",
            "commercial",
            "Active paying customers",
            "customers",
            "integer",
            "company",
            30,
            None,
        ),
    )
    descriptions = {
        "npm_downloads_30d_v1": (
            "Registry downloads of the currently mapped SDK in the "
            "closed 30-day window; not users or customers."
        ),
        "npm_downloads_previous_30d_v1": (
            "Same SDK registry count in the immediately preceding "
            "30-day window, without package splicing."
        ),
        "github_stable_releases_90d_v1": (
            "Published non-draft, non-prerelease GitHub releases of"
            " the verified SDK repository in 90 days; requires full"
            " bounded pagination."
        ),
        "reported_funding_round_usd_v1": (
            "USD amount of one explicitly selected company-reported"
            " financing announcement. Not total funding, cash "
            "balance, runway, or necessarily the latest round."
        ),
        "revenue_12m_usd_v1": (
            "Company revenue for a fully defined trailing twelve-"
            "month accounting period in USD; no public estimate "
            "substitution."
        ),
        "operating_cashflow_12m_usd_v1": (
            "Company operating cash flow for a fully defined "
            "trailing twelve-month accounting period in USD; "
            "financing inflows excluded."
        ),
        "active_paying_customers_v1": (
            "Distinct active paying customer accounts under a "
            "disclosed company definition at the measurement date."
        ),
    }
    return tuple(
        MetricDefinition.model_validate(
            {
                "metric_id": key,
                "family": family,
                "label": label,
                "definition": descriptions[key],
                "unit": unit,
                "value_kind": kind,
                "scope": scope,
                "applicability": (
                    "Company-backed AI developer infrastructure with the "
                    "indicated source or disclosure."
                ),
                "maximum_age_days": age,
                "currency": currency,
            }
        )
        for key, family, label, unit, kind, scope, age, currency in specs
    )


def _evidence(
    company_id: str,
    suffix: str,
    capture: HttpCapture,
    assertion: str,
    kind: str = "platform_observed",
) -> SourceEvidence:
    return SourceEvidence.model_validate(
        {
            "evidence_id": f"{company_id}-{suffix}",
            "company_id": company_id,
            "provider": "github"
            if "api.github.com" in capture.request.url
            else "company_announcement",
            "url": capture.request.url,
            "access": "public",
            "raw_artifact": capture.artifact,
            "locator": "Captured response",
            "assertion": assertion,
            "published_at": None,
            "availability_basis": "first_observed",
            "kind": kind,
            "review_state": "verified",
            "available_at": capture.collected_at,
            "collected_at": capture.collected_at,
        }
    )


def _metric(
    company_id: str,
    metric_id: str,
    period: TimeWindow,
    sources: tuple[SourceEvidence, ...],
    value: IntegerValue | DecimalValue | None,
) -> CompanyMetricObservation:
    collected = max(row.collected_at for row in sources)
    return CompanyMetricObservation(
        observation_id=f"{company_id}-{metric_id}",
        company_id=company_id,
        metric_id=metric_id,
        window=period,
        measured_at=None,
        value=value,
        state="observed" if value is not None else "missing",
        reason=None
        if value is not None
        else "Source history is incomplete or truncated; no complete value is claimed.",
        evidence_ids=tuple(row.evidence_id for row in sources)
        if value is not None
        else (),
        available_at=collected,
        collected_at=collected,
    )


def _npm_metrics(
    bundle: DatasetBundle,
    company_id: str,
    package_id: str,
    window: TimeWindow,
    stores: tuple[FileArtifactStore, FileArtifactStore],
) -> tuple[list[SourceEvidence], list[CompanyMetricObservation]]:
    source_store, destination = stores
    identity = next(row for row in bundle.series if row.entity_id == package_id)
    rows = [
        row
        for row in bundle.observations
        if row.series_id == identity.series_id
        and window.start <= row.window.start
        and row.window.end <= window.end
    ]
    extractions = {
        row.extraction_id: row for row in bundle.manifest.extraction_manifests
    }
    evidence: list[SourceEvidence] = []
    for extraction_id in sorted({row.extraction_id for row in rows}):
        extraction = extractions[extraction_id]
        package = next(
            row for row in bundle.catalog.packages if row.package_id == package_id
        )
        for index, ref in enumerate(extraction.raw_artifacts):
            destination.write(source_store.read(ref), ref.media_type)
            start = extraction.requested_window.start.date().isoformat()
            end = (
                (extraction.requested_window.end - timedelta(days=1)).date().isoformat()
            )
            url = (
                f"https://api.npmjs.org/downloads/range/{start}:{end}/"
                f"{quote(package.canonical_name, safe='@')}"
            )
            evidence.append(
                SourceEvidence(
                    evidence_id=f"{company_id}-npm-{len(evidence)}-{index}",
                    company_id=company_id,
                    provider="npm",
                    url=url.strip(),
                    access="public",
                    raw_artifact=ref,
                    locator=f"package={package.canonical_name}; daily downloads",
                    assertion=(
                        "Registry-reported downloads for the currently verified"
                        " SDK package, not company customers."
                    ),
                    published_at=None,
                    availability_basis="first_observed",
                    kind="platform_observed",
                    review_state="verified",
                    available_at=extraction.retrieved_at,
                    collected_at=extraction.retrieved_at,
                )
            )
    if not evidence:
        message = "Company npm window has no captured source data"
        raise ValueError(message)
    metrics = []
    for offset, metric_id in (
        (0, "npm_downloads_previous_30d_v1"),
        (30, "npm_downloads_30d_v1"),
    ):
        period = TimeWindow(
            start=window.start + timedelta(days=offset),
            end=window.start + timedelta(days=offset + 30),
        )
        selected = [
            row
            for row in rows
            if period.start <= row.window.start and row.window.end <= period.end
        ]
        complete = len(selected) == 30 and all(
            row.completeness == "complete" and row.value is not None for row in selected
        )
        value = (
            IntegerValue(value=sum(row.value or 0 for row in selected))
            if complete
            else None
        )
        metrics.append(
            _metric(
                company_id,
                metric_id,
                period,
                tuple(evidence),
                value,
            )
        )
    return evidence, metrics


def _company(
    seed: FundingSeed,
    bundle: DatasetBundle,
    settings: CompanyBuildSettings,
    root: Path,
    npm_root: Path,
) -> tuple[
    CompanyProfile,
    list[CompanyRelationship],
    list[SourceEvidence],
    list[CompanyMetricObservation],
    CompanyEvent,
]:
    tools = {row.tool_id: row for row in bundle.catalog.tools}
    mappings = [
        row
        for row in bundle.catalog.mappings
        if tools[row.tool_id].organization_id == seed.company_id
        and row.verified
        and row.primary
        and row.organization_representative
        and row.valid_from <= bundle.catalog.recorded_at
        and (row.valid_to is None or bundle.catalog.recorded_at < row.valid_to)
    ]
    if len(mappings) != 1 or mappings[0].repository_id is None:
        message = (
            "Company requires exactly one verified current package/repository mapping"
        )
        raise ValueError(message)
    mapping = mappings[0]
    tool = tools[mapping.tool_id]
    repository = next(
        row
        for row in bundle.catalog.repositories
        if row.repository_id == mapping.repository_id
    )
    destination = FileArtifactStore(root)
    with httpx.Client() as client:
        funding = capture_get(
            CaptureRequest(url=seed.url), client, root, settings.run_id
        )
        parser = _TextParser()
        parser.feed(destination.read(funding.artifact).decode("utf-8"))
        plain = " ".join(" ".join(parser.parts).split()).casefold()
        if not all(text.casefold() in plain for text in seed.required_text):
            message = (
                "Reviewed announcement anchors are absent; manual "
                "source review required"
            )
            raise ValueError(message)
        history = collect_releases(
            repository, client, root, settings.run_id, settings.maximum_github_pages
        )
    funding_source = _evidence(
        seed.company_id, "funding", funding, seed.description, "company_reported"
    )
    release_sources = [
        _evidence(
            seed.company_id,
            f"github-{index}",
            capture,
            "Verified SDK repository identity or captured release page.",
        )
        for index, capture in enumerate(history.captures)
    ]
    npm_sources, metrics = _npm_metrics(
        bundle,
        seed.company_id,
        mapping.package_id,
        TimeWindow(
            start=settings.measurement_end - timedelta(days=60),
            end=settings.measurement_end,
        ),
        (FileArtifactStore(npm_root), destination),
    )
    evidence = [funding_source, *release_sources, *npm_sources]
    period = TimeWindow(
        start=settings.measurement_end - timedelta(days=90),
        end=settings.measurement_end,
    )
    count = history.count(period)
    metrics.append(
        _metric(
            seed.company_id,
            "github_stable_releases_90d_v1",
            period,
            tuple(release_sources),
            IntegerValue(value=count) if count is not None else None,
        )
    )
    announced = datetime.combine(seed.announcement_date, time.min, UTC)
    metrics.append(
        _metric(
            seed.company_id,
            "reported_funding_round_usd_v1",
            TimeWindow(start=announced, end=announced + timedelta(days=1)),
            (funding_source,),
            DecimalValue(value=Decimal(seed.amount_usd)),
        )
    )
    collected = max(row.collected_at for row in evidence)
    for definition in _definitions():
        if definition.family == "commercial":
            metrics.append(
                CompanyMetricObservation(
                    observation_id=f"{seed.company_id}-{definition.metric_id}",
                    company_id=seed.company_id,
                    metric_id=definition.metric_id,
                    window=None,
                    measured_at=settings.measurement_end,
                    value=None,
                    state="missing",
                    reason=(
                        "No sufficiently defined company financial/customer "
                        "disclosure has been supplied; public activity is not a"
                        " substitute."
                    ),
                    evidence_ids=(),
                    available_at=collected,
                    collected_at=collected,
                )
            )
    profile = CompanyProfile(
        company_id=seed.company_id,
        display_name=next(
            row.name
            for row in bundle.catalog.organizations
            if row.organization_id == seed.company_id
        ),
        website_url=tool.website_url,
        segment=tool.category,
        business_model=None,
        stage=None,
        context_as_of=collected,
        evidence_ids=(funding_source.evidence_id, release_sources[0].evidence_id),
    )
    # The reviewed catalogue establishes current association, not earlier ownership.
    catalog_ref = destination.write(
        bundle.catalog.model_dump_json().encode(), "application/json"
    )
    catalog_source = SourceEvidence(
        evidence_id=f"{seed.company_id}-mapping",
        company_id=seed.company_id,
        provider="reviewed_catalogue",
        url=None,
        access="restricted",
        raw_artifact=catalog_ref,
        locator=mapping.mapping_id,
        assertion=(
            "Previously reviewed contemporary "
            "product/package/repository association; not historical"
            " company eligibility."
        ),
        published_at=None,
        availability_basis="first_observed",
        kind="user_supplied",
        review_state="verified",
        available_at=bundle.catalog.recorded_at,
        collected_at=bundle.catalog.recorded_at,
    )
    evidence.append(catalog_source)
    subjects: tuple[tuple[Literal["tool", "package", "repository"], str], ...] = (
        ("tool", tool.tool_id),
        ("package", mapping.package_id),
        ("repository", str(mapping.repository_id)),
    )
    relationships = [
        CompanyRelationship(
            relationship_id=f"{seed.company_id}-{kind}",
            company_id=seed.company_id,
            subject_kind=kind,
            subject_id=subject,
            valid_from=mapping.valid_from,
            valid_to=mapping.valid_to,
            evidence_ids=(catalog_source.evidence_id,),
        )
        for kind, subject in subjects
    ]
    event = CompanyEvent(
        event_id=f"{seed.company_id}-financing-announcement",
        company_id=seed.company_id,
        kind="funding",
        stage="announced",
        occurred_on=seed.announcement_date,
        date_precision="day",
        description=seed.description,
        evidence_ids=(funding_source.evidence_id,),
        available_at=funding_source.available_at,
        collected_at=funding_source.collected_at,
    )
    return profile, relationships, evidence, metrics, event


def build_company_source(
    settings: CompanyBuildSettings, npm_root: Path, root: Path
) -> CompanySourceSnapshot:
    """Collect bounded reviewed evidence and assemble a durable, unpublished candidate.

    Args:
        settings: Frozen identities, source claims and extraction bounds.
        npm_root: Existing published verified npm dataset root.
        root: Destination company artifacts/checkpoints.
    Returns:
        Validated source snapshot; exact reruns reuse the saved candidate and bytes.
    Raises:
        ValueError: For invalid windows, mappings, changed run configuration or claims.
        RuntimeError: For source rate/access exhaustion requiring a later restart.
        httpx.HTTPError: For source transport failures.
        OSError: For artifact/checkpoint errors.
    """
    end = settings.measurement_end
    if (
        end.utcoffset() != timedelta(0)
        or any((end.hour, end.minute, end.second, end.microsecond))
        or end > datetime.now(UTC)
    ):
        message = "Company measurement end requires a closed UTC midnight"
        raise ValueError(message)
    if len({row.company_id for row in settings.companies}) != len(settings.companies):
        message = "Company selection contains duplicate IDs"
        raise ValueError(message)
    bundle = LocalDatasetStore(npm_root).bundle(settings.npm_dataset_version)
    configuration = orjson.dumps(
        {
            "settings": settings.model_dump(mode="json"),
            "npm_manifest": bundle.manifest.model_dump(mode="json"),
        },
        option=orjson.OPT_SORT_KEYS,
    )
    freeze_run(root, settings.run_id, configuration)
    path = root / "candidates" / f"{settings.snapshot_id}.json"
    with file_lock(root / "captures" / settings.run_id / "build.lock"):
        if path.exists():
            previous = CompanySourceSnapshot.model_validate_json(path.read_bytes())
            if previous.configuration_sha256 != sha256(configuration).hexdigest():
                message = "Candidate identity already belongs to another configuration"
                raise ValueError(message)
            for source in previous.evidence:
                FileArtifactStore(root).read(source.raw_artifact)
            return previous
        records = [
            _company(seed, bundle, settings, root, npm_root)
            for seed in settings.companies
        ]
        evidence = tuple(source for record in records for source in record[2])
        snapshot = CompanySourceSnapshot(
            snapshot_id=settings.snapshot_id,
            as_of=max(source.collected_at for source in evidence),
            recorded_at=datetime.now(UTC),
            cohort_version=settings.cohort_version,
            code_revision=settings.code_revision,
            configuration_sha256=sha256(configuration).hexdigest(),
            synthetic=bundle.manifest.synthetic,
            mode="contemporary",
            limitations=(
                *bundle.manifest.limitations,
                (
                    "Current company evidence; not a historically "
                    "enumerated success/failure cohort."
                ),
                (
                    "Company-reported selected financing announcements are "
                    "not complete financing histories or cash balances."
                ),
                (
                    "Commercial financial/customer records and effective "
                    "family membership are unresolved."
                ),
            ),
            companies=tuple(row[0] for row in records),
            relationships=tuple(item for row in records for item in row[1]),
            definitions=_definitions(),
            evidence=evidence,
            metrics=tuple(item for row in records for item in row[3]),
            events=tuple(row[4] for row in records),
        )
        atomic_write(path, snapshot.model_dump_json(indent=2).encode())
        return snapshot
