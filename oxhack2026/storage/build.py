"""Assemble a verified npm candidate bundle from explicit extraction checkpoints."""

from collections import Counter
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import orjson

from oxhack2026.catalog.schemas import (
    CatalogSnapshot,
    Contract,
    Identifier,
    Sha256,
    TimeWindow,
    UtcInstant,
)
from oxhack2026.ingest.npm import NPM_POLICY, NpmExtraction
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.codec import encode_observations
from oxhack2026.storage.contracts import (
    DatasetManifest,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)
from oxhack2026.storage.datasets import DatasetBundle, load_bundle
from oxhack2026.storage.local import atomic_write


class CandidateConfig(Contract):
    """Pinned dataset identity and reproducibility metadata for one assembly run."""

    dataset_version: Identifier
    created_at: UtcInstant
    code_revision: Identifier
    configuration_sha256: Sha256
    feature_definition_version: Identifier = "features-v1"
    target_definition_version: Identifier = "downloads-v1"


def _coverage(
    rows: tuple[ObservationRevision, ...], series: tuple[ObservationSeries, ...]
) -> tuple[SourceCoverage, ...]:
    grouped: dict[str, list[ObservationRevision]] = {
        row.series_id: [] for row in series
    }
    for row in rows:
        grouped[row.series_id].append(row)
    coverage: list[SourceCoverage] = []
    for identity in series:
        values = grouped[identity.series_id]
        window = TimeWindow(
            start=min(row.window.start for row in values),
            end=max(row.window.end for row in values),
        )
        counts = Counter(row.completeness for row in values)
        complete = counts["complete"] == len(values)
        coverage.append(
            SourceCoverage(
                series_id=identity.series_id,
                window=window,
                expected_days=(window.end - window.start) // timedelta(days=1),
                complete_days=counts["complete"],
                partial_days=counts["partial"],
                missing_days=counts["missing"],
                status="complete"
                if complete
                else "missing"
                if counts["missing"] == len(values)
                else "partial",
                last_success_at=max(row.retrieved_at for row in values),
                reasons=() if complete else ("incomplete_source_days",),
            )
        )
    return tuple(coverage)


def write_candidate(
    catalog: CatalogSnapshot,
    extractions: tuple[NpmExtraction, ...],
    root: Path,
    config: CandidateConfig,
    previous: DatasetBundle | None = None,
) -> DatasetBundle:
    """Write and validate portable candidate artifacts, without advancing publication.

    Args:
        catalog: Frozen verified cohort, chosen before inspecting growth outcomes.
        extractions: Closed daily ranges whose raw artifacts already exist in root.
        root: Application-controlled artifact directory.
        config: Exact immutable dataset identity and versions.
        previous: Optional prior snapshot used to link changed daily revisions.
    Returns:
        Fully cross-validated bundle; dataset_manifest.json is a portable entry point.
    Raises:
        ValueError: For inconsistent identities, ranges or provenance.
        OSError: If any artifact cannot be written or verified.
    """
    if not extractions:
        message = "A candidate requires completed source extractions"
        raise ValueError(message)
    identities: dict[str, ObservationSeries] = {}
    for extraction in extractions:
        identity = extraction.series
        if identities.get(identity.series_id, identity) != identity:
            message = "A series ID cannot identify two different source entities"
            raise ValueError(message)
        identities[identity.series_id] = identity
    series = tuple(identities[key] for key in sorted(identities))
    old = (
        {(row.series_id, row.window.start): row for row in previous.observations}
        if previous
        else {}
    )
    observations: list[ObservationRevision] = []
    for extraction in extractions:
        for row in extraction.observations:
            prior = old.get((row.series_id, row.window.start))
            if prior is not None and (prior.value, prior.completeness) != (
                row.value,
                row.completeness,
            ):
                row = ObservationRevision.model_validate(
                    row.model_dump()
                    | {
                        "supersedes_revision_id": prior.revision_id,
                        "revision_id": "npm-"
                        + sha256(
                            f"{row.revision_id}:{prior.revision_id}".encode()
                        ).hexdigest(),
                    }
                )
            observations.append(row)
    rows = tuple(
        sorted(observations, key=lambda row: (row.series_id, row.window.start))
    )
    coverage = _coverage(rows, series)
    artifacts = FileArtifactStore(root)
    manifest = DatasetManifest(
        **config.model_dump(),
        catalog_version=catalog.catalog_version,
        mapping_version=catalog.mapping_version,
        catalog=artifacts.write(catalog.model_dump_json().encode(), "application/json"),
        series=artifacts.write(
            orjson.dumps([row.model_dump(mode="json") for row in series]),
            "application/json",
        ),
        observations=artifacts.write(
            encode_observations(rows), "application/vnd.apache.parquet"
        ),
        coverage=artifacts.write(
            orjson.dumps([row.model_dump(mode="json") for row in coverage]),
            "application/json",
        ),
        extraction_manifests=tuple(extraction.manifest for extraction in extractions),
        availability_policies=(NPM_POLICY,),
        completeness="complete"
        if all(row.status == "complete" for row in coverage)
        else "partial",
        synthetic=catalog.synthetic,
        limitations=(
            *catalog.limitations,
            "Current registry responses reconstruct history; collection is retained. "
            "Downloads are not customers or revenue.",
        ),
    )
    bundle = load_bundle(manifest, artifacts)
    atomic_write(
        root / "dataset_manifest.json", manifest.model_dump_json(indent=2).encode()
    )
    return bundle
