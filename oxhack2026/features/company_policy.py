"""Shared public-evidence usability for company narratives and model inputs."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Literal

from oxhack2026.catalog.company import (
    CompanyMetricObservation,
    MetricDefinition,
    SourceEvidence,
)

PublicEvidenceState = Literal["restricted", "unverified"]
CompanyMetricState = Literal[
    "observed",
    "missing",
    "not_applicable",
    "conflicting",
    "stale",
    "restricted",
    "unverified",
]


def public_evidence_state(
    evidence_ids: tuple[str, ...], evidence: Mapping[str, SourceEvidence]
) -> PublicEvidenceState | None:
    """Return why source support is unusable, or None for verified public evidence.

    Args:
        evidence_ids: Complete support set from a validated company source record.
        evidence: Exact source snapshot's evidence lookup.
    Returns:
        Restricted takes precedence over unverified/disputed; otherwise None.
    Raises:
        KeyError: A required evidence ID is absent from invalid input.
    """
    if any(evidence[key].access != "public" for key in evidence_ids):
        return "restricted"
    if any(evidence[key].review_state != "verified" for key in evidence_ids):
        return "unverified"
    return None


def company_metric_state(
    observation: CompanyMetricObservation,
    definition: MetricDefinition,
    evidence: Mapping[str, SourceEvidence],
    as_of: datetime,
) -> CompanyMetricState:
    """Classify public metric usability at the frozen source cutoff.

    Args:
        observation: Validated C1 metric, retaining source missingness/applicability.
        definition: Its exact source-owned measurement and freshness definition.
        evidence: Complete evidence lookup from that source publication.
        as_of: Validated UTC source cutoff, never the current execution clock.
    Returns:
        Observed only for fresh, verified public support; otherwise an explicit
        source-state, access/review or freshness reason. Values remain unchanged.
    Raises:
        KeyError: Evidence references are missing from invalid input.
    """
    if observation.state != "observed":
        return observation.state
    reason = public_evidence_state(observation.evidence_ids, evidence)
    if reason is not None:
        return reason
    if as_of - observation.measurement_end > timedelta(
        days=definition.maximum_age_days
    ):
        return "stale"
    return "observed"
