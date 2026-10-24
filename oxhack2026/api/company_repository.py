"""Read-only composition of exact company source and assessment publications."""

import logging
from dataclasses import dataclass
from typing import Protocol

from oxhack2026.api import company_schemas as s
from oxhack2026.api.repository import RepositoryUnavailable, ResourceNotFound
from oxhack2026.api.schemas import Health
from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import CompanySourceReader, metadata, resolve_family

logger = logging.getLogger(__name__)


class CompanyAssessmentReader(Protocol):
    """Published C2 reads; unknown publications raise KeyError, corruption ValueError.

    Implementations may raise OSError. Enumeration includes only source IDs with
    published assessments, without inventing an assessment from source activity.
    """

    def snapshot_ids(self) -> tuple[str, ...]:
        """Return exact source snapshot IDs with published assessment sets."""
        ...

    def assessments(self, snapshot_id: str) -> tuple[CompanyAssessment, ...]:
        """Return the complete immutable assessment set for an exact source ID."""
        ...


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
    assessments: dict[str, CompanyAssessment]

    @property
    def public(self) -> s.CompanyPublication:
        return s.CompanyPublication(
            source=metadata(self.source), company_count=len(self.source.companies)
        )


def _validate_assessments(
    source: CompanySourceSnapshot, assessments: tuple[CompanyAssessment, ...]
) -> dict[str, CompanyAssessment]:
    rows = {row.company_id: row for row in assessments}
    if len(rows) != len(assessments) or rows.keys() != {
        company.company_id for company in source.companies
    }:
        message = "Published assessments must cover each source company exactly once"
        raise ValueError(message)
    evidence = {row.evidence_id: row for row in source.evidence}
    metrics = {row.observation_id: row for row in source.metrics}
    events = {row.event_id: row for row in source.events}
    missing = {
        (row.company_id, row.metric_id)
        for row in source.metrics
        if row.state in {"missing", "conflicting"}
    }
    for assessment in rows.values():
        family = resolve_family(source, assessment.company_id, source.as_of)
        if (
            assessment.source_snapshot_id != source.snapshot_id
            or assessment.as_of != source.as_of
            or assessment.synthetic != source.synthetic
            or assessment.first_recorded_at < source.recorded_at
            or assessment.family_id != family.family_id
            or (
                assessment.family_id is None
                and set(assessment.family_reason_codes) != set(family.reason_codes)
            )
            or (assessment.mode == "prospective" and source.mode != "prospective")
        ):
            message = "Assessment and source publication identity/timing disagree"
            raise ValueError(message)
        for statement in assessment.statements:
            for keys, table in (
                (statement.evidence_ids, evidence),
                (statement.metric_observation_ids, metrics),
                (statement.event_ids, events),
            ):
                if any(
                    key not in table or table[key].company_id != assessment.company_id
                    for key in keys
                ):
                    message = "Assessment cites unknown or cross-company source facts"
                    raise ValueError(message)
            if any(
                (assessment.company_id, key) not in missing
                for key in statement.missing_metric_ids
            ):
                message = "Assessment gap does not match missing source observations"
                raise ValueError(message)
            cited = {
                key
                for observation_id in statement.metric_observation_ids
                for key in metrics[observation_id].evidence_ids
            } | {
                key
                for event_id in statement.event_ids
                for key in events[event_id].evidence_ids
            }
            if not cited <= set(statement.evidence_ids):
                message = "Assessment omits evidence supporting its cited facts"
                raise ValueError(message)
    return rows


@dataclass(frozen=True)
class PublishedCompanyRepository:
    """Project verified C1/C2 publications without persistence or numerical policy.

    Args:
        sources: Lifecycle-managed C1 exact-version reader.
        assessments: Lifecycle-managed published C2 reader.

    Construction performs no I/O. Each read verifies the selected immutable bytes
    through the owners' readers; no vendor collection or process cache is used.
    """

    sources: CompanySourceReader
    assessments: CompanyAssessmentReader

    def _load(self, snapshot_id: str) -> _Publication:
        try:
            if snapshot_id not in self.assessments.snapshot_ids():
                raise ResourceNotFound
            source = self.sources.snapshot(snapshot_id)
            if source.snapshot_id != snapshot_id:
                raise RepositoryUnavailable
            source = CompanySourceSnapshot.model_validate_json(source.model_dump_json())
            assessments = tuple(
                CompanyAssessment.model_validate_json(row.model_dump_json())
                for row in self.assessments.assessments(snapshot_id)
            )
            return _Publication(source, _validate_assessments(source, assessments))
        except (KeyError, OSError, ValueError) as error:
            logger.error(  # noqa: TRY400 - upstream error details may contain secrets
                "Company publication failed integrity or storage checks"
            )
            raise RepositoryUnavailable from error

    def publications(self) -> s.CompanyPublications:
        """Return verified publications; raise RepositoryUnavailable on broken data."""
        try:
            ids = self.assessments.snapshot_ids()
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
                    coverage=publication.source.coverage(company.company_id),
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
            family=resolve_family(source, company_id, source.as_of),
            definitions=source.definitions,
            metrics=tuple(
                row for row in source.metrics if row.company_id == company_id
            ),
            events=tuple(row for row in source.events if row.company_id == company_id),
            relationships=tuple(
                row for row in source.relationships if row.company_id == company_id
            ),
            coverage=source.coverage(company_id),
            evidence=tuple(
                s.public_source(row)
                for row in source.evidence
                if row.company_id == company_id
            ),
        )
