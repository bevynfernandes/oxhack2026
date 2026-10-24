"""Public company projections reuse source facts and model-owned assessments."""

from typing import Literal

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
    SourceEvidence,
)
from oxhack2026.models.company_assessments import (
    CompanyAssessment,
    CompanyOutcomeAssessment,
)


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
    company_count: int


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
    coverage: tuple[CompanyCoverage, ...]


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
    metrics: tuple[CompanyMetricObservation, ...]
    events: tuple[CompanyEvent, ...]
    relationships: tuple[CompanyRelationship, ...]
    coverage: tuple[CompanyCoverage, ...]
    evidence: tuple[CompanySource, ...]
