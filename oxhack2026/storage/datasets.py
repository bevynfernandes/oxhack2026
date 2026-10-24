"""Cross-artifact dataset validation and frozen readers, without vendor access."""

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256

import orjson
from pydantic import TypeAdapter

from oxhack2026.catalog.schemas import CatalogSnapshot
from oxhack2026.storage.codec import decode_observations
from oxhack2026.storage.contracts import (
    ArtifactStore,
    DatasetManifest,
    ObservationQuery,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
    validate_observation_policy,
)


@dataclass(frozen=True)
class DatasetBundle:
    """Validated contents of one immutable dataset with one selected row per day."""

    manifest: DatasetManifest
    catalog: CatalogSnapshot
    series: tuple[ObservationSeries, ...]
    observations: tuple[ObservationRevision, ...]
    coverage: tuple[SourceCoverage, ...]


def validate_bundle(bundle: DatasetBundle) -> None:
    """Validate identities, source provenance, selected vintages and exact coverage.

    Args:
        bundle: Parsed manifest and all referenced logical tables.
    Returns:
        None for a consistent frozen snapshot; hashes are checked by load_bundle.
    Raises:
        ValueError: For a broken relationship, ambiguity, or inaccurate coverage.
    """
    manifest, catalog = bundle.manifest, bundle.catalog
    if (
        catalog.catalog_version != manifest.catalog_version
        or catalog.mapping_version != manifest.mapping_version
        or catalog.synthetic != manifest.synthetic
        or catalog.recorded_at > manifest.created_at
    ):
        message = "Dataset and catalogue versions, provenance or dates disagree"
        raise ValueError(message)
    series = {row.series_id: row for row in bundle.series}
    coverage = {row.series_id: row for row in bundle.coverage}
    if (
        not series
        or len(series) != len(bundle.series)
        or len(coverage) != len(bundle.coverage)
        or series.keys() != coverage.keys()
    ):
        message = (
            "Dataset requires unique series and exactly one coverage row per series"
        )
        raise ValueError(message)
    packages = {row.package_id: row.ecosystem for row in catalog.packages}
    repositories = {str(row.repository_id) for row in catalog.repositories}
    for row in series.values():
        if (
            row.entity_kind == "package"
            and packages.get(row.entity_id) != row.ecosystem
        ) or (row.entity_kind == "repository" and row.entity_id not in repositories):
            message = "Series identity does not resolve in the frozen catalogue"
            raise ValueError(message)
    _validate_revisions(bundle)
    counts = Counter((row.series_id, row.completeness) for row in bundle.observations)
    for coverage_row in bundle.coverage:
        actual = tuple(
            counts[coverage_row.series_id, state]
            for state in ("complete", "partial", "missing")
        )
        expected = (
            coverage_row.complete_days,
            coverage_row.partial_days,
            coverage_row.missing_days,
        )
        if actual != expected or (
            manifest.completeness == "complete" and coverage_row.status != "complete"
        ):
            message = "Dataset coverage does not match the selected daily revisions"
            raise ValueError(message)


def _validate_revisions(bundle: DatasetBundle) -> None:
    series = {row.series_id: row for row in bundle.series}
    coverage = {row.series_id: row for row in bundle.coverage}
    extractions = {
        row.extraction_id: row for row in bundle.manifest.extraction_manifests
    }
    policies = {
        row.policy_version: row for row in bundle.manifest.availability_policies
    }
    packages = {row.package_id: row for row in bundle.catalog.packages}
    checked_requests: set[tuple[str, str]] = set()
    revisions: set[str] = set()
    days: set[tuple[str, object]] = set()
    for row in bundle.observations:
        key = row.series_id, row.window.start
        if row.revision_id in revisions or key in days:
            message = "A dataset must select one unique revision per series/day"
            raise ValueError(message)
        revisions.add(row.revision_id)
        days.add(key)
        identity = series.get(row.series_id)
        extraction = extractions.get(row.extraction_id)
        policy = policies.get(row.availability_policy_version)
        if identity is None or extraction is None or policy is None:
            message = "Observation series, extraction or policy foreign key is missing"
            raise ValueError(message)
        binding = (row.series_id, row.extraction_id)
        if identity.source == "npm" and binding not in checked_requests:
            package = packages[identity.entity_id]
            request = orjson.dumps(
                {
                    "package": package.model_dump(mode="json"),
                    "catalog_version": bundle.catalog.catalog_version,
                    "window": extraction.requested_window.model_dump(mode="json"),
                },
                option=orjson.OPT_SORT_KEYS,
            )
            canonical_series = (
                "npm-" + sha256(package.canonical_name.encode()).hexdigest()
            )
            if (
                row.series_id != canonical_series
                or extraction.configuration_sha256 != sha256(request).hexdigest()
            ):
                message = (
                    "npm series/package disagrees with its pinned extraction request"
                )
                raise ValueError(message)
            checked_requests.add(binding)
        window = coverage[row.series_id].window
        if not window.start <= row.window.start < row.window.end <= window.end:
            message = "Observation is outside its declared coverage window"
            raise ValueError(message)
        if (
            identity.source != extraction.source
            or identity.source != policy.source
            or row.extraction_version != extraction.extraction_version
            or row.filter_version != extraction.filter_version
            or row.retrieved_at != extraction.retrieved_at
            or row.raw_artifact_sha256
            not in {ref.sha256 for ref in extraction.raw_artifacts}
            or not extraction.requested_window.start <= row.window.start
            or row.window.end > extraction.requested_window.end
        ):
            message = "Observation disagrees with its source extraction provenance"
            raise ValueError(message)
        validate_observation_policy(row, policy)


def load_bundle(manifest: DatasetManifest, artifacts: ArtifactStore) -> DatasetBundle:
    """Verify all referenced bytes and return a cross-validated immutable dataset.

    Args:
        manifest: Exact candidate or published manifest.
        artifacts: Store whose reads verify hashes and sizes.
    Returns:
        Validated catalogue, series, daily revisions and coverage.
    Raises:
        ValueError: For corrupt bytes, invalid schemas or inconsistent tables.
        OSError: If a required artifact cannot be read.
    """
    raw_packages: dict[str, str] = {}
    for extraction in manifest.extraction_manifests:
        for reference in extraction.raw_artifacts:
            content = artifacts.read(reference)
            if extraction.source == "npm":
                payload = orjson.loads(content)
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("package"), str
                ):
                    message = "npm raw artifact requires an explicit package identity"
                    raise ValueError(message)
                raw_packages[reference.sha256] = payload["package"]
    bundle = DatasetBundle(
        manifest=manifest,
        catalog=CatalogSnapshot.model_validate_json(artifacts.read(manifest.catalog)),
        series=TypeAdapter(tuple[ObservationSeries, ...]).validate_python(
            orjson.loads(artifacts.read(manifest.series))
        ),
        observations=decode_observations(artifacts.read(manifest.observations)),
        coverage=TypeAdapter(tuple[SourceCoverage, ...]).validate_python(
            orjson.loads(artifacts.read(manifest.coverage))
        ),
    )
    validate_bundle(bundle)
    packages = {row.package_id: row.canonical_name for row in bundle.catalog.packages}
    series = {row.series_id: row for row in bundle.series}
    for row in bundle.observations:
        identity = series[row.series_id]
        if (
            identity.source == "npm"
            and raw_packages[row.raw_artifact_sha256] != packages[identity.entity_id]
        ):
            message = "npm raw package differs from its attributed series package"
            raise ValueError(message)
    return bundle


def select_observations(
    bundle: DatasetBundle, query: ObservationQuery
) -> Iterator[ObservationRevision]:
    """Filter a frozen selection by measurement and both knowledge-time boundaries.

    Args:
        bundle: Validated immutable dataset.
        query: Exact dataset and optional availability/actual-collection bounds.
    Returns:
        Matching selected rows; no fallback to a newer or earlier revision.
    Raises:
        KeyError: For an unknown dataset or series identity.
    """
    known = {row.series_id for row in bundle.series}
    if (
        query.dataset_version != bundle.manifest.dataset_version
        or not set(query.series_ids) <= known
    ):
        raise KeyError(query.dataset_version)
    selected = set(query.series_ids)
    return (
        row
        for row in bundle.observations
        if row.series_id in selected
        and query.window.start <= row.window.start
        and row.window.end <= query.window.end
        and (query.available_by is None or row.available_at <= query.available_by)
        and (query.collected_by is None or row.first_collected_at <= query.collected_by)
    )
