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
    help="SignalShift data/platform administration.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
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


@data.command("company-build")
def company_build(settings_path: Path, npm_root: Path, root: Path) -> None:
    """Build a company source candidate from SETTINGS_PATH and existing NPM_ROOT."""
    from oxhack2026.ingest.company_pipeline import (
        CompanyBuildSettings,
        build_company_source,
    )

    settings = CompanyBuildSettings.model_validate_json(settings_path.read_bytes())
    snapshot = build_company_source(settings, npm_root, root)
    typer.echo(f"{snapshot.snapshot_id}: {len(snapshot.companies)} companies")


@data.command("company-publish")
def company_publish(
    root: Path, snapshot_id: str, expected_current: str | None = None
) -> None:
    """Verify and publish an exact company candidate with a conditional pointer."""
    from oxhack2026.catalog.company import CompanySourceSnapshot
    from oxhack2026.ingest.capture import CaptureRun
    from oxhack2026.storage.company import LocalCompanyStore

    identifier = CaptureRun(run_id=snapshot_id).run_id
    snapshot = CompanySourceSnapshot.model_validate_json(
        (root / "candidates" / f"{identifier}.json").read_bytes()
    )
    if snapshot.snapshot_id != identifier:
        message = "Candidate filename and source identity disagree"
        raise ValueError(message)
    manifest = LocalCompanyStore(root).publish(snapshot, expected_current)
    typer.echo(manifest.snapshot_id)


@data.command("company-health")
def company_health(root: Path, snapshot_id: str) -> None:
    """Verify an exact source publication and summarize explicit coverage."""
    from oxhack2026.storage.company import LocalCompanyStore

    snapshot = LocalCompanyStore(root).snapshot(snapshot_id)
    for company in snapshot.companies:
        for coverage in snapshot.coverage(company.company_id):
            typer.echo(
                f"{company.company_id} {coverage.family}: "
                f"{len(coverage.observed_metric_ids)}/"
                f"{len(coverage.applicable_metric_ids)} observed; "
                f"{len(coverage.stale_metric_ids)} stale"
            )


@data.command("assessment-publish")
def assessment_publish(
    root: Path,
    publication_id: str,
    assessments_path: Path,
    expected_current: str | None = None,
) -> None:
    """Validate a model-produced C2 array against ROOT and publish an exact batch."""
    from pydantic import TypeAdapter

    from oxhack2026.models.company_assessments import CompanyAssessment
    from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore

    records = TypeAdapter(tuple[CompanyAssessment, ...]).validate_json(
        assessments_path.read_bytes()
    )
    manifest = LocalCompanyAssessmentStore(root).publish(
        publication_id, records, expected_current
    )
    typer.echo(manifest.publication_id)


@data.command("assessment-health")
def assessment_health(root: Path, publication_id: str) -> None:
    """Verify exact C2 records, manifest and all referenced C1 source bytes."""
    from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore

    records = LocalCompanyAssessmentStore(root).assessments(publication_id)
    typer.echo(f"{publication_id}: {len(records)} verified company assessments")


@data.command("company-backup")
def company_backup(root: Path, archive: Path) -> None:
    """Verify and back up all published company versions; emit the ZIP SHA-256."""
    from oxhack2026.storage.recovery import backup_company_store

    typer.echo(backup_company_store(root, archive))


@data.command("company-restore")
def company_restore(archive: Path, destination: Path, expected_sha256: str) -> None:
    """Restore verified company publications into a new DESTINATION directory."""
    from oxhack2026.storage.recovery import restore_company_store

    restore_company_store(archive, destination, expected_sha256)
    typer.echo("Company source and assessment publications verified and restored")
