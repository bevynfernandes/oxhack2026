"""Lightweight evaluation, evidence, and shortlist policy interfaces."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from oxhack2026.models.contracts import (
    ArtifactReference,
    Contract,
    Ecosystem,
    EvidenceStatus,
    TargetId,
    TimeWindow,
)


class MetricDefinition(Contract):
    """Versioned metric meaning, units, aggregation, and optimization direction."""

    metric_id: str
    description: str
    unit: str
    aggregation: Literal["origin_macro", "row_macro", "subgroup"]
    direction: Literal["maximize", "minimize", "diagnostic"]


class MetricValue(Contract):
    """Metric on a named common candidate universe; undefined values remain null."""

    metric_id: str
    model_id: str
    candidate_universe_id: str
    value: float | None
    row_count: int = Field(ge=0)
    origin_count: int = Field(ge=0)
    organization_count: int = Field(ge=0)
    exclusion_reasons: tuple[str, ...] = ()


class CohortCounts(Contract):
    """Coverage and exclusions, kept separate from conditional model performance."""

    candidate_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    organization_count: int = Field(ge=0)
    origin_count: int = Field(ge=0)
    headline_origin_count: int = Field(ge=0)
    exclusions: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Return counts; raise ValueError for negative or contradictory coverage."""
        if (
            self.eligible_count > self.candidate_count
            or self.organization_count > self.candidate_count
            or self.headline_origin_count > self.origin_count
            or any(count < 0 for count in self.exclusions.values())
        ):
            message = "Coverage counts must be nonnegative and internally consistent"
            raise ValueError(message)
        return self


class EvaluationReport(Contract):
    """Result state with exact periods, frozen protocol, and reproducible files."""

    schema_version: Literal["evaluation-v1"] = "evaluation-v1"
    evaluation_id: str
    experiment_id: str
    ecosystem: Ecosystem
    target_id: TargetId
    dataset_version: str
    mapping_version: str
    evidence_status: EvidenceStatus
    serving_model_id: str
    fallback_model_id: str
    period: TimeWindow
    counts: CohortCounts
    metrics: tuple[MetricValue, ...]
    metric_definitions: tuple[MetricDefinition, ...]
    experiment_manifest: ArtifactReference
    effective_block_count: int = Field(ge=0)
    statistical_superiority: bool = False
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Return the report; raise ValueError for unsupported superiority claims."""
        minimum_origins = 40 if self.target_id == "downloads_next_30d_v1" else 104
        if self.statistical_superiority and (
            self.evidence_status != "validated"
            or self.effective_block_count < 8
            or self.counts.headline_origin_count < minimum_origins
        ):
            message = "Superiority requires validated evidence and eight horizon blocks"
            raise ValueError(message)
        return self


class EvidenceItem(Contract):
    """Dated measured evidence, separate from cautious predictive interpretations."""

    evidence_id: str
    tool_id: str
    source: str
    source_revision_ids: tuple[str, ...]
    window: TimeWindow
    available_at: datetime
    availability_basis: str
    source_url: str | None = None
    measured_change: str
    predictive_interpretation: str | None = None
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        """Return evidence; raise ValueError for premature or non-UTC availability."""
        TimeWindow.validate_utc(self.available_at)
        if self.available_at < self.window.end:
            message = "Measured evidence cannot be available before its window ends"
            raise ValueError(message)
        return self


class RankedCandidate(Contract):
    """Organization representative produced by the single shared ranking policy."""

    forecast_id: str
    tool_id: str
    organization_id: str
    rank: int = Field(ge=1)
    predicted_growth_pct: float


class ShortlistScore(Contract):
    """Frozen manual selection score; missing truth yields missing metrics."""

    forecast_ids: tuple[str, ...]
    candidate_universe_id: str
    selection_count: int = Field(ge=0, le=5)
    eligible_organization_count: int = Field(ge=0)
    headline_eligible: bool
    complete_outcomes: bool
    mean_realized_log_growth: float | None
    precision_at_5: float | None
    recall_at_5: float | None
    regret: float | None
    reason_codes: tuple[str, ...] = ()


class OutcomeDiagnostics(Contract):
    """Separately revealed truth and model-owned per-tool numerical diagnostics."""

    forecast_id: str
    outcome_vintage: str
    actual_downloads: int = Field(ge=0)
    realized_growth_pct: float | None
    model_absolute_error: float | None = Field(default=None, ge=0)
    baseline_absolute_error: float | None = Field(default=None, ge=0)
    model_log_absolute_error: float | None = Field(default=None, ge=0)
    baseline_log_absolute_error: float | None = Field(default=None, ge=0)
    reason_codes: tuple[str, ...] = ()
