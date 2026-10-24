"""Verified filesystem dataset publication with an atomic compare-and-swap index."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from oxhack2026.catalog.schemas import CatalogSnapshot, Contract, Identifier
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import (
    ArtifactReference,
    DatasetManifest,
    ObservationQuery,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)
from oxhack2026.storage.datasets import DatasetBundle, load_bundle, select_observations
from oxhack2026.storage.local import atomic_write, file_lock


class PublicationIndex(Contract):
    """Small local pointer/index; every version references a hashed manifest."""

    current: Identifier | None = None
    versions: dict[Identifier, ArtifactReference] = Field(default_factory=dict)


@dataclass(frozen=True)
class LocalDatasetStore:
    """Filesystem implementation of C1 readers/publisher, independent of ingestion.

    The root is an application-controlled directory on one POSIX local filesystem.
    Database-backed deployment requires its own transactional publisher.
    """

    root: Path

    @property
    def artifacts(self) -> FileArtifactStore:
        """Return the hashed artifact store for this root without accessing disk."""
        return FileArtifactStore(self.root)

    def index(self) -> PublicationIndex:
        """Return the atomic index; missing stores are empty, malformed stores fail.

        Returns:
            Validated published versions and current pointer.
        Raises:
            OSError: For inaccessible files.
            ValueError: For malformed or oversized metadata.
        """
        path = self.root / "datasets.json"
        try:
            with path.open("rb") as stream:
                content = stream.read(8 * 1024 * 1024 + 1)
        except FileNotFoundError:
            return PublicationIndex()
        if len(content) > 8 * 1024 * 1024:
            message = "Dataset index exceeds the metadata size limit"
            raise ValueError(message)
        index = PublicationIndex.model_validate_json(content)
        if index.current is not None and index.current not in index.versions:
            message = "Dataset index points to an unknown version"
            raise ValueError(message)
        return index

    def manifest(self, dataset_version: str) -> DatasetManifest:
        """Read an exact verified manifest; raise KeyError for unpublished versions."""
        reference = self.index().versions[dataset_version]
        manifest = DatasetManifest.model_validate_json(self.artifacts.read(reference))
        if manifest.dataset_version != dataset_version:
            message = "Published dataset identifier disagrees with its manifest"
            raise ValueError(message)
        return manifest

    def bundle(self, dataset_version: str) -> DatasetBundle:
        """Load and validate all frozen bytes; propagate storage/validation failures."""
        return load_bundle(self.manifest(dataset_version), self.artifacts)

    def catalog(self, dataset_version: str) -> CatalogSnapshot:
        """Read the frozen catalogue; propagate unknown/corrupt store errors."""
        return self.bundle(dataset_version).catalog

    def series(self, dataset_version: str) -> tuple[ObservationSeries, ...]:
        """Read unique frozen series identities; propagate storage/validation errors."""
        return self.bundle(dataset_version).series

    def coverage(self, dataset_version: str) -> tuple[SourceCoverage, ...]:
        """Read verified frozen coverage; propagate storage/validation errors."""
        return self.bundle(dataset_version).coverage

    def observations(self, query: ObservationQuery) -> Iterator[ObservationRevision]:
        """Read selected rows with all C1 bounds; propagate unknown/corrupt errors."""
        return select_observations(self.bundle(query.dataset_version), query)

    def publish(self, manifest: DatasetManifest, expected_current: str | None) -> None:
        """Validate all bytes before atomically comparing and advancing the pointer.

        Args:
            manifest: Candidate immutable dataset, including raw provenance.
            expected_current: Expected active version; None for an empty store.
        Returns:
            None on success or an identical retry of the current publication.
        Raises:
            ValueError: For invalid bundles, reused version IDs, or CAS loss.
            OSError: For filesystem failure; old publication remains readable unless
                rename completed before a later durability error.
        """
        load_bundle(manifest, self.artifacts)
        reference = self.artifacts.write(
            manifest.model_dump_json().encode(), "application/json"
        )
        with file_lock(self.root / ".dataset-publication.lock"):
            index = self.index()
            previous = index.versions.get(manifest.dataset_version)
            if previous is not None and previous != reference:
                message = "An immutable dataset version cannot be replaced"
                raise ValueError(message)
            if index.current == manifest.dataset_version and previous == reference:
                return
            if index.current != expected_current:
                message = "Dataset publication lost its compare-and-swap race"
                raise ValueError(message)
            updated = PublicationIndex(
                current=manifest.dataset_version,
                versions=index.versions | {manifest.dataset_version: reference},
            )
            atomic_write(
                self.root / "datasets.json", updated.model_dump_json().encode()
            )
