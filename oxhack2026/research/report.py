"""Compose saved company facts and fresh attention without changing v1 publications."""

from oxhack2026.api.company_schemas import CompanyDetail, public_source
from oxhack2026.api.research_schemas import (
    ResearchInventory,
    ResearchJob,
    ResearchReport,
)
from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.startup_outlook import (
    SpecialistGroupId,
    SpecialistOutlook,
    StartupOutlook,
    build_untrained_outlook,
)
from oxhack2026.research.attention import AttentionCapture

_METRIC_GROUPS: dict[str, SpecialistGroupId] = {
    "npm_downloads_30d_v1": "adoption_retention",
    "npm_downloads_previous_30d_v1": "adoption_retention",
    "active_paying_customers_v1": "adoption_retention",
    "github_stable_releases_90d_v1": "team_execution",
    "revenue_12m_usd_v1": "financial_health",
    "operating_cashflow_12m_usd_v1": "financial_health",
}


def build_report(
    job: ResearchJob,
    saved: CompanyDetail,
    source: CompanySourceSnapshot,
    captured: AttentionCapture,
) -> ResearchReport:
    """Build an immutable inventory and shared null-model outlook at report cutoff.

    Args:
        job: Claimed job with confirmed exact saved identity.
        saved: Public-safe saved context from the exact assessment publication.
        source: Verified underlying source; never mutated or republished here.
        captured: Separately raw-backed fresh attention observation and evidence.
    Returns:
        One report resolving every saved/fresh reference, with no model inference.
    Raises:
        ValueError: Source/identity/timing or inventory references are inconsistent.
    """
    inventory_id = f"research-inventory-{job.job_id}"
    cutoff = captured.evidence.collected_at
    if (
        source.snapshot_id != saved.publication.source.snapshot_id
        or saved.publication.assessment.publication_id
        != job.request.assessment_publication_id
        or saved.company.company_id != job.request.company_id
        or captured.evidence.company_id != job.request.company_id
        or captured.observation.company_id != job.request.company_id
        or cutoff < (job.started_at or job.requested_at)
    ):
        message = "Research inputs disagree with the confirmed identity or job time"
        raise ValueError(message)
    # This derived view only recomputes freshness; the saved publication is retained.
    view = CompanySourceSnapshot.model_validate(
        source.model_dump()
        | {"snapshot_id": inventory_id, "as_of": cutoff, "recorded_at": cutoff}
    )
    definitions = {row.metric_id for row in source.definitions}
    mapping = {
        key: value for key, value in _METRIC_GROUPS.items() if key in definitions
    }
    saved_outlook = build_untrained_outlook(
        view, job.request.company_id, mapping, "research-metric-groups-v1"
    )
    observation = captured.observation
    attention = SpecialistOutlook(
        group_id="attention_sentiment",
        data_status="available" if captured.complete else "insufficient_data",
        metric_observation_ids=(observation.observation_id,),
        usable_metric_observation_ids=(observation.observation_id,)
        if captured.complete
        else (),
        evidence_ids=observation.evidence_ids if captured.complete else (),
        reason_codes=("model_not_trained", *observation.reason_codes),
    )
    outlook = StartupOutlook.model_validate(
        saved_outlook.model_dump()
        | {
            "specialists": tuple(
                attention if row.group_id == "attention_sentiment" else row
                for row in saved_outlook.specialists
            )
        }
    )
    return ResearchReport(
        report_id=f"report-{job.job_id}",
        job_id=job.job_id,
        researched_at=cutoff,
        source_publication_id=source.snapshot_id,
        assessment_publication_id=job.request.assessment_publication_id,
        inventory=ResearchInventory(
            inventory_id=inventory_id,
            company_id=job.request.company_id,
            as_of=cutoff,
            synthetic=source.synthetic,
            saved_context=saved,
            observations=(observation,),
            evidence=(public_source(captured.evidence),),
            capture_sha256=captured.evidence.raw_artifact.sha256,
            capture_byte_size=captured.evidence.raw_artifact.byte_size,
        ),
        outlook=outlook,
        limitations=(
            "Fresh research covers one bounded HN exact-domain link query only.",
            "Other metrics are saved context with their original measurement dates; "
            "their usability is re-evaluated at the report cutoff.",
            "HN links do not establish broad sentiment, customers or company success.",
            "Unknown-company identity resolution and trained predictions "
            "are unavailable.",
        ),
    )
