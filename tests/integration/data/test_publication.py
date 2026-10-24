"""Opt-in local publication, resume, failure and concurrent-writer checks."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
import orjson
import pytest

from oxhack2026.ingest.checkpoints import checkpointed_fetch
from oxhack2026.ingest.npm import NpmRequest
from oxhack2026.storage.contracts import (
    ArtifactStore,
    DatasetManifest,
    ObservationQuery,
)
from oxhack2026.storage.datasets import DatasetBundle
from oxhack2026.storage.publication import LocalDatasetStore

pytestmark = pytest.mark.integration
OUTPUTS = Path(__file__).resolve().parents[2] / "outputs" / "dataset-publication"


def _store(bundle: DatasetBundle, source: ArtifactStore) -> LocalDatasetStore:
    store = LocalDatasetStore(OUTPUTS / uuid4().hex)
    manifest = bundle.manifest
    refs = [manifest.catalog, manifest.series, manifest.observations, manifest.coverage]
    refs.extend(
        ref
        for extraction in manifest.extraction_manifests
        for ref in extraction.raw_artifacts
    )
    for reference in refs:
        assert (
            store.artifacts.write(source.read(reference), reference.media_type)
            == reference
        )
    return store


def test_publication_idempotence_and_frozen_reader(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Repeat publication keeps one version and exact catalog/history/coverage reads."""
    bundle, source = synthetic_bundle
    store = _store(bundle, source)
    store.publish(bundle.manifest, None)
    store.publish(bundle.manifest, None)
    version = bundle.manifest.dataset_version
    assert list(store.index().versions) == [version]
    assert store.catalog(version) == bundle.catalog
    assert store.series(version) == bundle.series
    assert store.coverage(version) == bundle.coverage
    query = ObservationQuery(
        dataset_version=version,
        series_ids=(bundle.series[0].series_id,),
        window=bundle.coverage[0].window,
    )
    assert tuple(store.observations(query)) == bundle.observations


def test_concurrent_publish_has_one_winner(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Two writers with the same expected pointer cannot overwrite each other."""
    bundle, source = synthetic_bundle
    store = _store(bundle, source)
    manifests = [
        DatasetManifest.model_validate(
            bundle.manifest.model_dump() | {"dataset_version": f"race-{i}"}
        )
        for i in range(2)
    ]

    def publish(manifest: DatasetManifest) -> str:
        try:
            store.publish(manifest, None)
        except ValueError as error:
            assert "compare-and-swap" in str(error)
            return "lost"
        else:
            return "published"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(publish, manifests)) == ["lost", "published"]
    assert len(store.index().versions) == 1


def test_failed_publication_and_version_reuse_leave_old_readable(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """A crash before pointer replacement and an ID collision preserve old batches."""
    bundle, source = synthetic_bundle
    store = _store(bundle, source)
    first = bundle.manifest
    store.publish(first, None)
    next_manifest = DatasetManifest.model_validate(
        first.model_dump() | {"dataset_version": "next"}
    )
    with (
        patch(
            "oxhack2026.storage.publication.atomic_write",
            side_effect=OSError("synthetic failure"),
        ),
        pytest.raises(OSError),
    ):
        store.publish(next_manifest, first.dataset_version)
    assert store.index().current == first.dataset_version
    assert store.bundle(first.dataset_version) == bundle
    changed = DatasetManifest.model_validate(
        first.model_dump() | {"code_revision": "other"}
    )
    with pytest.raises(ValueError, match="cannot be replaced"):
        store.publish(changed, first.dataset_version)
    raw = first.extraction_manifests[0].raw_artifacts[0]
    (store.root / raw.path).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        store.publish(next_manifest, first.dataset_version)
    assert store.index().current == first.dataset_version


def test_durable_checkpoint_resume_and_fresh_run(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """A new process/client resumes the same raw vintage; a fresh run can revise it."""
    bundle, _ = synthetic_bundle
    root = OUTPUTS / uuid4().hex
    request = NpmRequest(
        package=bundle.catalog.packages[0],
        catalog_version=bundle.catalog.catalog_version,
        window=bundle.coverage[0].window,
    )
    content = orjson.dumps(
        {
            "package": request.package.canonical_name,
            "start": "2025-01-01",
            "end": "2025-01-03",
            "downloads": [{"day": "2025-01-01", "downloads": 1}],
        }
    )
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=content)
        )
    ) as client:
        first = checkpointed_fetch(request, client, root, "run-1")
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("resume made HTTP request")
        )
    ) as client:
        resumed = checkpointed_fetch(request, client, root, "run-1")
    assert resumed == first
    content = content.replace(b'"downloads":1', b'"downloads":2')
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=content)
        )
    ) as client:
        refreshed = checkpointed_fetch(request, client, root, "run-2")
    assert refreshed.observations[0].value == 2
    assert refreshed.observations[0].revision_id != first.observations[0].revision_id
