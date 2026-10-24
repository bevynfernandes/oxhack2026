"""Read-only composition of exact company source and assessment publications."""

import logging
from dataclasses import dataclass
from typing import Protocol

from oxhack2026.api import company_schemas as s
from oxhack2026.api.company_mapping import (
    public_coverage,
    public_events,
    public_metrics,
    public_relationships,
)
from oxhack2026.api.repository import RepositoryUnavailable, ResourceNotFound
from oxhack2026.api.schemas import Health
from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import CompanySourceReader, metadata, resolve_family
from oxhack2026.storage.company_assessments import (
    CompanyAssessmentPublication,
    CompanyAssessmentReader,
    validate_company_assessments,
)

logger = logging.getLogger(__name__)


class CompanyRepository(Protocol):
    """Public read port; unknown IDs are 404, unusable publications are 503."""

    def publications(self) -> s.CompanyPublications:
        """Enumerate verified publications with public-safe metadata."""
        ...

    def companies(self, snapshot_id: str) -> s.CompanyList:
        """Read company rows in an exact publication."""
        ...

    def company(self, snapshot_id: str, company_id: str) -> s.CompanyDetail:
        """Read one exact profile without future outcome labels."""
        ...

    def readiness(self) -> Health:
        """Require at least one usable company assessment publication."""
        ...


@dataclass(frozen=True)
class _Publication:
    source: CompanySourceSnapshot
    assessment: CompanyAssessmentPublication
    assessments: dict[str, CompanyAssessment]

    @property
    def public(self) -> s.CompanyPublication:
        return s.CompanyPublication(
            source=metadata(self.source),
            assessment=self.assessment,
            company_count=len(self.source.companies),
        )


def _require_public_claims(
    source: CompanySourceSnapshot, assessments: tuple[CompanyAssessment, ...]
) -> None:
    public = {row.evidence_id for row in source.evidence if row.access == "public"}
    if any(not set(row.evidence_ids) <= public for row in source.companies):
        message = "Public company identity requires public supporting evidence"
        raise ValueError(message)
    metrics = {row.observation_id: row for row in source.metrics}
    events = {row.event_id: row for row in source.events}
    for assessment in assessments:
        for statement in assessment.statements:
            if statement.role == "evidence_gap":
                continue
            support = set(statement.evidence_ids)
            for key in statement.metric_observation_ids:
                support.update(metrics[key].evidence_ids)
            for key in statement.event_ids:
                support.update(events[key].evidence_ids)
            if not support <= public:
                message = "Public assessment facts cannot expose restricted sources"
                raise ValueError(message)


@dataclass(frozen=True)
class PublishedCompanyRepository:
    """Project verified C1/C2 publications without persistence or numerical policy.

    Args:
        sources: Lifecycle-managed C1 exact-version reader.
        assessments: Lifecycle-managed published C2 reader.
        publication_ids: Explicit canonical assessment publication selection.

    Construction performs no I/O. Each read verifies the selected immutable bytes
    through the owners' readers; no vendor collection or process cache is used.
    """

    sources: CompanySourceReader
    assessments: CompanyAssessmentReader
    publication_ids: tuple[str, ...]

    def _load(self, snapshot_id: str) -> _Publication:
        try:
            if len(self.publication_ids) != len(set(self.publication_ids)):
                raise RepositoryUnavailable
            if snapshot_id not in self.publication_ids:
                raise ResourceNotFound
            manifest = self.assessments.manifest(snapshot_id)
            publication = CompanyAssessmentPublication.model_validate(
                {
                    key: getattr(manifest, key)
                    for key in CompanyAssessmentPublication.model_fields
                }
            )
            source = self.sources.snapshot(publication.source_snapshot_id)
            if (
                publication.publication_id != snapshot_id
                or source.snapshot_id != publication.source_snapshot_id
            ):
                raise RepositoryUnavailable
            source = CompanySourceSnapshot.model_validate_json(source.model_dump_json())
            assessments = tuple(
                CompanyAssessment.model_validate_json(row.model_dump_json())
                for row in self.assessments.assessments(snapshot_id)
            )
            validate_company_assessments(source, assessments)
            if (
                publication.as_of != source.as_of
                or publication.synthetic != source.synthetic
                or set(publication.company_ids)
                != {row.company_id for row in assessments}
                or len(publication.company_ids) != len(assessments)
                or {row.policy_version for row in assessments}
                != {publication.policy_version}
                or publication.recorded_at
                != max(row.first_recorded_at for row in assessments)
            ):
                raise RepositoryUnavailable
            _require_public_claims(source, assessments)
            return _Publication(
                source, publication, {row.company_id: row for row in assessments}
            )
        except (KeyError, OSError, ValueError) as error:
            logger.error(  # noqa: TRY400 - upstream error details may contain secrets
                "Company publication failed integrity or storage checks"
            )
            raise RepositoryUnavailable from error

    def publications(self) -> s.CompanyPublications:
        """Return verified publications; raise RepositoryUnavailable on broken data."""
        try:
            ids = self.publication_ids
            if len(ids) != len(set(ids)):
                raise RepositoryUnavailable
            return s.CompanyPublications(
                items=tuple(self._load(key).public for key in sorted(ids))
            )
        except (KeyError, OSError, ValueError) as error:
            logger.error(  # noqa: TRY400 - upstream error details may contain secrets
                "Company publication enumeration failed"
            )
            raise RepositoryUnavailable from error

    def readiness(self) -> Health:
        """Return ready only with verified published company assessments."""
        if not self.publications().items:
            raise RepositoryUnavailable
        return Health(status="ready")

    def companies(self, snapshot_id: str) -> s.CompanyList:
        """Return name-ordered rows; propagate unknown/unavailable errors."""
        publication = self._load(snapshot_id)
        rows = []
        for company in sorted(
            publication.source.companies,
            key=lambda row: (row.display_name.casefold(), row.company_id),
        ):
            assessment = publication.assessments[company.company_id]
            signal = next(
                (
                    row.text
                    for row in assessment.statements
                    if row.role == "observation"
                ),
                None,
            )
            risk = next(
                (row.text for row in assessment.statements if row.role == "risk"),
                next(
                    (
                        row.text
                        for row in assessment.statements
                        if row.role == "evidence_gap"
                    ),
                    None,
                ),
            )
            rows.append(
                s.CompanySummary(
                    company=company,
                    assessment_id=assessment.assessment_id,
                    outcomes=assessment.outcomes,
                    supporting_signal=signal,
                    main_risk=risk,
                    coverage=public_coverage(publication.source, company.company_id),
                )
            )
        return s.CompanyList(publication=publication.public, items=tuple(rows))

    def company(self, snapshot_id: str, company_id: str) -> s.CompanyDetail:
        """Read an exact profile; raise ResourceNotFound for unknown companies."""
        publication = self._load(snapshot_id)
        source = publication.source
        companies = {row.company_id: row for row in source.companies}
        if company_id not in companies:
            raise ResourceNotFound
        return s.CompanyDetail(
            publication=publication.public,
            company=companies[company_id],
            assessment=publication.assessments[company_id],
            family=resolve_family(source, company_id, source.as_of, public_only=True),
            definitions=source.definitions,
            metrics=public_metrics(source, company_id),
            events=public_events(source, company_id),
            relationships=tuple(
                row
                for row in public_relationships(source)
                if row.company_id == company_id
            ),
            coverage=public_coverage(source, company_id),
            evidence=tuple(
                s.public_source(row)
                for row in source.evidence
                if row.company_id == company_id
            ),
        )
