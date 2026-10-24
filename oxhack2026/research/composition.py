"""Compose immutable reports with explicit gaps and shared null model forecasts."""

import re
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from oxhack2026.api.research_v2_schemas import Claim, Identity, Job, Observation, Report
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


def compose(job: Job, identity: Identity) -> Report:
    """Build a fresh report; saved context alone never qualifies as a fresh result.

    Args:
        job: Source checkpoints after every enabled collector has stopped.
        identity: Exact confirmed discovery preview, including conflicts/context.
    Returns:
        Validated immutable report retaining claims without invented metrics.
    """
    now = datetime.now(UTC)
    observations = [row for source in job.sources for row in source.observations]
    for metric_id, (unit, reason) in _GAPS.items():
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
                data_status="insufficient_data",
                reason_codes=("model_not_trained", "no_approved_metric_group_mapping"),
            )
            for group in SPECIALIST_GROUP_IDS
        ),
        unassigned_metric_observation_ids=tuple(
            row.observation_id for row in observations
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
        "Numerical forecasts remain null; no models were trained or run.",
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
        limitations=tuple(limitations),
    )
