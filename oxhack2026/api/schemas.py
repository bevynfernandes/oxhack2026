"""C3 public contracts; outcomes are separate from forecast DTOs."""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

CONTRACT_VERSION = "0.4.0"
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
Ecosystem = Literal["npm", "pypi"]
Target = Literal["downloads_next_30d_v1", "downloads_trailing_28d_at_91d_v1"]
EvidenceStatus = Literal["exploratory", "inconclusive", "rejected", "validated"]
Count = Annotated[int, Field(ge=0, strict=True)]
Number = Annotated[float, Field(allow_inf_nan=False)]
Estimate = Annotated[float, Field(ge=0, allow_inf_nan=False)]


def _utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        message = "Timestamps must use UTC"
        raise ValueError(message)
    return value


def _public_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        message = "Public links require HTTPS without credentials or query data"
        raise ValueError(message)
    return value


UTCDateTime = Annotated[AwareDatetime, AfterValidator(_utc)]
PublicURL = Annotated[str, Field(max_length=2048), AfterValidator(_public_url)]


class DTO(BaseModel):
    """Immutable public fields; undeclared upstream data fails validation."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always"
    )


class Window(DTO):
    """A UTC half-open measurement interval [start, end)."""

    start: UTCDateTime
    end: UTCDateTime

    @model_validator(mode="after")
    def ordered(self) -> Self:
        """Return this window; raise ValueError for empty/reversed bounds."""
        if self.start >= self.end:
            message = "Window end must follow start"
            raise ValueError(message)
        return self


class Provenance(DTO):
    """Public immutable version references, never storage locations or secrets."""

    dataset_version: Identifier
    catalog_version: Identifier
    mapping_version: Identifier
    feature_schema_version: Identifier
    evidence_version: Identifier
    experiment_id: Identifier
    synthetic: bool
    limitations: tuple[str, ...] = ()


class Evidence(DTO):
    """Persisted evidence whose availability is bounded by the decision cutoff."""

    evidence_id: Identifier
    source: str
    observed_at: UTCDateTime
    available_at: UTCDateTime
    kind: Literal["measurement", "interpretation", "limitation", "mapping"]
    text: str
    url: PublicURL | None = None


class Freshness(DTO):
    """Published quality assessment, independent of model validation status."""

    as_of: UTCDateTime | None
    stale: bool
    completeness: Literal["complete", "partial", "unavailable"]
    reasons: tuple[str, ...] = ()


class Tool(DTO):
    """Verified tool-to-package and organization mapping in one ecosystem."""

    tool_id: Identifier
    tool_name: str
    organization_id: Identifier
    organization_name: str
    package_id: Identifier
    package_name: str
    ecosystem: Ecosystem
    category: str
    representative: bool
    mapping_verification: Literal["before_cutoff", "retrospective"] = "before_cutoff"
    mapping_evidence: tuple[Evidence, ...]


class Catalog(DTO):
    """Versioned catalogue; batch reads use the batch's frozen mapping."""

    catalog_version: Identifier
    mapping_version: Identifier
    synthetic: bool
    tools: tuple[Tool, ...]
    recorded_at: UTCDateTime | None = None
    cohort_kind: Literal["contemporary_catalogue", "historical_eligibility"] = (
        "contemporary_catalogue"
    )
    membership_basis: Literal["decision_time", "contemporary_reconstruction"] = (
        "decision_time"
    )
    limitations: tuple[str, ...] = ()


class Cutoff(DTO):
    """An explicitly published, selectable forecast batch."""

    batch_id: Identifier
    ecosystem: Ecosystem
    target_id: Target
    decision_at: UTCDateTime
    mode: Literal["reconstructed", "prospective"]
    evaluation_id: Identifier | None
    synthetic: bool


class Cutoffs(DTO):
    """Supported combinations only; no interpolation to another cutoff."""

    items: tuple[Cutoff, ...]


class Interval(DTO):
    """An interval already approved by the model owner's serving gate."""

    lower: Estimate
    upper: Estimate
    nominal_coverage: Annotated[float, Field(gt=0, lt=1)]
    method: str
    calibration_id: Identifier
    status: Literal["validated"]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        """Return the interval; raise ValueError for reversed endpoints."""
        if self.lower > self.upper:
            message = "Interval lower bound exceeds upper bound"
            raise ValueError(message)
        return self


class Baseline(DTO):
    """A saved comparator forecast, without any future outcome values."""

    model_id: Identifier
    predicted_downloads: Estimate


class Forecast(DTO):
    """One tool's saved aggregate prediction or explicit unavailable result."""

    forecast_id: Identifier
    feature_row_id: Identifier
    data_age_hours: Estimate | None = None
    tool_id: Identifier
    organization_id: Identifier
    package_id: Identifier
    model_id: Identifier
    availability: Literal["available", "unavailable"]
    reference_downloads: Count | None
    predicted_downloads: Estimate | None
    predicted_growth_pct: Number | None
    estimate_kind: Literal["conditional_median", "log_space_point", "baseline"]
    ranking_eligible: bool
    reasons: tuple[str, ...]
    interval: Interval | None
    baseline: Baseline | None
    evidence_status: EvidenceStatus
    evidence: tuple[Evidence, ...]
    freshness: Freshness

    @model_validator(mode="after")
    def consistent(self) -> Self:
        """Return this result; raise ValueError for contradictory public states."""
        if (self.availability == "available") != (self.predicted_downloads is not None):
            message = "Prediction must match availability"
            raise ValueError(message)
        if self.availability == "unavailable" and (
            self.ranking_eligible
            or self.interval is not None
            or self.predicted_growth_pct is not None
        ):
            message = "Unavailable forecasts cannot expose ranking or intervals"
            raise ValueError(message)
        if self.ranking_eligible and self.predicted_growth_pct is None:
            message = "Ranked forecasts require published growth"
            raise ValueError(message)
        return self


class ForecastBatch(DTO):
    """Frozen prediction payload; shared identity/time apply to every result."""

    contract_version: Literal["0.4.0"] = "0.4.0"
    batch_id: Identifier
    ecosystem: Ecosystem
    target_id: Target
    target_definition_version: Identifier
    decision_at: UTCDateTime
    observation_window_end: UTCDateTime
    reference_window: Window
    target_window: Window
    mode: Literal["reconstructed", "prospective"]
    provenance: Provenance
    results: tuple[Forecast, ...]
    evaluation_id: Identifier | None

    @model_validator(mode="after")
    def bounded(self) -> Self:
        """Return the batch; raise ValueError on duplicates or future evidence."""
        if not (
            self.reference_window.end
            == self.observation_window_end
            < self.decision_at
            <= self.target_window.start
        ):
            message = "Batch observation and prediction boundaries disagree"
            raise ValueError(message)
        if len({item.tool_id for item in self.results}) != len(self.results):
            message = "Forecast tool IDs must be unique"
            raise ValueError(message)
        if any(
            evidence.available_at > self.decision_at
            or evidence.observed_at > self.observation_window_end
            for item in self.results
            for evidence in item.evidence
        ):
            message = "Evidence exceeds the permitted forecast boundary"
            raise ValueError(message)
        return self


class Ranking(DTO):
    """Ordered representatives supplied by shared numerical policy."""

    name: str
    tool_ids: tuple[Identifier, ...]


class Exclusion(DTO):
    """A published ranking exclusion with its original reason codes."""

    tool_id: Identifier
    reasons: tuple[str, ...]


class Rankings(DTO):
    """Published ordering and comparators; the API never recomputes rankings."""

    batch_id: Identifier
    policy_version: Identifier
    primary: Ranking
    recommended_tool_ids: Annotated[tuple[Identifier, ...], Field(max_length=5)]
    baselines: tuple[Ranking, ...]
    exclusions: tuple[Exclusion, ...]
    shortfall_reason: str | None
    reveal_allowed: bool


class HistoryPoint(DTO):
    """One observed interval; missing counts remain null."""

    window: Window
    downloads: Count | None
    available_at: UTCDateTime
    completeness: Literal["complete", "missing", "partial"]
    revision_id: Identifier


class History(DTO):
    """Frozen, batch-bounded observation history."""

    batch_id: Identifier
    tool_id: Identifier
    dataset_version: Identifier
    observation_window_end: UTCDateTime
    points: tuple[HistoryPoint, ...]


class RevealRequest(DTO):
    """A bounded user selection; scores are delegated to the model owner."""

    organization_ids: Annotated[tuple[Identifier, ...], Field(max_length=5)]

    @model_validator(mode="after")
    def distinct(self) -> Self:
        """Return this request; raise ValueError for duplicate organizations."""
        if len(set(self.organization_ids)) != len(self.organization_ids):
            message = "Select distinct organizations"
            raise ValueError(message)
        return self


class Outcome(DTO):
    """Mature truth and saved errors, available only in a reveal response."""

    tool_id: Identifier
    actual_downloads: Count | None
    realized_growth_pct: Number | None
    model_absolute_error: Estimate | None
    baseline_absolute_error: Estimate | None
    reasons: tuple[str, ...]


class Score(DTO):
    """Authoritative shortlist score with explicit undefined/insufficient states."""

    name: str
    metric: str
    value: Number | None
    organization_ids: tuple[Identifier, ...]
    reason: str | None
    candidate_universe_id: Identifier | None = None
    headline_eligible: bool | None = None
    complete_outcomes: bool | None = None


class Reveal(DTO):
    """Separate mature outcomes and scores; never nested in a forecast DTO."""

    batch_id: Identifier
    outcome_vintage: Identifier
    available_at: UTCDateTime
    selected_organization_ids: tuple[Identifier, ...]
    outcomes: tuple[Outcome, ...]
    selection_score: Score
    selection_metrics: tuple[Score, ...] = ()
    comparators: tuple[Score, ...]
    limitations: tuple[str, ...]


class Metric(DTO):
    """Published comparison, including common-row and interval diagnostics."""

    model_id: Identifier
    name: str
    value: Number | None
    unit: str
    lower_is_better: bool | None
    sample_count: Count
    common_rows_id: Identifier | None
    limitations: tuple[str, ...]


class ReportLink(DTO):
    """Public immutable report link without signed storage credentials."""

    label: str
    url: PublicURL


class Evaluation(DTO):
    """Immutable evaluation, with failed and inconclusive results preserved."""

    evaluation_id: Identifier
    ecosystem: Ecosystem
    target_id: Target
    mode: Literal["reconstructed", "prospective"]
    status: EvidenceStatus
    test_window: Window
    origin_count: Count
    organization_count: Count
    sample_count: Count
    exclusions: tuple[str, ...]
    missingness: tuple[str, ...]
    metrics: tuple[Metric, ...]
    interval_findings: tuple[str, ...]
    conclusion: str
    limitations: tuple[str, ...]
    provenance: Provenance
    reports: tuple[ReportLink, ...]


class SourceHealth(DTO):
    """Public source coverage; diagnostics contain no internal error strings."""

    source: str
    ecosystem: Ecosystem | None
    freshness: Freshness
    missing_partitions: Count
    revisions: Count
    mapping_status: str
    connector_status: Literal["ready", "degraded", "unavailable"]


class DataHealth(DTO):
    """Public quality summary for the active published release."""

    synthetic: bool
    sources: tuple[SourceHealth, ...]


class Health(DTO):
    """Process or repository readiness, without sensitive configuration."""

    status: Literal["ready", "unavailable"]
    contract_version: str = CONTRACT_VERSION
    reasons: tuple[str, ...] = ()


class Error(DTO):
    """Stable public failure code and safe user-facing description."""

    code: str
    message: str
