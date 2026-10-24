"""Thin CLI dispatch and deterministic pipeline configuration without external I/O."""

from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from oxhack2026.cli.commands import app
from oxhack2026.ingest.npm import NpmCheckpoint, NpmRequest, normalize_range
from oxhack2026.ingest.pipeline import NpmRun, extract_catalog
from oxhack2026.storage.contracts import ArtifactStore
from oxhack2026.storage.datasets import DatasetBundle
from oxhack2026.storage.publication import PublicationIndex


def test_cli_validates_catalog_and_candidate(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Commands parse explicit inputs and delegate validation to the same services."""
    bundle, _ = synthetic_bundle
    runner = CliRunner()
    with patch.object(
        Path, "read_bytes", return_value=bundle.catalog.model_dump_json().encode()
    ):
        result = runner.invoke(app, ["data", "catalog-validate", "catalog.json"])
    assert result.exit_code == 0 and "synthetic-catalog" in result.output
    with (
        patch.object(
            Path, "read_bytes", return_value=bundle.manifest.model_dump_json().encode()
        ),
        patch("oxhack2026.cli.commands.load_bundle", return_value=bundle),
    ):
        result = runner.invoke(app, ["data", "dataset-validate", "mock"])
    assert result.exit_code == 0 and "partial" in result.output


def test_cli_publication_and_empty_health(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Publishing supplies the expected pointer; empty stores fail health explicitly."""
    bundle, _ = synthetic_bundle
    store = MagicMock()
    store.index.return_value = PublicationIndex()
    with (
        patch.object(
            Path, "read_bytes", return_value=bundle.manifest.model_dump_json().encode()
        ),
        patch("oxhack2026.cli.commands.LocalDatasetStore", return_value=store),
    ):
        result = CliRunner().invoke(
            app, ["data", "publish", "mock", "--expected-current", "old"]
        )
        assert result.exit_code == 0
        store.publish.assert_called_once_with(bundle.manifest, "old")
        assert CliRunner().invoke(app, ["data", "health", "mock"]).exit_code == 1


def test_pipeline_pins_run_and_passes_bounded_requests(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Frozen run configuration and request checkpoints feed deterministic assembly."""
    bundle, artifacts = synthetic_bundle
    manifest = bundle.manifest.extraction_manifests[0]
    request = NpmRequest(
        package=bundle.catalog.packages[0],
        catalog_version=bundle.catalog.catalog_version,
        window=bundle.coverage[0].window,
    )
    extraction = normalize_range(
        NpmCheckpoint(
            request=request,
            retrieved_at=manifest.retrieved_at,
            raw_artifact=manifest.raw_artifacts[0],
        ),
        artifacts.read(manifest.raw_artifacts[0]),
    )
    run = NpmRun(
        run_id="run",
        dataset_version="dataset",
        window=request.window,
        code_revision="test",
    )
    with (
        patch("oxhack2026.ingest.pipeline.file_lock", return_value=nullcontext()),
        patch.object(Path, "exists", return_value=False),
        patch("oxhack2026.ingest.pipeline.atomic_write") as write,
        patch(
            "oxhack2026.ingest.pipeline.checkpointed_fetch", return_value=extraction
        ) as fetch,
        patch("oxhack2026.ingest.pipeline.httpx.Client"),
        patch(
            "oxhack2026.ingest.pipeline.write_candidate", return_value=bundle
        ) as build,
    ):
        assert extract_catalog(bundle.catalog, Path("mock"), run) == bundle
    write.assert_called_once()
    fetch.assert_called_once()
    assert build.call_args.args[3].created_at == manifest.retrieved_at
    with (
        patch("oxhack2026.ingest.pipeline.file_lock", return_value=nullcontext()),
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_bytes", return_value=b"different"),
        pytest.raises(ValueError, match="already bound"),
    ):
        extract_catalog(bundle.catalog, Path("mock"), run)
