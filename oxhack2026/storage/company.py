"""Validated company source publication and exact-version filesystem reads."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from oxhack2026.catalog.company import (
    CompanyCoverage,
    CompanyEvent,
    CompanyMetricObservation,
    CompanyProfile,
    CompanyRelationship,
    CompanySnapshotMetadata,
    CompanySourceSnapshot,
    FamilyResolution,
    MetricDefinition,
    SourceEvidence,
)
from oxhack2026.catalog.schemas import UtcInstant
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock
from oxhack2026.storage.publication import PublicationIndex


class CompanySourceManifest(CompanySnapshotMetadata):
    """Hash-pinned normalized source tables; no future labels or assessment policy."""

    content: ArtifactReference


class CompanySourceReader(Protocol):
    """No vendor calls; unknown IDs raise KeyError, corrupt bytes raise ValueError.

    Concrete storage can additionally raise OSError. All parameters identify exact
    immutable versions; enumeration returns public-safe metadata only.
    """

    def snapshots(self) -> tuple[CompanySnapshotMetadata, ...]:
        """Enumerate verified published source snapshot metadata."""
        ...

    def manifest(self, snapshot_id: str) -> CompanySourceManifest:
        """Return the manifest for an exact snapshot identifier."""
        ...

    def snapshot(self, snapshot_id: str) -> CompanySourceSnapshot:
        """Return fully validated source tables for an exact publication."""
        ...

    def companies(self, snapshot_id: str) -> tuple[CompanyProfile, ...]:
        """Return company identities in an exact publication."""
        ...

    def company(self, snapshot_id: str, company_id: str) -> CompanyProfile:
        """Resolve one company; do not select a replacement for unknown IDs."""
        ...

    def definitions(self, snapshot_id: str) -> tuple[MetricDefinition, ...]:
        """Return the exact versioned definitions consumed by metric rows."""
        ...

    def metrics(
        self, snapshot_id: str, company_id: str
    ) -> tuple[CompanyMetricObservation, ...]:
        """Return selected company metrics, including missing/inapplicable rows."""
        ...

    def events(self, snapshot_id: str, company_id: str) -> tuple[CompanyEvent, ...]:
        """Return dated company events with announcement/completion distinctions."""
        ...

    def evidence(self, snapshot_id: str, evidence_id: str) -> SourceEvidence:
        """Resolve source provenance; public projections must strip restricted data."""
        ...

    def relationships(
        self, snapshot_id: str, company_id: str
    ) -> tuple[CompanyRelationship, ...]:
        """Return effective ownership/product mappings with their evidence IDs."""
        ...

    def coverage(
        self, snapshot_id: str, company_id: str
    ) -> tuple[CompanyCoverage, ...]:
        """Return applicability, missingness and freshness at the frozen cutoff."""
        ...

    def family_at(
        self, snapshot_id: str, company_id: str, assessment_at: UtcInstant
    ) -> FamilyResolution:
        """Resolve evidenced family membership without applying later ownership."""
        ...


def metadata(snapshot: CompanySnapshotMetadata) -> CompanySnapshotMetadata:
    """Return public-safe metadata, excluding source tables/internal references."""
    return CompanySnapshotMetadata.model_validate(
        {key: getattr(snapshot, key) for key in CompanySnapshotMetadata.model_fields}
    )


def resolve_family(
    snapshot: CompanySourceSnapshot,
    company_id: str,
    assessment_at: UtcInstant,
    *,
    public_only: bool = False,
) -> FamilyResolution:
    """Resolve dated membership, returning explicit unknown/conflict reasons.

    Args:
        snapshot: Validated immutable source tables.
        company_id: Exact company in the snapshot.
        assessment_at: UTC cutoff no later than the snapshot cutoff.
        public_only: Exclude restricted evidence for public assessments/projection.
    Returns:
        Effective family or an unresolved result with reason codes.
    Raises:
        KeyError: If the company is unknown.
        ValueError: If the cutoff exceeds the snapshot or is not UTC.
    """
    from oxhack2026.catalog.schemas import require_utc

    require_utc(assessment_at)
    if assessment_at > snapshot.as_of:
        message = "Family lookup cannot exceed source snapshot cutoff"
        raise ValueError(message)
    if company_id not in {row.company_id for row in snapshot.companies}:
        raise KeyError(company_id)
    sources = {row.evidence_id: row for row in snapshot.evidence}
    candidates = [
        row
        for row in snapshot.relationships
        if row.company_id == company_id
        and row.subject_kind == "family"
        and row.valid_from <= assessment_at
        and (row.valid_to is None or assessment_at < row.valid_to)
        and all(
            sources[key].available_at <= assessment_at
            and sources[key].review_state == "verified"
            and (not public_only or sources[key].access == "public")
            and (
                snapshot.mode == "historical_reconstruction"
                or sources[key].collected_at <= assessment_at
            )
            for key in row.evidence_ids
        )
    ]
    families = {row.subject_id for row in candidates}
    return FamilyResolution(
        company_id=company_id,
        assessment_at=assessment_at,
        family_id=next(iter(families)) if len(families) == 1 else None,
        reason_codes=()
        if len(families) == 1
        else ("conflicting_family_evidence",)
        if families
        else ("family_not_established_at_cutoff",),
        relationship_ids=tuple(sorted(row.relationship_id for row in candidates)),
    )


@dataclass(frozen=True)
class LocalCompanyStore:
    """Immutable local source publications; construction performs no I/O.

    Reads verify hashes/schema/raw evidence each time. The small company catalogue
    is intentionally not cached across calls, so corruption is never hidden by a
    stale process cache. API composition may hold an explicitly verified snapshot.
    """

    root: Path

    @property
    def artifacts(self) -> FileArtifactStore:
        """Return the bounded content-addressed artifact adapter for this root."""
        return FileArtifactStore(self.root)

    def index(self) -> PublicationIndex:
        """Read the bounded source index; missing means no published snapshots."""
        path = self.root / "company-snapshots.json"
        try:
            with path.open("rb") as stream:
                content = stream.read(8 * 1024 * 1024 + 1)
        except FileNotFoundError:
            return PublicationIndex()
        if len(content) > 8 * 1024 * 1024:
            message = "Company index exceeds metadata size limit"
            raise ValueError(message)
        result = PublicationIndex.model_validate_json(content)
        if result.current is not None and result.current not in result.versions:
            message = "Company index points to an unknown snapshot"
            raise ValueError(message)
        return result

    def manifest(self, snapshot_id: str) -> CompanySourceManifest:
        """Read exact verified metadata; propagate unknown/integrity/I/O errors."""
        result = CompanySourceManifest.model_validate_json(
            self.artifacts.read(self.index().versions[snapshot_id])
        )
        if result.snapshot_id != snapshot_id:
            message = "Company manifest disagrees with publication identity"
            raise ValueError(message)
        return result

    def _load(self, manifest: CompanySourceManifest) -> CompanySourceSnapshot:
        snapshot = CompanySourceSnapshot.model_validate_json(
            self.artifacts.read(manifest.content)
        )
        if metadata(snapshot) != metadata(manifest):
            message = "Source tables disagree with manifest metadata"
            raise ValueError(message)
        for source in snapshot.evidence:
            self.artifacts.read(source.raw_artifact)
        return snapshot

    def snapshot(self, snapshot_id: str) -> CompanySourceSnapshot:
        """Read exact validated tables/raw evidence; propagate storage errors."""
        return self._load(self.manifest(snapshot_id))

    def publish(
        self, snapshot: CompanySourceSnapshot, expected_current: str | None
    ) -> CompanySourceManifest:
        """Validate raw evidence then atomically publish an immutable source snapshot.

        Args:
            snapshot: Candidate tables referencing source bytes already in this root.
            expected_current: Expected current ID; None for an empty index.
        Returns:
            Hash-pinned source manifest, also for an identical idempotent retry.
        Raises:
            ValueError: For corruption, conflicting IDs or failed compare-and-swap.
            OSError: For filesystem failures; retain/reconcile the existing index.
        """
        snapshot = CompanySourceSnapshot.model_validate_json(snapshot.model_dump_json())
        content = self.artifacts.write(
            snapshot.model_dump_json().encode(), "application/json"
        )
        manifest = CompanySourceManifest(
            **metadata(snapshot).model_dump(), content=content
        )
        self._load(manifest)
        reference = self.artifacts.write(
            manifest.model_dump_json().encode(), "application/json"
        )
        with file_lock(self.root / ".company-publication.lock"):
            index = self.index()
            old = index.versions.get(snapshot.snapshot_id)
            if old is not None and old != reference:
                message = "An immutable company snapshot cannot be replaced"
                raise ValueError(message)
            if index.current == snapshot.snapshot_id and old == reference:
                return manifest
            if index.current != expected_current:
                message = "Company publication lost its compare-and-swap race"
                raise ValueError(message)
            updated = PublicationIndex(
                current=snapshot.snapshot_id,
                versions=index.versions | {snapshot.snapshot_id: reference},
            )
            atomic_write(
                self.root / "company-snapshots.json", updated.model_dump_json().encode()
            )
        return manifest

    def snapshots(self) -> tuple[CompanySnapshotMetadata, ...]:
        """Enumerate exact verified publications; no current-version substitution."""
        return tuple(
            metadata(self.snapshot(key)) for key in sorted(self.index().versions)
        )

    def companies(self, snapshot_id: str) -> tuple[CompanyProfile, ...]:
        """Return immutable company profiles; propagate publication errors."""
        return self.snapshot(snapshot_id).companies

    def company(self, snapshot_id: str, company_id: str) -> CompanyProfile:
        """Resolve one exact company; raise KeyError if absent."""
        return {row.company_id: row for row in self.companies(snapshot_id)}[company_id]

    def definitions(self, snapshot_id: str) -> tuple[MetricDefinition, ...]:
        """Read snapshot-pinned metric definitions; propagate publication errors."""
        return self.snapshot(snapshot_id).definitions

    def _company_snapshot(
        self, snapshot_id: str, company_id: str
    ) -> CompanySourceSnapshot:
        snapshot = self.snapshot(snapshot_id)
        if company_id not in {row.company_id for row in snapshot.companies}:
            raise KeyError(company_id)
        return snapshot

    def metrics(
        self, snapshot_id: str, company_id: str
    ) -> tuple[CompanyMetricObservation, ...]:
        """Read selected metrics; unknown company/publication IDs raise KeyError."""
        return tuple(
            row
            for row in self._company_snapshot(snapshot_id, company_id).metrics
            if row.company_id == company_id
        )

    def events(self, snapshot_id: str, company_id: str) -> tuple[CompanyEvent, ...]:
        """Read dated events; unknown company/publication IDs raise KeyError."""
        return tuple(
            row
            for row in self._company_snapshot(snapshot_id, company_id).events
            if row.company_id == company_id
        )

    def evidence(self, snapshot_id: str, evidence_id: str) -> SourceEvidence:
        """Read source provenance; unknown evidence/publication raises KeyError."""
        return {row.evidence_id: row for row in self.snapshot(snapshot_id).evidence}[
            evidence_id
        ]

    def relationships(
        self, snapshot_id: str, company_id: str
    ) -> tuple[CompanyRelationship, ...]:
        """Read effective mappings; unknown company/publication raises KeyError."""
        return tuple(
            row
            for row in self._company_snapshot(snapshot_id, company_id).relationships
            if row.company_id == company_id
        )

    def coverage(
        self, snapshot_id: str, company_id: str
    ) -> tuple[CompanyCoverage, ...]:
        """Read coverage evaluated at the frozen source cutoff, never wall time."""
        return self.snapshot(snapshot_id).coverage(company_id)

    def family_at(
        self, snapshot_id: str, company_id: str, assessment_at: UtcInstant
    ) -> FamilyResolution:
        """Resolve dated family; propagate unknown IDs and invalid-cutoff errors."""
        return resolve_family(self.snapshot(snapshot_id), company_id, assessment_at)
