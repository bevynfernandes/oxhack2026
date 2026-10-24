"""Company evidence contracts; raw facts are separate from model assessments."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from oxhack2026.catalog.schemas import (
    Contract,
    Count,
    Identifier,
    Name,
    PublicUrl,
    Sha256,
    TimeWindow,
    UtcInstant,
)
from oxhack2026.storage.contracts import ArtifactReference

MetricFamily = Literal["traction", "commercial", "execution", "market_financing"]
ObservationState = Literal["observed", "missing", "not_applicable", "conflicting"]
Text = Annotated[str, Field(min_length=1, max_length=4000)]
EvidenceIds = Annotated[tuple[Identifier, ...], Field(min_length=1)]


class CompanyProfile(Contract):
    """Snapshot-specific company identity/context; unknown context remains null."""

    company_id: Identifier
    display_name: Name
    website_url: PublicUrl
    segment: Identifier
    business_model: Name | None
    stage: Name | None
    context_as_of: UtcInstant
    evidence_ids: EvidenceIds


class CompanyRelationship(Contract):
    """Evidence-backed effective mapping, including explicit family membership.

    Family targets are opaque grouping IDs, not an implicit current parent.
    A self-family assertion needs evidence just like any other membership.
    """

    relationship_id: Identifier
    company_id: Identifier
    subject_kind: Literal["legal_entity", "tool", "package", "repository", "family"]
    subject_id: Identifier
    valid_from: UtcInstant
    valid_to: UtcInstant | None
    evidence_ids: EvidenceIds

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        """Return the mapping; raise ValueError for reversed/empty effective dates."""
        if self.valid_to is not None and self.valid_from >= self.valid_to:
            message = "Relationship requires valid_from < valid_to"
            raise ValueError(message)
        return self


class MetricDefinition(Contract):
    """Versioned measurement meaning; source freshness is not predictive confidence."""

    metric_id: Identifier
    family: MetricFamily
    label: Name
    definition: Text
    unit: Name
    value_kind: Literal["integer", "decimal", "boolean"]
    scope: Literal["company", "product", "repository"]
    applicability: Text
    maximum_age_days: Annotated[int, Field(gt=0, strict=True)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None


class IntegerValue(Contract):
    """Exact count, excluding Boolean and coercible string/float inputs."""

    kind: Literal["integer"] = "integer"
    value: Count


class DecimalValue(Contract):
    """Exact finite decimal serialized as a string; binary floats are rejected."""

    kind: Literal["decimal"] = "decimal"
    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def require_exact_input(cls, value: object) -> object:
        """Accept Decimal/string input; raise ValueError for lossy numeric coercion."""
        if not isinstance(value, (Decimal, str)):
            message = "Decimal metrics require decimal strings or Decimal values"
            raise ValueError(message)  # noqa: TRY004 - Pydantic validation error
        return value


class BooleanValue(Contract):
    """Explicit observed Boolean; absence is represented by observation state."""

    kind: Literal["boolean"] = "boolean"
    value: StrictBool


MetricValue = Annotated[
    IntegerValue | DecimalValue | BooleanValue, Field(discriminator="kind")
]


class EvidenceTiming(Contract):
    """Known-at and actual-collection bounds shared by observations and events."""

    available_at: UtcInstant
    collected_at: UtcInstant

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        """Return timing; raise ValueError if availability follows collection."""
        if self.available_at > self.collected_at:
            message = "Evidence availability cannot follow actual collection"
            raise ValueError(message)
        return self


class SourceEvidence(EvidenceTiming):
    """Captured source and bounded assertion, scoped to one company.

    Restricted attachments have no public URL. Review state describes verification
    of the asserted source fact, never probability of company success.
    """

    evidence_id: Identifier
    company_id: Identifier
    provider: Identifier
    url: PublicUrl | None
    access: Literal["public", "restricted"]
    raw_artifact: ArtifactReference
    locator: Text
    assertion: Text
    published_at: UtcInstant | None
    availability_basis: Literal["dated_publication", "first_observed"]
    kind: Literal[
        "registry_record", "company_reported", "platform_observed", "user_supplied"
    ]
    review_state: Literal["unreviewed", "verified", "disputed"]

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        """Return evidence; reject contradictory public access or availability."""
        if (self.access == "public") != (self.url is not None):
            message = "Only public evidence requires a public source URL"
            raise ValueError(message)
        if self.published_at is not None and self.published_at > self.collected_at:
            message = "Publication cannot follow collection"
            raise ValueError(message)
        expected = (
            self.published_at
            if self.availability_basis == "dated_publication"
            else self.collected_at
        )
        if expected is None or self.available_at != expected:
            message = "Evidence availability must match its declared basis"
            raise ValueError(message)
        return self


class CompanyMetricObservation(EvidenceTiming):
    """One selected metric vintage; missing/conflicting values cannot become zero."""

    observation_id: Identifier
    company_id: Identifier
    metric_id: Identifier
    window: TimeWindow | None
    measured_at: UtcInstant | None
    value: MetricValue | None
    state: ObservationState
    reason: Text | None
    evidence_ids: tuple[Identifier, ...]
    supersedes_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        """Return observation; reject invalid values, periods, or self-revisions."""
        if (self.window is None) == (self.measured_at is None):
            message = "Metric requires exactly one window or point-in-time"
            raise ValueError(message)
        if self.measurement_end > self.available_at:
            message = "Metric measurement cannot follow availability"
            raise ValueError(message)
        if (self.state == "observed") != (self.value is not None):
            message = "Only observed metrics have a value"
            raise ValueError(message)
        if self.state == "observed" and not self.evidence_ids:
            message = "Observed metrics require source evidence"
            raise ValueError(message)
        if self.state != "observed" and not self.reason:
            message = "Missing/inapplicable/conflicting metrics require reasons"
            raise ValueError(message)
        if self.supersedes_id == self.observation_id:
            message = "An observation cannot supersede itself"
            raise ValueError(message)
        return self

    @property
    def measurement_end(self) -> UtcInstant:
        """Return the measurement boundary used for frozen freshness checks."""
        if self.window is not None:
            return self.window.end
        if self.measured_at is None:
            message = "Metric has no measurement boundary"
            raise ValueError(message)
        return self.measured_at


class CompanyEvent(EvidenceTiming):
    """Dated reported occurrence; company shutdown differs from product retirement."""

    event_id: Identifier
    company_id: Identifier
    kind: Literal[
        "funding",
        "acquisition",
        "company_shutdown",
        "product_retirement",
        "release",
        "ownership_change",
    ]
    stage: Literal["announced", "completed", "reported"]
    occurred_on: date | None
    date_precision: Literal["day", "unknown"]
    description: Text
    evidence_ids: EvidenceIds
    supersedes_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        """Return event; reject invented precision or a future completed event."""
        if (self.date_precision == "day") != (self.occurred_on is not None):
            message = "Event date and date precision disagree"
            raise ValueError(message)
        if (
            self.stage != "announced"
            and self.occurred_on is not None
            and self.occurred_on > self.available_at.date()
        ):
            message = "A reported/completed event cannot occur after availability"
            raise ValueError(message)
        if self.supersedes_id == self.event_id:
            message = "An event cannot supersede itself"
            raise ValueError(message)
        return self


class CompanyCoverage(Contract):
    """Frozen metric coverage by family; applicability excludes irrelevant metrics."""

    company_id: Identifier
    family: MetricFamily
    applicable_metric_ids: tuple[Identifier, ...]
    observed_metric_ids: tuple[Identifier, ...]
    missing_metric_ids: tuple[Identifier, ...]
    conflicting_metric_ids: tuple[Identifier, ...]
    inapplicable_metric_ids: tuple[Identifier, ...]
    stale_metric_ids: tuple[Identifier, ...]


class FamilyResolution(Contract):
    """Effective family at a cutoff, or explicit unresolved/conflicting ownership."""

    company_id: Identifier
    assessment_at: UtcInstant
    family_id: Identifier | None
    reason_codes: tuple[Identifier, ...]
    relationship_ids: tuple[Identifier, ...]


class CompanySnapshotMetadata(Contract):
    """Immutable source publication identity and actual production provenance."""

    schema_version: Literal["company-source-v1"] = "company-source-v1"
    snapshot_id: Identifier
    as_of: UtcInstant
    recorded_at: UtcInstant
    cohort_version: Identifier
    code_revision: Identifier
    configuration_sha256: Sha256
    synthetic: StrictBool
    mode: Literal["contemporary", "historical_reconstruction", "prospective"]
    limitations: tuple[Text, ...]

    @model_validator(mode="after")
    def validate_snapshot_time(self) -> Self:
        """Return metadata; reject evidence cutoffs after actual publication."""
        if self.as_of > self.recorded_at:
            message = "Source cutoff cannot follow publication"
            raise ValueError(message)
        return self


class CompanySourceSnapshot(CompanySnapshotMetadata):
    """Normalized frozen tables; cross-table validation rejects misattribution."""

    companies: tuple[CompanyProfile, ...]
    relationships: tuple[CompanyRelationship, ...]
    definitions: tuple[MetricDefinition, ...]
    evidence: tuple[SourceEvidence, ...]
    metrics: tuple[CompanyMetricObservation, ...]
    events: tuple[CompanyEvent, ...]

    @model_validator(mode="after")
    def validate_tables(self) -> Self:
        """Return snapshot; raise ValueError for inconsistent identities/times/types."""
        from oxhack2026.catalog.company_validation import validate_company_snapshot

        validate_company_snapshot(self)
        return self

    def coverage(self, company_id: str) -> tuple[CompanyCoverage, ...]:
        """Return immutable-cutoff coverage; raise KeyError for an unknown company."""
        if company_id not in {row.company_id for row in self.companies}:
            raise KeyError(company_id)
        definitions = {row.metric_id: row for row in self.definitions}
        rows = [row for row in self.metrics if row.company_id == company_id]
        result = []
        for family in ("traction", "commercial", "execution", "market_financing"):
            group = [row for row in rows if definitions[row.metric_id].family == family]
            groups = {
                state: tuple(
                    sorted(row.metric_id for row in group if row.state == state)
                )
                for state in ("observed", "missing", "conflicting", "not_applicable")
            }
            result.append(
                CompanyCoverage.model_validate(
                    {
                        "company_id": company_id,
                        "family": family,
                        "applicable_metric_ids": tuple(
                            sorted(
                                row.metric_id
                                for row in group
                                if row.state != "not_applicable"
                            )
                        ),
                        "observed_metric_ids": groups["observed"],
                        "missing_metric_ids": groups["missing"],
                        "conflicting_metric_ids": groups["conflicting"],
                        "inapplicable_metric_ids": groups["not_applicable"],
                        "stale_metric_ids": tuple(
                            sorted(
                                row.metric_id
                                for row in group
                                if row.state == "observed"
                                and self.as_of - row.measurement_end
                                > timedelta(
                                    days=definitions[row.metric_id].maximum_age_days
                                )
                            )
                        ),
                    }
                )
            )
        return tuple(result)
