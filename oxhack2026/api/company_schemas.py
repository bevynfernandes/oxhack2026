"""Public company projections reuse source facts and model-owned assessments."""

from typing import Literal, Self

from pydantic import Field, model_validator

from oxhack2026.api.schemas import DTO, Identifier, PublicURL, UTCDateTime
from oxhack2026.catalog.company import (
    CompanyCoverage,
    CompanyEvent,
    CompanyMetricObservation,
    CompanyProfile,
    CompanyRelationship,
    CompanySnapshotMetadata,
    FamilyResolution,
    MetricDefinition,
    MetricValue,
    ObservationState,
    SourceEvidence,
)
from oxhack2026.catalog.schemas import TimeWindow
from oxhack2026.models.company_assessments import (
    CompanyAssessment,
    CompanyOutcomeAssessment,
)
from oxhack2026.models.dimension_serving import CompanyDimensionModels
from oxhack2026.models.startup_outlook import StartupOutlook
from oxhack2026.storage.company_assessments import CompanyAssessmentPublication


class CompanySource(DTO):
    """Public provenance without raw locations, locators or restricted contents."""

    evidence_id: Identifier
    provider: str
    access: Literal["public", "restricted"]
    url: PublicURL | None
    assertion: str | None
    published_at: UTCDateTime | None
    available_at: UTCDateTime
    collected_at: UTCDateTime
    availability_basis: Literal["dated_publication", "first_observed"]
    kind: Literal[
        "registry_record", "company_reported", "platform_observed", "user_supplied"
    ]
    review_state: Literal["unreviewed", "verified", "disputed"]


def public_source(source: SourceEvidence) -> CompanySource:
    """Project provenance, redacting restricted assertions and attachment details.

    Args:
        source: Source record from the verified publication.
    Returns:
        Public dates/review state with contents only for public evidence.
    Raises:
        ValueError: Public fields do not satisfy the response contract.
    """
    return CompanySource(
        evidence_id=source.evidence_id,
        provider=source.provider,
        access=source.access,
        url=source.url if source.access == "public" else None,
        assertion=source.assertion if source.access == "public" else None,
        published_at=source.published_at,
        available_at=source.available_at,
        collected_at=source.collected_at,
        availability_basis=source.availability_basis,
        kind=source.kind,
        review_state=source.review_state,
    )


class CompanyPublication(DTO):
    """An exact source snapshot with a complete published assessment set."""

    schema_version: Literal["company-api-v1"] = "company-api-v1"
    source: CompanySnapshotMetadata
    assessment: CompanyAssessmentPublication
    company_count: int


class CompanyMetric(DTO):
    """Source measurement with an explicit restricted state for withheld values."""

    observation_id: Identifier
    company_id: Identifier
    metric_id: Identifier
    window: TimeWindow | None
    measured_at: UTCDateTime | None
    value: MetricValue | None
    state: ObservationState | Literal["restricted"]
    reason: str | None
    evidence_ids: tuple[Identifier, ...]
    available_at: UTCDateTime
    collected_at: UTCDateTime

    @model_validator(mode="after")
    def validate_public_measurement(self) -> Self:
        """Return valid C1 measurement metadata; reject private value exposure."""
        payload = self.model_dump()
        if self.state == "restricted":
            if self.value is not None or self.evidence_ids:
                message = "Restricted measurements cannot expose values or evidence IDs"
                raise ValueError(message)
            payload["state"] = "missing"
        CompanyMetricObservation.model_validate(payload)
        return self


class PublicCompanyCoverage(CompanyCoverage):
    """Coverage counts public observations and withheld metrics separately."""

    restricted_metric_ids: tuple[Identifier, ...] = ()


class CompanyPublications(DTO):
    """Explicit publication choices; an empty list never loads examples."""

    items: tuple[CompanyPublication, ...]


class CompanySummary(DTO):
    """Company context, separate outcomes and published evidence for a table row."""

    company: CompanyProfile
    assessment_id: Identifier
    outcomes: tuple[CompanyOutcomeAssessment, ...]
    supporting_signal: str | None
    main_risk: str | None
    coverage: tuple[PublicCompanyCoverage, ...]


class CompanyList(DTO):
    """Name-ordered companies in one immutable publication."""

    publication: CompanyPublication
    items: tuple[CompanySummary, ...]


class CompanyDetail(DTO):
    """Pre-outcome profile; raw source paths and future labels are absent."""

    publication: CompanyPublication
    company: CompanyProfile
    assessment: CompanyAssessment
    family: FamilyResolution
    definitions: tuple[MetricDefinition, ...]
    metrics: tuple[CompanyMetric, ...]
    events: tuple[CompanyEvent, ...]
    relationships: tuple[CompanyRelationship, ...]
    coverage: tuple[PublicCompanyCoverage, ...]
    evidence: tuple[CompanySource, ...]
    outlook: StartupOutlook | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    dimension_models: CompanyDimensionModels | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
