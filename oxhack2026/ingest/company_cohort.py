"""Public batch discovery and unresolved follow-up, never inferred outcome labels."""

from pathlib import Path
from typing import Annotated, Literal, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from oxhack2026.catalog.schemas import (
    Contract,
    Identifier,
    Name,
    PublicUrl,
    UtcInstant,
)
from oxhack2026.features.company_outcomes import COMPANY_OUTCOME_IDS, CompanyOutcomeId
from oxhack2026.ingest.capture import CaptureRequest, capture_get, freeze_run
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock

CommitId = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$", strict=True)]


class CohortDiscoverySettings(Contract):
    """Pin an entire public YC batch before looking at company status."""

    cohort_version: Identifier
    batch_slug: Identifier
    batch_name: Name
    source_revision: CommitId
    code_revision: CommitId

    @property
    def source_url(self) -> str:
        """Return the exact commit-pinned upstream JSON endpoint."""
        return (
            "https://raw.githubusercontent.com/yc-oss/api/"
            f"{self.source_revision}/batches/{self.batch_slug}.json"
        )


class _YcCompany(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Annotated[int, Field(gt=0, strict=True)]
    name: Name
    batch: Name
    status: Name
    url: PublicUrl


class DiscoveredCompany(Contract):
    """Current directory observation; neither historical feature nor verified label."""

    company_id: Identifier
    source_company_id: Annotated[int, Field(gt=0, strict=True)]
    name: Name
    batch: Name
    directory_status: Name
    primary_profile_url: PublicUrl
    historical_identity_verified: Literal[False] = False
    family_id: None = None


class CompanyFollowup(Contract):
    """Unresolved source-review work item; Dev 2 owns eventual outcome eligibility."""

    company_id: Identifier
    outcome_id: CompanyOutcomeId
    state: Literal["pending_source_review"] = "pending_source_review"
    label: None = None
    reason_codes: tuple[Identifier, ...] = (
        "no_dated_outcome_evidence",
        "no_historical_feature_vintage",
        "company_family_unverified",
    )


class CohortDiscovery(Contract):
    """Immutable discovery ledger retaining every returned company and all unknowns."""

    schema_version: Literal["company-cohort-discovery-v1"] = (
        "company-cohort-discovery-v1"
    )
    settings: CohortDiscoverySettings
    source_url: PublicUrl
    collected_at: UtcInstant
    raw_artifact: ArtifactReference
    companies: tuple[DiscoveredCompany, ...]
    followups: tuple[CompanyFollowup, ...]
    limitations: tuple[str, ...] = (
        "Unofficial current mirror of public YC profiles; "
        "not a complete original cohort.",
        "Discovery includes all returned statuses, without success-based filtering.",
        "Current names/statuses are observed at collection, not known at batch entry.",
        "Directory status does not establish event dates, cash flow, "
        "growth or outcome labels.",
        "YC selection and surviving public pages limit representativeness.",
        "Public accessibility does not establish unrestricted redistribution rights.",
    )

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        """Require unique companies and three unresolved follow-ups each."""
        ids = {row.company_id for row in self.companies}
        expected = {(key, outcome) for key in ids for outcome in COMPANY_OUTCOME_IDS}
        if (
            not ids
            or len(ids) != len(self.companies)
            or len(self.followups) != len(expected)
            or {(row.company_id, row.outcome_id) for row in self.followups} != expected
            or self.source_url != self.settings.source_url
        ):
            message = "Discovery inventory or pinned source is inconsistent"
            raise ValueError(message)
        return self


def parse_cohort(raw: bytes, batch_name: str) -> tuple[DiscoveredCompany, ...]:
    """Normalize every public batch record without filtering on reported status.

    Args:
        raw: Exact archived upstream JSON array.
        batch_name: Expected batch; mismatched or duplicate records fail the run.
    Returns:
        Stable directory identities sorted by upstream numeric ID.
    Raises:
        ValueError: For invalid schema, duplicate IDs, wrong batch or profile host.
    """
    rows = TypeAdapter(tuple[_YcCompany, ...]).validate_json(raw)
    if not rows or len({row.id for row in rows}) != len(rows):
        message = "Discovery requires nonempty unique upstream company IDs"
        raise ValueError(message)
    if any(
        row.batch != batch_name
        or not row.url.startswith("https://www.ycombinator.com/companies/")
        for row in rows
    ):
        message = "Directory records disagree with the selected batch or primary host"
        raise ValueError(message)
    return tuple(
        DiscoveredCompany(
            company_id=f"yc-{row.id}",
            source_company_id=row.id,
            name=row.name,
            batch=row.batch,
            directory_status=row.status,
            primary_profile_url=row.url,
        )
        for row in sorted(rows, key=lambda row: row.id)
    )


def collect_cohort(settings: CohortDiscoverySettings, root: Path) -> CohortDiscovery:
    """Capture a pinned public batch and write an immutable unresolved ledger.

    Args:
        settings: Explicit batch/commit/version; all returned statuses are retained.
        root: Local artifact/checkpoint root with existing versions preserved.
    Returns:
        A validated discovery ledger, identical for same-run replay.
    Raises:
        ValueError, OSError, HTTPError: For config conflicts, bad data or transport.
    """
    freeze_run(root, settings.cohort_version, settings.model_dump_json().encode())
    with httpx.Client() as client:
        capture = capture_get(
            CaptureRequest(url=settings.source_url),
            client,
            root,
            settings.cohort_version,
        )
    companies = parse_cohort(
        FileArtifactStore(root).read(capture.artifact), settings.batch_name
    )
    ledger = CohortDiscovery(
        settings=settings,
        source_url=settings.source_url,
        collected_at=capture.collected_at,
        raw_artifact=capture.artifact,
        companies=companies,
        followups=tuple(
            CompanyFollowup(company_id=row.company_id, outcome_id=outcome)
            for row in companies
            for outcome in COMPANY_OUTCOME_IDS
        ),
    )
    path = root / "cohorts" / f"{settings.cohort_version}.json"
    content = ledger.model_dump_json().encode()
    with file_lock(root / ".cohort-publication.lock"):
        if path.exists():
            if path.read_bytes() != content:
                message = "An immutable cohort discovery cannot be replaced"
                raise ValueError(message)
        else:
            atomic_write(path, content)
    return ledger


def load_cohort(root: Path, cohort_version: str) -> CohortDiscovery:
    """Read an exact ledger and verify its raw batch and normalized company set.

    Args:
        root: Discovery artifact root.
        cohort_version: Exact immutable ledger ID, never a latest alias.
    Returns:
        Validated ledger including every upstream company and unresolved follow-up.
    Raises:
        ValueError, OSError: For invalid IDs, missing files or inconsistent bytes.
    """
    identifier = TypeAdapter(Identifier).validate_python(cohort_version)
    with (root / "cohorts" / f"{identifier}.json").open("rb") as stream:
        content = stream.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        message = "Cohort ledger exceeds size limit"
        raise ValueError(message)
    ledger = CohortDiscovery.model_validate_json(content)
    raw = FileArtifactStore(root).read(ledger.raw_artifact)
    if ledger.settings.cohort_version != identifier or ledger.companies != parse_cohort(
        raw, ledger.settings.batch_name
    ):
        message = "Discovery ledger disagrees with its identity or archived batch"
        raise ValueError(message)
    return ledger
