"""Versioned numerical artifacts; importing these types starts no services."""

from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from oxhack2026.features.definitions import (
    HISTORY_DAYS,
    MIN_REFERENCE_COUNT,
    require_utc,
    target_windows,
)

SCHEMA_VERSION: Literal["models-v1"] = "models-v1"
Ecosystem = Literal["npm", "pypi"]
TargetId = Literal["downloads_next_30d_v1", "downloads_trailing_28d_at_91d_v1"]
ForecastMode = Literal["reconstructed", "prospective"]
EvidenceStatus = Literal["exploratory", "validated", "inconclusive", "rejected"]
ReasonCode = Literal[
    "insufficient_history",
    "missing_source",
    "low_reference_count",
    "unverified_mapping",
    "unvalidated_interval",
    "immature_outcome",
]


class Contract(BaseModel):
    """Immutable, strict artifacts rejecting unknown fields and nonfinite numbers."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ArtifactReference(Contract):
    """Relative bundle path and SHA-256 digest; paths cannot escape the bundle."""

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Return a relative POSIX path or raise ValueError for unsafe paths.

        Args:
            value: Artifact path relative to the receiving bundle root.
        Returns:
            The unchanged safe path.
        Raises:
            ValueError: If the path is absolute, traverses parents, or uses backslashes.
        """
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or value == ".":
            message = "Artifact paths must stay within the bundle root"
            raise ValueError(message)
        return value


class TimeWindow(Contract):
    """Nonempty half-open measurement interval with timezone-aware UTC bounds."""

    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        """Return a UTC instant or raise ValueError for naive/non-UTC timestamps.

        Args:
            value: Measurement boundary.
        Returns:
            Boundary normalized to datetime.UTC.
        Raises:
            ValueError: If the boundary lacks a timezone or has a nonzero offset.
        """
        return require_utc(value).astimezone(UTC)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Return this interval; raise ValueError unless start precedes end."""
        if self.start >= self.end:
            message = "Half-open intervals require start < end"
            raise ValueError(message)
        return self


class TargetWindows(Contract):
    """One decision's target definition, fixed observation anchor, and windows."""

    target_id: TargetId
    decision_at: datetime
    observation_window_end: datetime
    reference: TimeWindow
    target: TimeWindow
    definition_version: Literal["targets-v1"] = "targets-v1"

    @model_validator(mode="after")
    def validate_boundaries(self) -> Self:
        """Return valid plan windows; raise ValueError for inconsistent boundaries."""
        expected = target_windows(self.decision_at, self.target_id)
        require_utc(self.observation_window_end)
        if (
            self.observation_window_end != expected.observation_end
            or self.reference.start != expected.reference_start
            or self.reference.end != expected.reference_end
            or self.target.start != expected.target_start
            or self.target.end != expected.target_end
        ):
            message = "Windows must match the versioned target and 48-hour lag"
            raise ValueError(message)
        return self


class RowIdentity(Contract):
    """Frozen tool/package/company identity within one ecosystem and dataset."""

    tool_id: str = Field(min_length=1)
    organization_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    ecosystem: Ecosystem
    dataset_version: str = Field(min_length=1)
    mapping_version: str = Field(min_length=1)


class FeatureRow(Contract):
    """Feature vector with explicit missingness and immutable source references."""

    feature_row_id: str
    identity: RowIdentity
    windows: TargetWindows
    mode: ForecastMode
    feature_schema_version: str
    values: dict[str, float | None]
    complete_history_days: int = Field(ge=0)
    source_revision_ids: tuple[str, ...]
    forecast_eligible: bool
    reason_codes: tuple[ReasonCode, ...] = ()

    @model_validator(mode="after")
    def validate_history(self) -> Self:
        """Return this row; raise ValueError for eligibility below 84 complete days."""
        if self.forecast_eligible and self.complete_history_days < HISTORY_DAYS:
            message = "Learned forecast eligibility requires 84 complete history days"
            raise ValueError(message)
        return self


class LabelRow(Contract):
    """Separate label row; an unavailable outcome remains null, including its time."""

    feature_row_id: str
    windows: TargetWindows
    actual_downloads: int | None = Field(default=None, ge=0)
    available_at: datetime | None = None
    outcome_revision_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_maturity(self) -> Self:
        """Return the label; raise ValueError for incomplete or premature outcomes."""
        if (self.actual_downloads is None) != (self.available_at is None):
            message = "An actual outcome requires its availability timestamp"
            raise ValueError(message)
        if self.available_at is not None:
            TimeWindow.validate_utc(self.available_at)
            if self.available_at < self.windows.target.end:
                message = "Outcome cannot be available before target completion"
                raise ValueError(message)
        return self


class ModelReference(Contract):
    """Frozen model and optional paired calibrator, scoped to ecosystem/target."""

    model_id: str
    experiment_id: str
    ecosystem: Ecosystem
    target_id: TargetId
    model_artifact: ArtifactReference
    calibration_id: str | None = None
    calibration_artifact: ArtifactReference | None = None

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        """Return the reference; raise ValueError for an incomplete calibrator pair."""
        if (self.calibration_id is None) != (self.calibration_artifact is None):
            message = "Calibration ID and artifact must be supplied together"
            raise ValueError(message)
        return self


class PredictionInterval(Contract):
    """Empirically validated aggregate band, never an invented daily trajectory."""

    interval_lower: float = Field(ge=0)
    interval_upper: float = Field(ge=0)
    nominal_coverage: float = Field(gt=0, lt=1)
    interval_method: str
    calibration_id: str

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Return the band; raise ValueError for crossing endpoints."""
        if self.interval_lower > self.interval_upper:
            message = "Interval endpoints must be ordered"
            raise ValueError(message)
        return self


class ForecastResult(Contract):
    """Immutable pre-reveal prediction; this contract contains no realized outcome."""

    forecast_id: str
    batch_id: str
    identity: RowIdentity
    windows: TargetWindows
    feature_row_id: str
    feature_schema_version: str
    model_id: str
    experiment_id: str
    mode: ForecastMode
    evidence_status: EvidenceStatus
    reference_downloads: int | None = Field(default=None, ge=0)
    predicted_downloads: float | None = Field(default=None, ge=0)
    predicted_growth_pct: float | None = None
    estimate_kind: Literal["conditional_median", "log_space_point", "baseline"]
    interval: PredictionInterval | None = None
    baseline_model_id: str
    baseline_predicted_downloads: float | None = Field(default=None, ge=0)
    forecast_status: Literal["ready", "unavailable"]
    ranking_eligible: bool
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    data_age_hours: float | None = Field(default=None, ge=0)
    stale: bool = False

    @model_validator(mode="after")
    def validate_prediction(self) -> Self:
        """Return the forecast; raise ValueError for inconsistent eligibility/counts."""
        ready = self.forecast_status == "ready"
        if ready != (self.predicted_downloads is not None):
            message = "Ready forecasts require a prediction; unavailable do not"
            raise ValueError(message)
        if ready and self.reference_downloads is None:
            message = "Ready forecasts require a reference count"
            raise ValueError(message)
        can_rank = (
            ready
            and self.reference_downloads is not None
            and self.reference_downloads >= MIN_REFERENCE_COUNT
        )
        if self.ranking_eligible and not can_rank:
            message = "Ranking requires a ready forecast and reference >= 1000"
            raise ValueError(message)
        if self.predicted_growth_pct is not None:
            if (
                not can_rank
                or self.reference_downloads is None
                or self.predicted_downloads is None
            ):
                message = "Percentage growth requires reference >= 1000"
                raise ValueError(message)
            expected = 100 * (self.predicted_downloads / self.reference_downloads - 1)
            if abs(self.predicted_growth_pct - expected) > 1e-8:
                message = "Growth must agree with predicted and reference counts"
                raise ValueError(message)
        elif self.ranking_eligible:
            message = "Ranking requires predicted percentage growth"
            raise ValueError(message)
        if self.interval is not None and (
            not ready or self.evidence_status != "validated"
        ):
            message = "Serving intervals require a ready, validated forecast"
            raise ValueError(message)
        return self


class MatureOutcome(Contract):
    """Separately revealed complete truth, with an explicitly identified vintage."""

    forecast_id: str
    label: LabelRow
    outcome_vintage: str
    first_complete_vintage: bool

    @model_validator(mode="after")
    def validate_complete(self) -> Self:
        """Return truth; raise ValueError if the label remains immature."""
        if self.label.actual_downloads is None:
            message = "Reveal requires a complete, available label"
            raise ValueError(message)
        return self


class FeatureManifest(Contract):
    """Feature/label bundle binding source data, policies, code, and schemas."""

    schema_version: Literal["models-v1"] = SCHEMA_VERSION
    dataset_version: str
    mapping_version: str
    feature_schema_version: str
    availability_policy_version: str
    code_revision: str
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    features: ArtifactReference
    labels: ArtifactReference
    synthetic: bool
    limitations: tuple[str, ...] = ()


class ForecastManifest(Contract):
    """Published batch with outcomes stored as separate versioned artifacts."""

    schema_version: Literal["models-v1"] = SCHEMA_VERSION
    batch_id: str
    windows: TargetWindows
    ecosystem: Ecosystem
    dataset_version: str
    mapping_version: str
    feature_schema_version: str
    model: ModelReference
    mode: ForecastMode
    first_recorded_at: datetime
    forecasts: ArtifactReference
    evidence: ArtifactReference
    synthetic: bool
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        """Return the manifest; raise ValueError for mixed scopes or late live runs."""
        TimeWindow.validate_utc(self.first_recorded_at)
        if (
            self.model.ecosystem != self.ecosystem
            or self.model.target_id != self.windows.target_id
        ):
            message = "Model and forecast batch must use the same scope"
            raise ValueError(message)
        if (
            self.mode == "prospective"
            and self.first_recorded_at >= self.windows.decision_at
        ):
            message = "Late recordings cannot be called prospective"
            raise ValueError(message)
        return self
