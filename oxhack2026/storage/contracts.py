"""C1 observations, immutable bundle references and I/O-free storage protocols."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Annotated, Literal, Protocol, Self

from pydantic import Field, field_validator, model_validator

from oxhack2026.catalog.schemas import (
    CatalogSnapshot,
    Contract,
    Count,
    Ecosystem,
    Identifier,
    Sha256,
    TimeWindow,
    UtcInstant,
)

Source = Literal["npm", "pypi", "github", "hackernews"]
Completeness = Literal["complete", "partial", "missing"]
AvailabilityBasis = Literal["collected", "vendor_published", "assumed_lag"]


class ArtifactReference(Contract):
    """Hashed artifact relative to a configured bundle root, never a signed URL."""

    path: Annotated[str, Field(min_length=1)]
    sha256: Sha256
    byte_size: Count
    media_type: Literal[
        "application/json",
        "application/x-ndjson",
        "application/vnd.apache.parquet",
        "application/octet-stream",
    ]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Return a canonical relative POSIX path, rejecting escapes and URLs.

        Args:
            value: Artifact location relative to the bundle root.
        Returns:
            The unchanged safe relative path.
        Raises:
            ValueError: For absolute paths, traversal, URLs, or noncanonical forms.
        """
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or ":" in value
            or str(path) != value
            or value == "."
            or "\x00" in value
        ):
            message = (
                "Artifact path must be a canonical relative path within the bundle"
            )
            raise ValueError(message)
        return value


class AvailabilityPolicy(Contract):
    """Versioned source availability assumptions, separate from vendor publication."""

    policy_version: Identifier
    source: Source
    basis: AvailabilityBasis
    assumed_lag_hours: Count | None
    description: str

    @model_validator(mode="after")
    def validate_assumption(self) -> Self:
        """Return the policy; raise ValueError for inconsistent lag assumptions."""
        if (self.basis == "assumed_lag") != (self.assumed_lag_hours is not None):
            message = "Only assumed-lag policies require assumed_lag_hours"
            raise ValueError(message)
        return self


class ObservationSeries(Contract):
    """Stable source/entity/metric identity; a replacement package is a new series."""

    series_id: Identifier
    source: Source
    entity_kind: Literal["package", "repository", "domain"]
    entity_id: Identifier
    ecosystem: Ecosystem | None
    metric: Identifier
    unit: Literal["downloads", "events", "mentions"]
    cadence: Literal["day"] = "day"

    @model_validator(mode="after")
    def validate_source_identity(self) -> Self:
        """Return this series; raise ValueError for mismatched source/entity scope."""
        expected_kind = {
            "npm": "package",
            "pypi": "package",
            "github": "repository",
            "hackernews": "domain",
        }[self.source]
        expected_ecosystem = self.source if self.source in ("npm", "pypi") else None
        if self.entity_kind != expected_kind or self.ecosystem != expected_ecosystem:
            message = "Series entity kind and ecosystem must match its source"
            raise ValueError(message)
        return self


class ObservationRevision(Contract):
    """Append-only vintage with measurement, knowledge and retrieval times."""

    schema_version: Literal["data-v1"] = "data-v1"
    revision_id: Identifier
    series_id: Identifier
    window: TimeWindow
    value: Count | None
    completeness: Completeness
    published_at: UtcInstant | None
    assumed_available_at: UtcInstant | None
    available_at: UtcInstant
    availability_basis: AvailabilityBasis
    availability_policy_version: Identifier
    first_collected_at: UtcInstant
    retrieved_at: UtcInstant
    extraction_id: Identifier
    extraction_version: Identifier
    filter_version: Identifier
    source_revision_id: str | None
    supersedes_revision_id: Identifier | None
    raw_artifact_sha256: Sha256

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        """Return the revision; raise ValueError for contradictory count/time states."""
        if self.window.end - self.window.start != timedelta(days=1) or any(
            (
                self.window.start.hour,
                self.window.start.minute,
                self.window.start.second,
                self.window.start.microsecond,
            )
        ):
            message = (
                "Daily observations require exactly one UTC midnight-to-midnight day"
            )
            raise ValueError(message)
        if self.completeness == "complete" and self.value is None:
            message = "Complete observations require an explicit count, including zero"
            raise ValueError(message)
        if self.completeness == "missing" and self.value is not None:
            message = "Missing observations require null, not a manufactured zero"
            raise ValueError(message)
        if self.first_collected_at > self.retrieved_at:
            message = "First collection cannot follow retrieval"
            raise ValueError(message)
        if self.first_collected_at < self.window.end:
            message = (
                "Closed daily observations cannot be collected before interval end"
            )
            raise ValueError(message)
        if self.available_at < self.window.end:
            message = (
                "Closed daily observations cannot be available before interval end"
            )
            raise ValueError(message)
        if self.supersedes_revision_id == self.revision_id:
            message = "A revision cannot supersede itself"
            raise ValueError(message)
        self._validate_basis()
        return self

    def _validate_basis(self) -> None:
        expected = {
            "collected": self.first_collected_at,
            "vendor_published": self.published_at,
            "assumed_lag": self.assumed_available_at,
        }[self.availability_basis]
        if expected is None or self.available_at != expected:
            message = "Availability must match the timestamp justified by its basis"
            raise ValueError(message)
        if (
            self.availability_basis != "assumed_lag"
            and self.assumed_available_at is not None
        ):
            message = "Assumed availability is only populated for assumed-lag records"
            raise ValueError(message)
        if self.published_at is not None and self.published_at > self.retrieved_at:
            message = "Observed vendor publication cannot follow retrieval"
            raise ValueError(message)


class SourceCoverage(Contract):
    """Daily source coverage distinguishing complete, partial and absent rows."""

    series_id: Identifier
    window: TimeWindow
    expected_days: Count
    complete_days: Count
    partial_days: Count
    missing_days: Count
    status: Completeness
    last_success_at: UtcInstant | None
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Return coverage; raise ValueError for inconsistent completeness counts."""
        if self.window.end - self.window.start != timedelta(days=self.expected_days):
            message = "Coverage window length must equal expected_days"
            raise ValueError(message)
        if (
            self.expected_days
            != self.complete_days + self.partial_days + self.missing_days
        ):
            message = "Coverage day counts must add up to expected_days"
            raise ValueError(message)
        complete = self.complete_days == self.expected_days and self.expected_days > 0
        missing = self.missing_days == self.expected_days
        if (self.status == "complete") != complete or (
            self.status == "missing"
        ) != missing:
            message = "Coverage status must agree with complete and missing days"
            raise ValueError(message)
        return self


class ExtractionManifest(Contract):
    """Raw extraction identity, filter and result bounds for reproducible provenance."""

    extraction_id: Identifier
    source: Source
    catalog_version: Identifier
    requested_window: TimeWindow
    retrieved_at: UtcInstant
    extraction_version: Identifier
    filter_version: Identifier
    configuration_sha256: Sha256
    raw_artifacts: tuple[ArtifactReference, ...]
    status: Literal["complete", "partial", "failed"]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_raw_provenance(self) -> Self:
        """Return metadata; raise ValueError for unbacked complete extractions."""
        if self.status == "complete" and not self.raw_artifacts:
            message = "Complete extractions require hashed raw artifacts"
            raise ValueError(message)
        return self


class DatasetManifest(Contract):
    """Frozen observation revision set and its exact source/identity provenance."""

    schema_version: Literal["data-v1"] = "data-v1"
    dataset_version: Identifier
    catalog_version: Identifier
    mapping_version: Identifier
    created_at: UtcInstant
    code_revision: Identifier
    configuration_sha256: Sha256
    catalog: ArtifactReference
    series: ArtifactReference
    observations: ArtifactReference
    coverage: ArtifactReference
    extraction_manifests: tuple[ExtractionManifest, ...]
    availability_policies: tuple[AvailabilityPolicy, ...]
    feature_definition_version: Identifier
    target_definition_version: Identifier
    completeness: Literal["complete", "partial"]
    synthetic: bool
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_extractions(self) -> Self:
        """Return the manifest; raise ValueError for invalid publication provenance."""
        if not self.extraction_manifests or not self.availability_policies:
            message = "Datasets require source extraction and availability provenance"
            raise ValueError(message)
        if self.completeness == "complete" and any(
            extraction.status != "complete" for extraction in self.extraction_manifests
        ):
            message = "Incomplete extractions cannot publish a complete dataset"
            raise ValueError(message)
        if any(
            item.catalog_version != self.catalog_version
            for item in self.extraction_manifests
        ):
            message = "Extractions must use this dataset's frozen catalogue"
            raise ValueError(message)
        if any(
            item.retrieved_at > self.created_at for item in self.extraction_manifests
        ):
            message = "Dataset cannot reference extractions retrieved after creation"
            raise ValueError(message)
        policies = {item.policy_version for item in self.availability_policies}
        extractions = {item.extraction_id for item in self.extraction_manifests}
        if len(policies) != len(self.availability_policies) or len(extractions) != len(
            self.extraction_manifests
        ):
            message = "Dataset policy and extraction identifiers must be unique"
            raise ValueError(message)
        policy_sources = {item.source for item in self.availability_policies}
        if any(item.source not in policy_sources for item in self.extraction_manifests):
            message = "Each extraction source requires an availability policy"
            raise ValueError(message)
        return self


class ObservationQuery(Contract):
    """Read only the named frozen revision set; optional knowledge-time filters."""

    dataset_version: Identifier
    series_ids: tuple[Identifier, ...]
    window: TimeWindow
    available_by: UtcInstant | None = None
    collected_by: UtcInstant | None = None


class ArtifactStore(Protocol):
    """Content-addressed I/O boundary; concrete implementations validate all reads."""

    def read(self, reference: ArtifactReference) -> bytes:
        """Read bytes only after checking their reference, size and digest.

        Args:
            reference: Expected immutable artifact metadata.
        Returns:
            Verified artifact bytes.
        Raises:
            OSError: If the artifact is unavailable.
            ValueError: If the path, size or checksum is invalid.
        """
        ...

    def write(self, content: bytes, media_type: str) -> ArtifactReference:
        """Write content under an immutable content-addressed location.

        Args:
            content: Serialized artifact bytes.
            media_type: Supported artifact content type.
        Returns:
            Relative location, checksum, size and content type.
        Raises:
            OSError: If durable write or read-back fails.
            ValueError: If the content type is unsupported.
        """
        ...


class DatasetReader(Protocol):
    """Frozen reads; implementations never fetch vendors or train models."""

    def manifest(self, dataset_version: str) -> DatasetManifest:
        """Read a verified dataset manifest by its immutable version.

        Args:
            dataset_version: Exact dataset identifier.
        Returns:
            The validated manifest; never a silently substituted current version.
        Raises:
            KeyError: If this version is unknown.
            OSError: If storage is unavailable.
            ValueError: If schema or checksum validation fails.
        """
        ...

    def catalog(self, dataset_version: str) -> CatalogSnapshot:
        """Read a frozen catalogue.

        Args:
            dataset_version: Published immutable dataset identifier.
        Returns:
            Validated catalogue for this exact dataset.
        Raises:
            KeyError: If the version does not exist.
            OSError: If storage is unavailable.
            ValueError: If artifact/schema validation fails.
        """
        ...

    def observations(self, query: ObservationQuery) -> Iterator[ObservationRevision]:
        """Read exact dataset revisions satisfying all query bounds.

        Args:
            query: Dataset, series, measurement and knowledge-time constraints.
        Returns:
            Iterator of matching revisions, without silently choosing a newer one.
        Raises:
            KeyError: If the version does not exist.
            OSError: If storage is unavailable.
            ValueError: If artifact/schema validation fails.
        """
        ...

    def coverage(self, dataset_version: str) -> tuple[SourceCoverage, ...]:
        """Read the frozen source coverage for a dataset version.

        Args:
            dataset_version: Exact published dataset identifier.
        Returns:
            Validated per-series coverage, including gaps.
        Raises:
            KeyError: If this version is unknown.
            OSError: If storage is unavailable.
            ValueError: If artifact/schema validation fails.
        """
        ...


class DatasetPublisher(Protocol):
    """Verify complete bundles before atomically advancing their active pointer."""

    def publish(self, manifest: DatasetManifest, expected_current: str | None) -> None:
        """Validate a bundle and atomically compare-and-swap its active pointer.

        Args:
            manifest: Candidate immutable dataset and artifact references.
            expected_current: Expected active version, or None for an empty store.
        Returns:
            None, after verified artifacts and metadata are committed.
        Raises:
            ValueError: If validation fails or the active version has changed.
            OSError: If storage fails; the prior pointer must remain usable.
        """
        ...


def validate_observation_policy(
    revision: ObservationRevision,
    policy: AvailabilityPolicy,
) -> None:
    """Check an observation's assumed bound against its pinned source policy.

    Args:
        revision: Parsed immutable observation vintage.
        policy: Policy referenced by this observation's version identifier.
    Returns:
        None if the availability provenance is consistent.
    Raises:
        ValueError: For a mismatched policy/basis or incorrectly calculated lag.
    """
    if (
        revision.availability_policy_version != policy.policy_version
        or revision.availability_basis != policy.basis
    ):
        message = "Observation references a different availability policy or basis"
        raise ValueError(message)
    if policy.assumed_lag_hours is not None and revision.assumed_available_at != (
        revision.window.end + timedelta(hours=policy.assumed_lag_hours)
    ):
        message = "Assumed availability must equal interval end plus the pinned lag"
        raise ValueError(message)
