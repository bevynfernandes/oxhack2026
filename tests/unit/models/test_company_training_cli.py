"""Model CLI orchestration uses mocked storage and retains immutable run lineage."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import orjson
from typer.testing import CliRunner

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.cli.commands import app
from oxhack2026.models.company_combiner import (
    CompanyCombinerPlan,
    CompanyCombinerResult,
)
from oxhack2026.models.company_training import CompanyExperimentPlan
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS
from oxhack2026.storage.contracts import ArtifactReference

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"
REFERENCE = ArtifactReference(
    path=f"objects/{'a' * 2}/{'a' * 64}",
    sha256="a" * 64,
    byte_size=1,
    media_type="application/json",
)


def test_audit_reports_actual_group_coverage_without_training() -> None:
    """Verified source metrics and absent labels stay distinct in an audit."""
    source = CompanySourceSnapshot.model_validate_json(FIXTURE.read_bytes())
    storage = MagicMock()
    storage.snapshot.return_value = source
    storage.manifest.return_value = source
    artifacts = MagicMock()
    artifacts.write.return_value = REFERENCE

    with (
        patch("oxhack2026.cli.models.LocalCompanyStore", return_value=storage),
        patch("oxhack2026.cli.models.FileArtifactStore", return_value=artifacts),
    ):
        result = CliRunner().invoke(
            app, ["models", "audit", "mock", source.snapshot_id, "mock-output"]
        )

    assert result.exit_code == 0, result.output
    report = orjson.loads(artifacts.write.call_args.args[0])
    assert report["company_count"] == 2
    assert report["synthetic"] is True
    assert report["groups"]["adoption_retention"]["usable_observations"] == 2
    assert report["groups"]["financial_health"]["usable_observations"] == 0
    assert report["overall_ascore"] is None
    assert report["label_status"] == "no_label_artifact_supplied"


def test_train_saves_blocked_result_and_input_hashes_without_fitting() -> None:
    """Retain a blocked CLI run with exact inputs and no fabricated weights."""
    source = CompanySourceSnapshot.model_validate_json(FIXTURE.read_bytes())
    test_source = CompanySourceSnapshot.model_validate(
        source.model_dump()
        | {
            "snapshot_id": "synthetic-test-vintage",
            "as_of": "2025-02-02T00:00:00Z",
            "recorded_at": "2025-02-02T00:00:00Z",
        }
    )
    plan = CompanyExperimentPlan(
        experiment_id="synthetic-cli-test",
        group_id="team_execution",
        outcome_id="commercial_viability_12m_v1",
        metric_ids=("sdk_releases_30d_v1",),
        train_snapshot_ids=(source.snapshot_id,),
        test_snapshot_ids=(test_source.snapshot_id,),
        fit_at=datetime(2025, 2, 2, tzinfo=UTC),
        evaluated_at=datetime(2026, 10, 24, tzinfo=UTC),
    )
    storage = MagicMock()
    storage.snapshot.side_effect = [source, test_source]
    storage.manifest.return_value = source
    artifacts = MagicMock()
    artifacts.write.return_value = REFERENCE

    with (
        patch.object(
            Path, "read_bytes", side_effect=[plan.model_dump_json().encode(), b"[]"]
        ),
        patch("oxhack2026.cli.models.LocalCompanyStore", return_value=storage),
        patch("oxhack2026.cli.models.FileArtifactStore", return_value=artifacts),
        patch("oxhack2026.models.company_training._fit") as fit,
    ):
        result = CliRunner().invoke(
            app, ["models", "train", "mock", "plan.json", "labels.json", "mock-output"]
        )

    assert result.exit_code == 0, result.output
    fit.assert_not_called()
    report = orjson.loads(artifacts.write.call_args_list[0].args[0])
    run = orjson.loads(artifacts.write.call_args_list[1].args[0])
    assert report["status"] == "blocked"
    assert report["model"] is None
    assert run["public_release"] is False
    assert len(run["plan_sha256"]) == len(run["labels_sha256"]) == 64


def test_combined_training_loads_three_periods_and_retains_exact_inputs() -> None:
    """The combined flag selects the combiner and preserves all source manifests."""
    source = CompanySourceSnapshot.model_validate_json(FIXTURE.read_bytes())
    plan = CompanyCombinerPlan(
        experiment_id="synthetic-cli-combined-test",
        outcome_id="commercial_viability_12m_v1",
        group_metrics=dict.fromkeys(SPECIALIST_GROUP_IDS, ("sdk_downloads_30d_v1",)),
        base_snapshot_ids=("base-source",),
        blend_snapshot_ids=("blend-source",),
        test_snapshot_ids=("test-source",),
        base_fit_at=datetime(2022, 1, 1, tzinfo=UTC),
        fit_at=datetime(2024, 1, 1, tzinfo=UTC),
        evaluated_at=datetime(2026, 10, 24, tzinfo=UTC),
    )
    storage = MagicMock()
    storage.snapshot.return_value = source
    storage.manifest.return_value = source
    artifacts = MagicMock()
    artifacts.write.return_value = REFERENCE
    blocked = CompanyCombinerResult(
        plan=plan, status="blocked", reasons=("synthetic_sources_forbidden",), counts={}
    )

    with (
        patch.object(
            Path, "read_bytes", side_effect=[plan.model_dump_json().encode(), b"[]"]
        ),
        patch("oxhack2026.cli.models.LocalCompanyStore", return_value=storage),
        patch("oxhack2026.cli.models.FileArtifactStore", return_value=artifacts),
        patch(
            "oxhack2026.models.company_combiner.run_company_combiner",
            return_value=blocked,
        ) as combined,
        patch("oxhack2026.models.company_training.run_company_experiment") as single,
    ):
        result = CliRunner().invoke(
            app,
            [
                "models",
                "train",
                "mock",
                "plan.json",
                "labels.json",
                "mock-output",
                "--combined",
            ],
        )

    assert result.exit_code == 0, result.output
    single.assert_not_called()
    combined.assert_called_once_with(plan, (source, source, source), ())
    assert [call.args[0] for call in storage.snapshot.call_args_list] == [
        "base-source",
        "blend-source",
        "test-source",
    ]
    run = orjson.loads(artifacts.write.call_args_list[1].args[0])
    assert run["status"] == "blocked"
    assert run["public_release"] is False
    assert len(run["source_manifests"]) == 3
