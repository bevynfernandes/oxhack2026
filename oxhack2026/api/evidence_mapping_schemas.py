"""Versioned evidence interpretation, separate from forecasting readiness."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, model_validator

from oxhack2026.api.research_analysis import InterpretationStatistics, ResearchAnalysis
from oxhack2026.api.research_configuration import ResearchSettings
from oxhack2026.api.schemas import DTO, Identifier, UTCDateTime
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS, SpecialistGroupId
from oxhack2026.storage.contracts import ArtifactReference

MappingState = Literal[
    "pending", "running", "completed", "partial", "failed", "skipped"
]
SubjectKind = Literal["company", "product", "customer", "third_party", "unresolved"]
MAPPING_DEADLINE_SECONDS = 120


class QuoteAnchor(DTO):
    """Exact selection in a hashed, normalized document derived from a capture."""

    evidence_id: Identifier
    capture_id: Identifier
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    block_id: Identifier
    exact: str = Field(min_length=1, max_length=4000)
    prefix: str = Field(default="", max_length=120)
    suffix: str = Field(default="", max_length=120)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    location: str

    @model_validator(mode="after")
    def _positions(self) -> Self:
        if self.end - self.start != len(self.exact):
            message = "Quote offsets must select the exact normalized text"
            raise ValueError(message)
        return self


class MappedRecord(DTO):
    """An attributable interpretation; source support does not verify truth."""

    mapping_id: Identifier
    record_type: Literal["observation", "claim", "event"]
    record_id: Identifier
    group_id: SpecialistGroupId
    concept: Identifier
    subject: SubjectKind
    subject_name: str
    attribution: Literal[
        "platform_measured", "company_reported", "registry", "coverage_candidate"
    ]
    method: Literal["rule", "gemini"]
    evidence_ids: tuple[Identifier, ...]
    quotes: tuple[QuoteAnchor, ...] = ()
    resource: str | None = None
    language: str = "und"
    published_on: str | None = None
    metric_eligible: bool = False
    exact_decimal: str | None = None
    numerical_context: "NumericalContext | None" = None
    qualifier: Literal[
        "exact", "approximate", "lower_bound", "upper_bound", "range", "unknown"
    ] = "unknown"
    reason_codes: tuple[str, ...]


class NumericalContext(DTO):
    """An attributed numeric expression; normalization does not verify its truth."""

    value_decimal: str = Field(pattern=r"^-?\d+(?:\.\d+)?$")
    unit: Literal["currency", "percent", "count"]
    currency: str | None = None
    measurement_start: date | None = None
    measurement_end: date | None = None
    measurement_instant: date | None = None
    qualifier: Literal["exact", "approximate", "lower_bound", "upper_bound"]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not Decimal(self.value_decimal).is_finite():
            message = "Normalized decimal must be finite"
            raise ValueError(message)
        if (self.unit == "currency") != (self.currency is not None):
            message = "Only currency quantities require an explicit currency"
            raise ValueError(message)
        if (self.measurement_start is None) != (self.measurement_end is None):
            message = "Measurement windows require both dates"
            raise ValueError(message)
        if self.measurement_start and self.measurement_end:
            if self.measurement_end < self.measurement_start:
                message = "Measurement end precedes start"
                raise ValueError(message)
            if self.measurement_instant is not None:
                message = "A quantity cannot have both a window and an instant"
                raise ValueError(message)
        return self


class MappingDisposition(DTO):
    """Explain why a candidate was rejected or remains unmapped."""

    candidate_id: Identifier
    state: Literal["rejected", "unmapped"]
    reason: str


class DimensionCoverage(DTO):
    """Evidence coverage without implying a trained model or verified prose."""

    group_id: SpecialistGroupId
    status: Literal["measured", "reported", "missing", "not_applicable"]
    mapping_ids: tuple[Identifier, ...] = ()
    observation_ids: tuple[Identifier, ...] = ()
    claim_ids: tuple[Identifier, ...] = ()
    event_ids: tuple[Identifier, ...] = ()
    reason_codes: tuple[str, ...] = ()


class MappingProgress(DTO):
    """Durable mapping progress, independent of collection sources."""

    statistics: InterpretationStatistics | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    state: MappingState = "pending"
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    completed_batches: int = Field(default=0, ge=0)
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        terminal = self.state in {"completed", "partial", "failed", "skipped"}
        if terminal != (self.finished_at is not None):
            message = "Terminal mapping progress requires a finish time"
            raise ValueError(message)
        if self.state == "running" and self.started_at is None:
            message = "Running mapping requires a start time"
            raise ValueError(message)
        if self.finished_at and self.started_at and self.finished_at < self.started_at:
            message = "Mapping finish precedes its start"
            raise ValueError(message)
        return self


class MappingBundle(DTO):
    """Immutable mapping provenance and its exact supporting artifacts."""

    schema_version: Literal["evidence-mapping-v1", "evidence-mapping-v2"] = (
        "evidence-mapping-v1"
    )
    statistics: InterpretationStatistics | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    analysis: ResearchAnalysis | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    policy_version: Literal["public-evidence-mapping-v1"] = "public-evidence-mapping-v1"
    parser_version: Literal["evidence-document-v1", "evidence-document-v2"] = (
        "evidence-document-v2"
    )
    prompt_version: Literal["evidence-proposals-v1"] = "evidence-proposals-v1"
    mapped_at: UTCDateTime
    source_as_of: UTCDateTime
    derived_from_report_id: Identifier | None = None
    state: Literal["completed", "partial"]
    mode: Literal["rules", "rules_gemini"]
    records: tuple[MappedRecord, ...]
    dimensions: tuple[DimensionCoverage, ...]
    dispositions: tuple[MappingDisposition, ...] = ()
    artifacts: tuple[ArtifactReference, ...] = ()
    model: str | None = None
    model_version: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    generation_attempts: int = Field(default=0, ge=0, le=24)
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _inventory(self) -> Self:
        if tuple(row.group_id for row in self.dimensions) != SPECIALIST_GROUP_IDS:
            message = "Mapping requires all five ordered dimensions"
            raise ValueError(message)
        identifiers = {row.mapping_id for row in self.records}
        if self.analysis and any(
            not set(statement.mapping_ids) <= identifiers
            for statement in self.analysis.statements
        ):
            message = "Analysis cites an absent mapped record"
            raise ValueError(message)
        if len(identifiers) != len(self.records):
            message = "Mapping identifiers must be unique"
            raise ValueError(message)
        records = {(row.record_type, row.record_id) for row in self.records}
        if len(records) != len(self.records):
            message = "Each record requires one primary dimension assignment"
            raise ValueError(message)
        referenced = [item for row in self.dimensions for item in row.mapping_ids]
        if len(referenced) != len(set(referenced)) or set(referenced) != identifiers:
            message = "Every mapping must belong to exactly one dimension"
            raise ValueError(message)
        groups = {row.mapping_id: row.group_id for row in self.records}
        if any(
            groups[key] != row.group_id
            for row in self.dimensions
            for key in row.mapping_ids
        ):
            message = "Dimension references a mapping from another group"
            raise ValueError(message)
        indexed = {row.mapping_id: row for row in self.records}
        for dimension in self.dimensions:
            rows = [indexed[key] for key in dimension.mapping_ids]
            expected = (
                tuple(row.record_id for row in rows if row.record_type == kind)
                for kind in ("observation", "claim", "event")
            )
            if tuple(expected) != (
                dimension.observation_ids,
                dimension.claim_ids,
                dimension.event_ids,
            ):
                message = "Dimension record references disagree with its mappings"
                raise ValueError(message)
        return self


class MappingJobRequest(DTO):
    """Explicitly request a new interpretation of retained source evidence."""

    source_report_id: Identifier
    cache_policy: Literal["reuse", "bypass"] = Field(default_factory=lambda: "reuse")


class MappingJob(DTO):
    """Durable re-mapping work sharing the research worker capacity."""

    settings: ResearchSettings | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    schema_version: Literal["research-mapping-job-v1"] = "research-mapping-job-v1"
    job_id: Identifier
    source_report_id: Identifier
    cache_policy: Literal["reuse", "bypass"] = Field(default_factory=lambda: "reuse")
    requested_at: UTCDateTime
    progress: MappingProgress = Field(default_factory=MappingProgress)
    report_id: Identifier | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.progress.state in {"completed", "partial"}) != (
            self.report_id is not None
        ):
            message = "Useful mapping results require a new report"
            raise ValueError(message)
        for instant in (self.progress.started_at, self.progress.finished_at):
            if instant and instant < self.requested_at:
                message = "Mapping progress precedes the request"
                raise ValueError(message)
        return self


class MappingCapability(DTO):
    """Local configuration only; no vendor probe is performed."""

    enabled: bool
    mode: Literal["rules", "rules_gemini"]
    gemini_available: bool
    reason: str | None = None
    deadline_seconds: int = MAPPING_DEADLINE_SECONDS
