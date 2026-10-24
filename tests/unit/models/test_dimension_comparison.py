"""Architecture selection uses validation outcomes and retains fitted candidates."""

from datetime import date
from pathlib import Path
from typing import cast
from unittest.mock import patch

import numpy as np
import pytest

from oxhack2026.models.dimension_comparison import (
    _classifiers,
    _regressors,
    compare_numeric_architectures,
    compare_public_architectures,
    compare_sentiment_architectures,
)
from oxhack2026.models.public_dimensions import DimensionRow, NumericRecipe


class ConstantEstimator:
    """Small deterministic estimator used to isolate experiment orchestration."""

    def __init__(self, value: float) -> None:
        self.value = value
        self.classes_ = np.array(["Negative", "Neutral", "Positive"])

    def fit(self, values: object, truth: object) -> "ConstantEstimator":
        """Return the fixed estimator without accessing held-out outcomes."""
        return self

    def predict(self, values: object) -> object:
        """Return one constant for every input row."""
        return np.full(len(np.asarray(values)), self.value)

    def predict_proba(self, values: object) -> object:
        """Return normalized three-class probabilities for sparse input rows."""
        return np.tile([0.1, 0.2, 0.7], (cast(np.ndarray, values).shape[0], 1))


def test_numeric_comparison_selects_validation_and_retains_model() -> None:
    """The better test-only candidate cannot override validation selection."""
    recipe = NumericRecipe(
        dimension="team_execution",
        target="Synthetic test target",
        feature_names=("count",),
        baseline_index=0,
        train_end=date(2021, 1, 1),
        validation_end=date(2023, 1, 1),
        test_end=date(2025, 1, 1),
        limitations=("Synthetic test only",),
    )
    partitions = {
        name: [
            DimensionRow(name, name, date(2020, 1, 1), date(2020, 2, 1), (9,), target)
            for _ in range(10)
        ]
        for name, target in (("train", 1.0), ("validation", 1.0), ("test", 2.0))
    }
    with (
        patch(
            "oxhack2026.models.dimension_comparison.partition_numeric_rows",
            return_value=partitions,
        ),
        patch(
            "oxhack2026.models.dimension_comparison._regressors",
            return_value=[
                ("validation_winner", ConstantEstimator(1)),
                ("test_winner", ConstantEstimator(2)),
            ],
        ),
        patch.object(Path, "mkdir"),
        patch.object(Path, "write_bytes") as write,
    ):
        report = compare_numeric_architectures(recipe, (), Path("mock"))

    assert report["selected"] == "validation_winner"
    assert report["public_serving_approved"] is False
    assert write.call_count == 3


def test_comparison_rejects_nonfinite_inputs_before_fitting() -> None:
    """Malformed features cannot generate misleading comparison metrics."""
    from oxhack2026.models.public_training import public_dimension_recipes

    row = DimensionRow("mock", "mock", date.min, date.max, (float("nan"),), 1)
    with (
        patch(
            "oxhack2026.models.dimension_comparison.partition_numeric_rows",
            return_value={name: [row] for name in ("train", "validation", "test")},
        ),
        pytest.raises(ValueError, match="finite"),
    ):
        compare_numeric_architectures(public_dimension_recipes()[0], (), Path("mock"))


def test_sentiment_comparison_preserves_metrics_and_artifact() -> None:
    """Training-only vocabulary feeds probability metrics in all partitions."""
    partitions = {
        name: [
            (f"targetentity sample {label}", label, f"entity-{index}")
            for index, label in enumerate(("Negative", "Neutral", "Positive"))
            for _ in range(2)
        ]
        for name in ("train", "validation", "test")
    }
    with (
        patch(
            "oxhack2026.models.dimension_comparison.partition_sentiment_articles",
            return_value=(partitions, {}),
        ),
        patch(
            "oxhack2026.models.dimension_comparison._classifiers",
            return_value=[("fixed", ConstantEstimator(1))],
        ),
        patch.object(Path, "mkdir"),
        patch.object(Path, "write_bytes") as write,
    ):
        report = compare_sentiment_architectures((), Path("mock"))

    assert report["selected"] == "fixed"
    assert report["counts"] == {"train": 6, "validation": 6, "test": 6}
    assert write.call_count == 2


def test_fixed_candidate_inventory_covers_requested_architectures() -> None:
    """Factories include linear, tree, boosting, kernel and small neural models."""
    regressors = _regressors()
    classifiers = _classifiers([f"entity-{i}" for i in range(12)], ["Positive"] * 12)

    assert len(regressors) == 15
    assert len(classifiers) == 12
    assert {"catboost", "small_mlp", "random_forest", "ridge_1", "rbf_svr"} <= {
        name for name, _ in regressors
    }
    assert "calibrated_linear_svm" in {name for name, _ in classifiers}


def test_public_comparison_retains_all_dimensions_and_source_code_lineage() -> None:
    """The runner compares four numeric groups then text on verified sources."""
    from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS

    with (
        patch(
            "oxhack2026.models.dimension_comparison._source_manifest",
            return_value=(b"{}", "a" * 64),
        ),
        patch(
            "oxhack2026.models.dimension_comparison.build_sdk_datasets",
            return_value=(dict.fromkeys(SPECIALIST_GROUP_IDS, ()), {}),
        ),
        patch(
            "oxhack2026.models.dimension_comparison.build_financial_dataset",
            return_value=((), {}),
        ),
        patch(
            "oxhack2026.models.dimension_comparison.compare_numeric_architectures",
            return_value={},
        ) as numeric,
        patch(
            "oxhack2026.models.dimension_comparison.compare_sentiment_architectures",
            return_value={},
        ) as sentiment,
        patch.object(Path, "mkdir"),
        patch.object(Path, "read_bytes", return_value=b"[]"),
        patch.object(Path, "write_bytes") as write,
    ):
        report = compare_public_architectures(Path("mock"), Path("cohort"), Path("out"))

    experiments = report["experiments"]
    assert isinstance(experiments, dict)
    assert set(experiments) == set(SPECIALIST_GROUP_IDS)
    assert numeric.call_count == 4
    sentiment.assert_called_once()
    assert report["source_manifest_sha256"] == "a" * 64
    assert report["public_serving_approved"] is False
    assert write.call_count == 2
