"""Thin data/platform CLI; imports start no network, database, or scheduler."""

import logging
from pathlib import Path

import typer

from oxhack2026.catalog.schemas import CatalogSnapshot
from oxhack2026.ingest.pipeline import NpmRun, extract_catalog
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference, DatasetManifest
from oxhack2026.storage.datasets import load_bundle
from oxhack2026.storage.publication import LocalDatasetStore

logger = logging.getLogger(__name__)
app = typer.Typer(
    help="SignalShift data/platform administration.", no_args_is_help=True
)
data = typer.Typer(help="Validate, extract and publish immutable datasets.")
app.add_typer(data, name="data")


@data.command("catalog-validate")
def catalog_validate(path: Path) -> None:
    """Validate a frozen catalogue at PATH; errors propagate without modifications."""
    catalog = CatalogSnapshot.model_validate_json(path.read_bytes())
    typer.echo(
        f"{catalog.catalog_version}: {len(catalog.tools)} tools; "
        f"synthetic={catalog.synthetic}"
    )


@data.command("extract-npm")
def extract_npm(catalog_path: Path, root: Path, run_path: Path) -> None:
    """Extract CATALOG_PATH using a pinned RUN_PATH JSON config into ROOT."""
    catalog = CatalogSnapshot.model_validate_json(catalog_path.read_bytes())
    run = NpmRun.model_validate_json(run_path.read_bytes())
    bundle = extract_catalog(catalog, root, run)
    typer.echo(
        f"{bundle.manifest.dataset_version}: "
        f"{len(bundle.observations)} selected daily rows"
    )


@data.command("dataset-validate")
def dataset_validate(root: Path) -> None:
    """Validate ROOT/dataset_manifest.json and every referenced artifact."""
    manifest = DatasetManifest.model_validate_json(
        (root / "dataset_manifest.json").read_bytes()
    )
    bundle = load_bundle(manifest, FileArtifactStore(root))
    typer.echo(
        f"{manifest.dataset_version}: {manifest.completeness}; "
        f"{len(bundle.series)} series"
    )


@data.command("publish")
def publish(root: Path, expected_current: str | None = None) -> None:
    """Atomically publish the validated candidate, conditional on EXPECTED_CURRENT."""
    manifest = DatasetManifest.model_validate_json(
        (root / "dataset_manifest.json").read_bytes()
    )
    LocalDatasetStore(root).publish(manifest, expected_current)
    typer.echo(manifest.dataset_version)


@data.command("health")
def health(root: Path) -> None:
    """Verify the active dataset and report frozen coverage without refreshing it."""
    store = LocalDatasetStore(root)
    current = store.index().current
    if current is None:
        logger.error("No dataset has been published")
        raise typer.Exit(1)
    bundle = store.bundle(current)
    for coverage in bundle.coverage:
        typer.echo(
            f"{coverage.series_id}: {coverage.status}; missing={coverage.missing_days}"
        )


@data.command("artifact-verify")
def artifact_verify(root: Path, reference_path: Path) -> None:
    """Verify a JSON artifact reference against ROOT without changing any files."""
    reference = ArtifactReference.model_validate_json(reference_path.read_bytes())
    FileArtifactStore(root).read(reference)
    typer.echo(reference.sha256)
