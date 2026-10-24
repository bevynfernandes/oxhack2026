"""Public training verifies source bytes and retains five explicit proxy artifacts."""

from hashlib import sha256
from pathlib import Path
from unittest.mock import MagicMock, patch

import orjson
import pytest
from typer.testing import CliRunner

from oxhack2026.cli.commands import app
from oxhack2026.models.public_training import (
    _source_manifest,
    public_dimension_recipes,
    train_public_dimension_models,
)
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS


def test_source_manifest_verifies_bytes_and_rejects_tampering() -> None:
    """A cached source must match its digest, size and retained cohort lineage."""
    metadata = {
        "url": "https://example.org/data",
        "sha256": sha256(b"raw").hexdigest(),
        "byte_size": 3,
    }
    with (
        patch.object(Path, "rglob", return_value=[Path("mock/data.capture.json")]),
        patch.object(Path, "is_file", return_value=True),
        patch.object(
            Path, "read_bytes", side_effect=[orjson.dumps(metadata), b"raw", b"cohort"]
        ),
    ):
        content, digest = _source_manifest(Path("mock"), Path("cohort"))

    assert digest == sha256(content).hexdigest()
    assert orjson.loads(content)["sources"][0]["url"] == metadata["url"]
    with (
        patch.object(Path, "rglob", return_value=[Path("mock/data.capture.json")]),
        patch.object(Path, "is_file", return_value=True),
        patch.object(
            Path, "read_bytes", side_effect=[orjson.dumps(metadata), b"changed"]
        ),
        pytest.raises(ValueError, match="integrity"),
    ):
        _source_manifest(Path("mock"), Path("cohort"))


def test_public_training_retains_all_five_models_and_descriptive_index() -> None:
    """Orchestration writes actual fit results without claiming public forecasts."""
    model = MagicMock()
    model.model_dump_json.return_value = "{}"
    with (
        patch(
            "oxhack2026.models.public_training._source_manifest",
            return_value=(b"{}", "a" * 64),
        ),
        patch(
            "oxhack2026.models.public_training.build_sdk_datasets",
            return_value=(dict.fromkeys(SPECIALIST_GROUP_IDS, ()), {}),
        ),
        patch(
            "oxhack2026.models.public_training.build_financial_dataset",
            return_value=((), {}),
        ),
        patch(
            "oxhack2026.models.public_training.fit_numeric_dimension",
            side_effect=lambda *args: (model, {}),
        ) as numeric,
        patch(
            "oxhack2026.models.public_training.fit_entity_sentiment",
            return_value=(model, {}),
        ) as sentiment,
        patch.object(Path, "mkdir"),
        patch.object(Path, "read_bytes", return_value=b"[]"),
        patch.object(Path, "write_bytes") as write,
    ):
        report = train_public_dimension_models(
            Path("mock"), Path("cohort"), Path("out")
        )

    assert numeric.call_count == 4
    sentiment.assert_called_once()
    artifacts = report["artifacts"]
    assert isinstance(artifacts, dict)
    assert set(artifacts) == set(SPECIALIST_GROUP_IDS)
    assert report["public_serving_approved"] is False
    assert write.call_count == 13


def test_recipes_are_explicit_and_cli_dispatches_public_commands() -> None:
    """Both commands retain offline artifacts and do not invoke serving code."""
    assert {recipe.dimension for recipe in public_dimension_recipes()} == set(
        SPECIALIST_GROUP_IDS
    ) - {"attention_sentiment"}
    for command, target in (
        (
            "train-public",
            "oxhack2026.models.public_training.train_public_dimension_models",
        ),
        (
            "compare-public",
            "oxhack2026.models.dimension_comparison.compare_public_architectures",
        ),
    ):
        with patch(target, return_value={}) as train:
            result = CliRunner().invoke(
                app, ["models", command, "mock", "cohort", "out"]
            )
        assert result.exit_code == 0, result.output
        train.assert_called_once_with(Path("mock"), Path("cohort"), Path("out"))
