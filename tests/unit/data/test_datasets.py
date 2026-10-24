"""Pure cross-artifact validation, frozen query filtering, and Parquet semantics."""

from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO

import polars as pl
import pytest

from oxhack2026.storage.codec import decode_observations, encode_observations
from oxhack2026.storage.contracts import (
    ArtifactStore,
    DatasetManifest,
    ObservationQuery,
    ObservationRevision,
    ObservationSeries,
)
from oxhack2026.storage.datasets import (
    DatasetBundle,
    select_observations,
    validate_bundle,
)


def test_parquet_preserves_zero_null_count_and_utc(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Explicit Arrow types survive round trips, including null publication dates."""
    bundle, _ = synthetic_bundle
    decoded = decode_observations(encode_observations(bundle.observations))
    assert decoded == bundle.observations
    assert [row.value for row in decoded] == [0, None, 120]
    assert all(row.window.start.tzinfo is not None for row in decoded)
    assert all(row.published_at is None for row in decoded)


def test_incompatible_parquet_schema_rejected() -> None:
    """A readable Parquet file is not sufficient to satisfy the C1 schema."""
    output = BytesIO()
    pl.DataFrame({"value": [1.5]}).write_parquet(output)
    with pytest.raises(ValueError, match="schema differs"):
        decode_observations(output.getvalue())


def test_two_selected_vintages_for_day_rejected(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Publication must freeze exactly one selected revision per daily series."""
    bundle, _ = synthetic_bundle
    changed = ObservationRevision.model_validate(
        bundle.observations[0].model_dump() | {"revision_id": "other"}
    )
    with pytest.raises(ValueError, match="one unique revision"):
        validate_bundle(replace(bundle, observations=(*bundle.observations, changed)))


def test_claimed_coverage_requires_every_day(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Dropping a missing row does not manufacture complete daily coverage."""
    bundle, _ = synthetic_bundle
    with pytest.raises(ValueError, match="coverage does not match"):
        validate_bundle(replace(bundle, observations=bundle.observations[:1]))


@pytest.mark.parametrize(
    "change",
    [
        {"extraction_id": "unknown"},
        {"availability_policy_version": "unknown"},
        {"raw_artifact_sha256": "f" * 64},
        {"filter_version": "wrong"},
    ],
)
def test_provenance_cannot_drift(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore], change: dict[str, object]
) -> None:
    """Every selected count must agree with its source, policy and raw extraction."""
    bundle, _ = synthetic_bundle
    changed = ObservationRevision.model_validate(
        bundle.observations[0].model_dump() | change
    )
    with pytest.raises(ValueError):
        validate_bundle(
            replace(bundle, observations=(changed, *bundle.observations[1:]))
        )


def test_catalogue_and_series_relationships(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Manifest and package identity must resolve in the frozen catalogue."""
    bundle, _ = synthetic_bundle
    wrong = ObservationSeries.model_validate(
        bundle.series[0].model_dump() | {"entity_id": "unknown"}
    )
    with pytest.raises(ValueError, match="catalogue"):
        validate_bundle(replace(bundle, series=(wrong,)))
    manifest = DatasetManifest.model_validate(
        bundle.manifest.model_dump() | {"mapping_version": "different"}
    )
    with pytest.raises(ValueError, match="versions"):
        validate_bundle(replace(bundle, manifest=manifest))


def test_prospective_filter_does_not_substitute_vintages(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Assumed historical availability never implies actual collection at the time."""
    bundle, _ = synthetic_bundle
    query = ObservationQuery(
        dataset_version=bundle.manifest.dataset_version,
        series_ids=(bundle.series[0].series_id,),
        window=bundle.coverage[0].window,
        available_by=datetime(2025, 1, 10, tzinfo=UTC),
    )
    assert len(tuple(select_observations(bundle, query))) == 3
    prospective = ObservationQuery.model_validate(
        query.model_dump() | {"collected_by": query.available_by}
    )
    assert tuple(select_observations(bundle, prospective)) == ()
    unknown = ObservationQuery.model_validate(
        query.model_dump() | {"series_ids": ["unknown"]}
    )
    with pytest.raises(KeyError):
        select_observations(bundle, unknown)
