"""Offline company training and source-readiness commands with immutable outputs."""

from hashlib import sha256
from pathlib import Path

import orjson
import typer
from pydantic import TypeAdapter

from oxhack2026.features.company_outcomes import COMPANY_OUTCOME_IDS
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.startup_outlook import (
    SPECIALIST_GROUP_IDS,
    SpecialistGroupId,
    build_company_outlook,
)
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.company import LocalCompanyStore, resolve_family

app = typer.Typer(help="Audit inputs and run offline company model experiments.")


@app.command("compare-public")
def compare_public_models(root: Path, cohort_path: Path, output_root: Path) -> None:
    """Compare many candidate architectures on fixed acquired public datasets.

    Args:
        root: Retained raw-capture directory.
        cohort_path: Frozen SDK cohort JSON.
        output_root: Retained candidate models and validation/test reports.
    Returns:
        None; emits the retained architecture-comparison path.
    Raises:
        ValueError: Source integrity or experiment support fails.
        OSError: Input/output storage fails.
    """
    from oxhack2026.models.dimension_comparison import compare_public_architectures

    compare_public_architectures(root, cohort_path, output_root)
    typer.echo(str(output_root / "comparison.json"))


@app.command("train-public")
def train_public_dimensions(root: Path, cohort_path: Path, output_root: Path) -> None:
    """Train the five descriptive dimension candidates from acquired public datasets.

    Args:
        root: Retained public raw-capture directory.
        cohort_path: Frozen public SDK cohort JSON.
        output_root: Model and evaluation output directory.
    Returns:
        None; emits run artifact metadata after real fitting completes.
    Raises:
        ValueError: Capture integrity, schema or training support fails.
        OSError: Inputs or outputs cannot be accessed.
    """
    from oxhack2026.models.public_training import train_public_dimension_models

    typer.echo(
        orjson.dumps(
            train_public_dimension_models(root, cohort_path, output_root)
        ).decode()
    )


@app.command("audit")
def audit_company_models(root: Path, snapshot_id: str, output_root: Path) -> None:
    """Audit the exact real source behind production company profiles.

    Args:
        root: Existing verified company publication/artifact directory.
        snapshot_id: Exact immutable source identity; never silently use current.
        output_root: Directory for content-addressed JSON audit artifacts.
    Returns:
        None; emits the retained artifact reference as JSON.
    Raises:
        KeyError: The source identity is unknown.
        ValueError: Source or raw evidence hashes fail validation.
        OSError: Source/output storage fails.
    """
    store = LocalCompanyStore(root)
    snapshot = store.snapshot(snapshot_id)
    groups: dict[SpecialistGroupId, dict[str, object]] = {
        group: {"companies_with_usable_metrics": 0, "usable_observations": 0}
        for group in SPECIALIST_GROUP_IDS
    }
    families = set()
    usable_companies: dict[SpecialistGroupId, set[str]] = {
        group: set() for group in SPECIALIST_GROUP_IDS
    }
    observations = dict.fromkeys(SPECIALIST_GROUP_IDS, 0)
    for company in snapshot.companies:
        family = resolve_family(
            snapshot, company.company_id, snapshot.as_of, public_only=True
        )
        if family.family_id is not None:
            families.add(family.family_id)
        for section in build_company_outlook(snapshot, company.company_id).specialists:
            if section.usable_metric_observation_ids:
                usable_companies[section.group_id].add(company.company_id)
            observations[section.group_id] += len(section.usable_metric_observation_ids)
    for group in SPECIALIST_GROUP_IDS:
        groups[group]["companies_with_usable_metrics"] = len(usable_companies[group])
        groups[group]["usable_observations"] = observations[group]
        groups[group]["model_status"] = "not_trained"
    report = {
        "schema_version": "company-training-audit-v1",
        "source": store.manifest(snapshot_id).model_dump(mode="json"),
        "company_count": len(snapshot.companies),
        "resolved_family_count": len(families),
        "origin_count": 1,
        "synthetic": snapshot.synthetic,
        "groups": groups,
        "supported_label_definitions": COMPANY_OUTCOME_IDS,
        "label_status": "no_label_artifact_supplied",
        "overall_ascore": None,
        "reasons": [
            "no_verified_training_labels",
            "no_chronological_holdout",
            "overall_utility_not_defined",
        ],
    }
    reference = FileArtifactStore(output_root).write(
        orjson.dumps(report, option=orjson.OPT_SORT_KEYS), "application/json"
    )
    typer.echo(reference.model_dump_json())


@app.command("train")
def train_company_model(
    root: Path,
    plan_path: Path,
    labels_path: Path,
    output_root: Path,
    combined: bool = False,
) -> None:
    """Run a frozen experiment using production sources and adjudicated JSON labels.

    Args:
        root: Verified company source/artifact directory.
        plan_path: Frozen specialist or, with --combined, combiner plan JSON.
        labels_path: JSON array of source-adjudicated CompanyOutcomeLabel records.
        output_root: Directory retaining content-addressed results and input hashes.
        combined: Read a three-period CompanyCombinerPlan and fit all five groups.
    Returns:
        None; emits an immutable run reference, including for blocked runs.
    Raises:
        ValueError: Plan, labels, source integrity or training prerequisites conflict.
        KeyError: A frozen snapshot identity is missing.
        OSError: Input/output storage fails.
    """
    from oxhack2026.models.company_combiner import (
        CompanyCombinerPlan,
        CompanyCombinerResult,
        run_company_combiner,
    )
    from oxhack2026.models.company_training import (
        CompanyExperimentPlan,
        CompanyExperimentResult,
        run_company_experiment,
    )

    plan_bytes = plan_path.read_bytes()
    label_bytes = labels_path.read_bytes()
    labels = TypeAdapter(tuple[CompanyOutcomeLabel, ...]).validate_json(label_bytes)
    sources = LocalCompanyStore(root)
    result: CompanyCombinerResult | CompanyExperimentResult
    if combined:
        combined_plan = CompanyCombinerPlan.model_validate_json(plan_bytes)
        identities = (
            combined_plan.base_snapshot_ids
            + combined_plan.blend_snapshot_ids
            + combined_plan.test_snapshot_ids
        )
        result = run_company_combiner(
            combined_plan, tuple(sources.snapshot(key) for key in identities), labels
        )
    else:
        plan = CompanyExperimentPlan.model_validate_json(plan_bytes)
        identities = plan.train_snapshot_ids + plan.test_snapshot_ids
        result = run_company_experiment(
            plan, tuple(sources.snapshot(key) for key in identities), labels
        )
    output = FileArtifactStore(output_root)
    result_reference = output.write(
        result.model_dump_json().encode(), "application/json"
    )
    run = {
        "experiment_id": result.plan.experiment_id,
        "plan_sha256": sha256(plan_bytes).hexdigest(),
        "labels_sha256": sha256(label_bytes).hexdigest(),
        "source_manifests": [
            sources.manifest(key).model_dump(mode="json") for key in identities
        ],
        "result": result_reference.model_dump(mode="json"),
        "status": result.status,
        "public_release": False,
    }
    reference = output.write(
        orjson.dumps(run, option=orjson.OPT_SORT_KEYS), "application/json"
    )
    typer.echo(reference.model_dump_json())
