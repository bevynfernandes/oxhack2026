"""Compose immutable reports with explicit gaps and shared null model forecasts."""

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from math import log, log1p
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from oxhack2026.api.research_v2_schemas import (
    Claim,
    Identity,
    Job,
    Observation,
    Report,
    ResearchEvidence,
)
from oxhack2026.models.dimension_serving import DimensionInputs, DimensionModelRegistry
from oxhack2026.models.startup_outlook import (
    FORECAST_HORIZONS,
    SPECIALIST_GROUP_IDS,
    OutcomeForecast,
    SpecialistOutlook,
    StartupOutlook,
)

_GAPS = {
    "revenue": (
        "currency_per_period",
        "No normalized revenue with sufficient unit, definition and period.",
    ),
    "retention": (
        "percent",
        "Retention definition, cohort and period are unavailable.",
    ),
    "runway": ("months", "Cash and burn are unavailable; funding is not runway."),
    "competitor_coverage": (
        "companies",
        "No verified competitor coverage collector is configured.",
    ),
}


def _conflicting_claims(job: Job) -> tuple[Claim, ...]:
    claims = [claim for source in job.sources for claim in source.claims]
    groups: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        key = re.sub(r"\d+(?:[.,]\d+)*", "#", claim.text.lower())
        groups[key].append(claim)
    return tuple(
        claim.model_copy(
            update={
                "conflicts_with": tuple(
                    other.claim_id
                    for other in groups[
                        re.sub(r"\d+(?:[.,]\d+)*", "#", claim.text.lower())
                    ]
                    if other.text != claim.text
                ),
            }
        )
        for claim in claims
    )


def _adoption_features(
    rows: list[Observation], evidence: dict[str, ResearchEvidence]
) -> tuple[tuple[float, ...] | None, tuple[str, ...], str]:
    adoption: tuple[tuple[float, ...] | None, tuple[str, ...], str] = (
        None,
        (),
        "requires_complete_adjacent_npm_windows",
    )
    if len(rows) == 2 and len({row.metric_id for row in rows}) == 2:
        selected = {row.metric_id: row for row in rows}
        current, previous = (
            selected["npm_downloads_latest_30d"],
            selected["npm_downloads_previous_30d"],
        )
        packages = []
        for row in (current, previous):
            names = set()
            for key in row.evidence_ids:
                item = evidence.get(key)
                if item is None:
                    continue
                parsed = urlsplit(item.url)
                if parsed.hostname == "api.npmjs.org" and parsed.path.startswith(
                    "/downloads/range/"
                ):
                    names.add(unquote(parsed.path.split("/", 4)[-1]))
            packages.append(names)
        if (
            current.window is not None
            and previous.window is not None
            and previous.window.end == current.window.start
            and all(
                row.value is not None
                and row.value >= 1000
                and float(row.value).is_integer()
                and row.unit == "downloads"
                and row.missing_reason is None
                and row.window is not None
                and row.window.end - row.window.start == timedelta(days=30)
                for row in rows
            )
            and len(packages[0]) == 1
            and packages[0] == packages[1]
            and current.value is not None
            and previous.value is not None
        ):
            adoption = (
                (
                    log1p(current.value),
                    log1p(previous.value),
                    log((current.value + 1) / (previous.value + 1)),
                ),
                (current.observation_id, previous.observation_id),
                "experimental_sdk_proxy_only",
            )
    return adoption


def _dimension_inputs(job: Job, outlook: StartupOutlook) -> DimensionInputs:
    evidence = {
        row.evidence_id: row for source in job.sources for row in source.evidence
    }
    packages: dict[str, list[Observation]] = defaultdict(list)
    for source in job.sources:
        for row in source.observations:
            if row.metric_id not in {
                "npm_downloads_latest_30d",
                "npm_downloads_previous_30d",
            }:
                continue
            names = {
                unquote(parsed.path.split("/", 4)[-1])
                for key in row.evidence_ids
                if (item := evidence.get(key)) is not None
                and (parsed := urlsplit(item.url)).hostname == "api.npmjs.org"
                and parsed.path.startswith("/downloads/range/")
            }
            if len(names) == 1:
                packages[names.pop()].append(row)
    candidates = [
        candidate
        for name in sorted(packages)
        if (candidate := _adoption_features(packages[name], evidence))[0] is not None
    ]
    # A pre-origin size rule chooses one SDK; counts from separate packages never mix.
    adoption = max(
        candidates,
        key=lambda candidate: candidate[0][0] if candidate[0] is not None else -1,
        default=(None, (), "requires_complete_adjacent_npm_windows"),
    )
    return DimensionInputs(
        outlook.company_id, outlook.source_snapshot_id, outlook.as_of, adoption
    )


def compose(
    job: Job, identity: Identity, models: DimensionModelRegistry | None = None
) -> Report:
    """Build a fresh report; saved context alone never qualifies as a fresh result.

    Args:
        job: Source checkpoints after every enabled collector has stopped.
        identity: Exact confirmed discovery preview, including conflicts/context.
        models: Optional verified experimental bundle; old report bytes are untouched.
    Returns:
        Validated immutable report retaining claims without invented metrics.
    """
    now = datetime.now(UTC)
    observations = [row for source in job.sources for row in source.observations]
    for metric_id, (unit, reason) in _GAPS.items():
        if any(row.metric_id == metric_id for row in observations):
            continue
        observations.append(
            Observation(
                observation_id=uuid4().hex,
                metric_id=metric_id,
                definition=reason,
                unit=unit,
                collected_at=now,
                missing_reason="not_publicly_established",
            )
        )
    support = tuple(item for source in job.sources for item in source.evidence)
    captures = tuple(item for source in job.sources for item in source.captures)
    report_id = uuid4().hex
    company_id = (
        identity.saved_context.company.company_id
        if identity.saved_context
        else identity.identity_id
    )
    financial = tuple(
        row
        for source in job.sources
        if source.provider == "sec"
        for row in source.observations
        if row.metric_id == "revenue" or row.metric_id.startswith("sec_")
    )
    usable_financial = tuple(
        row
        for row in financial
        if row.value is not None
        and row.window is not None
        and row.window.end >= now - timedelta(days=550)
    )
    financial_ids = {row.observation_id for row in financial}
    outlook = StartupOutlook(
        company_id=company_id,
        source_snapshot_id=report_id,
        as_of=now,
        grouping_policy_version="research-v2-unassigned-v1",
        synthetic=False,
        forecasts=tuple(
            OutcomeForecast(outcome_id=outcome, horizon_months=horizon)
            for outcome, horizon in FORECAST_HORIZONS.items()
        ),
        specialists=tuple(
            SpecialistOutlook(
                group_id=group,
                data_status="available" if usable_financial else "insufficient_data",
                metric_observation_ids=tuple(row.observation_id for row in financial),
                usable_metric_observation_ids=tuple(
                    row.observation_id for row in usable_financial
                ),
                evidence_ids=tuple(
                    sorted(
                        {key for row in usable_financial for key in row.evidence_ids}
                    )
                ),
                reason_codes=(
                    "model_not_trained",
                    "sec_annual_financial_component_only",
                ),
            )
            if group == "financial_health" and financial
            else SpecialistOutlook(
                group_id=group,
                data_status="insufficient_data",
                reason_codes=("model_not_trained", "no_approved_metric_group_mapping"),
            )
            for group in SPECIALIST_GROUP_IDS
        ),
        unassigned_metric_observation_ids=tuple(
            row.observation_id
            for row in observations
            if row.observation_id not in financial_ids
        ),
    )
    limitations = [
        "Collection is bounded; absent evidence is not evidence of business failure.",
        "Company disclosures are attributed claims; logos do not establish customers.",
        "Revenue, retention, cash, burn and competitor coverage may be unavailable.",
        (
            "Conflicting statements are retained; differing dates or "
            "definitions may explain disagreements."
        ),
        (
            "News discovery returns candidates; only explicit domain links "
            "establish a domain match."
        ),
        (
            "Saved context retains its original collection dates and "
            "synthetic flag in identity.saved_context."
        ),
        (
            "Outcome forecasts remain null; experimental dimensions are separate."
            if models
            else "Growth, survival and complete business scores remain unavailable."
        ),
    ]
    limitations.extend(
        f"{source.name}: {', '.join(source.reason_codes)}"
        for source in job.sources
        if source.reason_codes
    )
    return Report(
        report_id=report_id,
        job_id=job.job_id,
        researched_at=now,
        identity=identity,
        sources=job.sources,
        observations=tuple(observations),
        claims=_conflicting_claims(job),
        events=tuple(row for source in job.sources for row in source.events),
        evidence=(*identity.evidence, *support),
        captures=(*identity.captures, *captures),
        outlook=outlook,
        dimension_models=models.evaluate_inputs(_dimension_inputs(job, outlook))
        if models
        else None,
        limitations=tuple(limitations),
    )
