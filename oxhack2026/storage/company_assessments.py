"""Immutable C2 company assessments bound to verified C1 source publications."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import StrictBool, TypeAdapter

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.catalog.schemas import Contract, Identifier, UtcInstant
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import LocalCompanyStore, resolve_family
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock
from oxhack2026.storage.publication import PublicationIndex


class CompanyAssessmentPublication(Contract):
    """Public-safe batch metadata; recorded_at is the latest model recording time."""

    schema_version: Literal["company-assessment-publication-v1"] = (
        "company-assessment-publication-v1"
    )
    publication_id: Identifier
    source_snapshot_id: Identifier
    as_of: UtcInstant
    recorded_at: UtcInstant
    policy_version: Identifier
    synthetic: StrictBool
    company_ids: tuple[Identifier, ...]


class CompanyAssessmentManifest(CompanyAssessmentPublication):
    """Hash-pinned assessment array and the exact source manifest it consumed."""

    source_manifest: ArtifactReference
    assessments: ArtifactReference


class CompanyAssessmentReader(Protocol):
    """Read published assessments without model execution or source refresh.

    Unknown versions/companies raise KeyError; corrupt/incompatible artifacts raise
    ValueError. Concrete storage may additionally raise OSError.
    """

    def publications(self) -> tuple[CompanyAssessmentPublication, ...]:
        """Enumerate verified batches with public-safe metadata."""
        ...

    def manifest(self, publication_id: str) -> CompanyAssessmentManifest:
        """Read the exact publication manifest, without selecting a replacement."""
        ...

    def assessments(self, publication_id: str) -> tuple[CompanyAssessment, ...]:
        """Read all assessments bound to this source publication."""
        ...

    def company(self, publication_id: str, company_id: str) -> CompanyAssessment:
        """Read one company assessment within an exact publication."""
        ...


def _validate_statement_links(
    source: CompanySourceSnapshot, assessment: CompanyAssessment
) -> None:
    evidence = {
        row.evidence_id: row
        for row in source.evidence
        if row.company_id == assessment.company_id
    }
    metrics = {
        row.observation_id: row
        for row in source.metrics
        if row.company_id == assessment.company_id
    }
    events = {
        row.event_id: row
        for row in source.events
        if row.company_id == assessment.company_id
    }
    definitions = {row.metric_id for row in source.definitions}
    for statement in assessment.statements:
        if (
            not set(statement.evidence_ids) <= evidence.keys()
            or not set(statement.metric_observation_ids) <= metrics.keys()
            or not set(statement.event_ids) <= events.keys()
            or not set(statement.missing_metric_ids) <= definitions
        ):
            message = (
                "Assessment statement has unknown or cross-company source references"
            )
            raise ValueError(message)
        support = {
            key
            for observation_id in statement.metric_observation_ids
            for key in metrics[observation_id].evidence_ids
        } | {
            key
            for event_id in statement.event_ids
            for key in events[event_id].evidence_ids
        }
        if not support <= set(statement.evidence_ids):
            message = "Assessment statement omits evidence supporting referenced facts"
            raise ValueError(message)
        if any(
            evidence[key].available_at > assessment.as_of
            for key in statement.evidence_ids
        ):
            message = "Assessment statement uses evidence after its cutoff"
            raise ValueError(message)


def validate_company_assessments(
    source: CompanySourceSnapshot, assessments: tuple[CompanyAssessment, ...]
) -> None:
    """Validate C2 identity, lineage, timing and references against frozen C1 facts.

    Args:
        source: Fully validated exact source snapshot, with actual evidence dates.
        assessments: One C2 record per source company, all at the source cutoff.
    Returns:
        None when the complete publication is compatible.
    Raises:
        ValueError: For missing/duplicate companies, wrong lineage, time or support.
    """
    companies = {row.company_id for row in source.companies}
    if (
        len(assessments) != len(companies)
        or {row.company_id for row in assessments} != companies
        or len({row.assessment_id for row in assessments}) != len(assessments)
    ):
        message = (
            "Publication requires one uniquely identified assessment per source company"
        )
        raise ValueError(message)
    if len({row.policy_version for row in assessments}) != 1:
        message = "Assessment publication cannot mix interpretation policies"
        raise ValueError(message)
    for assessment in assessments:
        if (
            assessment.source_snapshot_id != source.snapshot_id
            or assessment.synthetic != source.synthetic
            or assessment.as_of != source.as_of
        ):
            message = "Assessment source identity, cutoff or synthetic status disagrees"
            raise ValueError(message)
        if assessment.first_recorded_at < source.recorded_at:
            message = "Assessment cannot be recorded before its source publication"
            raise ValueError(message)
        if assessment.mode == "prospective" and source.mode != "prospective":
            message = "Prospective assessments require prospective source provenance"
            raise ValueError(message)
        family = resolve_family(source, assessment.company_id, assessment.as_of)
        if assessment.family_id != family.family_id or not set(
            family.reason_codes
        ) <= set(assessment.family_reason_codes):
            message = "Assessment family disagrees with dated source ownership evidence"
            raise ValueError(message)
        _validate_statement_links(source, assessment)


def _public_metadata(
    manifest: CompanyAssessmentManifest,
) -> CompanyAssessmentPublication:
    return CompanyAssessmentPublication.model_validate(
        {
            key: getattr(manifest, key)
            for key in CompanyAssessmentPublication.model_fields
        }
    )


@dataclass(frozen=True)
class LocalCompanyAssessmentStore:
    """Filesystem C2 publisher/reader sharing the source root's artifact objects."""

    root: Path

    @property
    def sources(self) -> LocalCompanyStore:
        """Return the exact source reader without accessing storage."""
        return LocalCompanyStore(self.root)

    def index(self) -> PublicationIndex:
        """Read the bounded assessment index; absent index means no publications."""
        try:
            with (self.root / "company-assessments.json").open("rb") as stream:
                content = stream.read(8 * 1024 * 1024 + 1)
        except FileNotFoundError:
            return PublicationIndex()
        if len(content) > 8 * 1024 * 1024:
            message = "Assessment publication index exceeds size limit"
            raise ValueError(message)
        index = PublicationIndex.model_validate_json(content)
        if index.current is not None and index.current not in index.versions:
            message = "Assessment index points to unknown publication"
            raise ValueError(message)
        return index

    def manifest(self, publication_id: str) -> CompanyAssessmentManifest:
        """Read exact metadata; unknown IDs and corrupt bytes propagate as errors."""
        reference = self.index().versions[publication_id]
        manifest = CompanyAssessmentManifest.model_validate_json(
            self.sources.artifacts.read(reference)
        )
        if manifest.publication_id != publication_id:
            message = "Assessment manifest disagrees with its publication identifier"
            raise ValueError(message)
        return manifest

    def _load(
        self, manifest: CompanyAssessmentManifest
    ) -> tuple[CompanyAssessment, ...]:
        source_reference = self.sources.index().versions[manifest.source_snapshot_id]
        if source_reference != manifest.source_manifest:
            message = "Assessment source manifest differs from its pinned publication"
            raise ValueError(message)
        source = self.sources.snapshot(manifest.source_snapshot_id)
        assessments = TypeAdapter(tuple[CompanyAssessment, ...]).validate_json(
            self.sources.artifacts.read(manifest.assessments)
        )
        validate_company_assessments(source, assessments)
        if (
            manifest.company_ids != tuple(sorted(row.company_id for row in assessments))
            or manifest.as_of != source.as_of
            or manifest.synthetic != source.synthetic
            or manifest.recorded_at != max(row.first_recorded_at for row in assessments)
            or manifest.policy_version != assessments[0].policy_version
        ):
            message = "Assessment manifest metadata disagrees with its records"
            raise ValueError(message)
        return assessments

    def assessments(self, publication_id: str) -> tuple[CompanyAssessment, ...]:
        """Read validated assessments and raw source lineage for an exact batch."""
        return self._load(self.manifest(publication_id))

    def company(self, publication_id: str, company_id: str) -> CompanyAssessment:
        """Read one assessment; absent company/publication raises KeyError."""
        return {row.company_id: row for row in self.assessments(publication_id)}[
            company_id
        ]

    def publications(self) -> tuple[CompanyAssessmentPublication, ...]:
        """Enumerate verified batches, stripping internal artifact references."""
        result = []
        for key in sorted(self.index().versions):
            manifest = self.manifest(key)
            self._load(manifest)
            result.append(_public_metadata(manifest))
        return tuple(result)

    def publish(
        self,
        publication_id: str,
        assessments: tuple[CompanyAssessment, ...],
        expected_current: str | None,
    ) -> CompanyAssessmentManifest:
        """Validate source-bound model records and atomically publish their batch.

        Args:
            publication_id: Safe immutable batch identity.
            assessments: Complete source-company set under one assessment policy.
            expected_current: Expected active batch ID, or None for empty storage.
        Returns:
            Hash-pinned publication manifest, also for identical repeated calls.
        Raises:
            ValueError: For incompatible facts, immutable ID conflicts or lost CAS.
            KeyError: For an unknown source publication.
            OSError: For storage failures; prior versions remain accessible.
        """
        assessments = tuple(
            CompanyAssessment.model_validate_json(row.model_dump_json())
            for row in assessments
        )
        if not assessments:
            message = "Cannot publish an empty company assessment set"
            raise ValueError(message)
        source_id = assessments[0].source_snapshot_id
        source = self.sources.snapshot(source_id)
        validate_company_assessments(source, assessments)
        ordered = tuple(sorted(assessments, key=lambda row: row.company_id))
        content = TypeAdapter(tuple[CompanyAssessment, ...]).dump_json(ordered)
        manifest = CompanyAssessmentManifest(
            publication_id=publication_id,
            source_snapshot_id=source_id,
            as_of=source.as_of,
            recorded_at=max(row.first_recorded_at for row in ordered),
            policy_version=ordered[0].policy_version,
            synthetic=source.synthetic,
            company_ids=tuple(row.company_id for row in ordered),
            source_manifest=self.sources.index().versions[source_id],
            assessments=self.sources.artifacts.write(content, "application/json"),
        )
        self._load(manifest)
        reference = self.sources.artifacts.write(
            manifest.model_dump_json().encode(), "application/json"
        )
        with file_lock(self.root / ".company-assessments.lock"):
            index = self.index()
            old = index.versions.get(publication_id)
            if old is not None and old != reference:
                message = "An immutable assessment publication cannot be replaced"
                raise ValueError(message)
            if index.current == publication_id and old == reference:
                return manifest
            if index.current != expected_current:
                message = "Assessment publication lost its compare-and-swap race"
                raise ValueError(message)
            updated = PublicationIndex(
                current=publication_id,
                versions=index.versions | {publication_id: reference},
            )
            atomic_write(
                self.root / "company-assessments.json",
                updated.model_dump_json().encode(),
            )
        return manifest
