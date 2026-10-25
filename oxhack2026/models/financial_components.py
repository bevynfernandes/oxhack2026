"""Frozen local classifier comparison for disclosed annual financial components."""

import hashlib
from datetime import date
from pathlib import Path
from typing import Protocol, Self

import joblib  # type: ignore[import-untyped]
import numpy as np
import numpy.typing as npt
import orjson
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
from sklearn.tree import DecisionTreeClassifier  # type: ignore[import-untyped]
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from oxhack2026.features.sec_financial_panel import FINANCIAL_FEATURES

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


class _Classifier(Protocol):
    def fit(self, features: FloatArray, target: IntArray) -> Self:
        """Fit on the supplied training rows and return the classifier."""
        ...

    def predict_proba(self, features: FloatArray) -> FloatArray:
        """Return two class probabilities per input row."""
        ...


def _candidates() -> dict[str, _Classifier]:
    estimators = {
        "logistic_c_0.1": LogisticRegression(C=0.1, max_iter=2000),
        "logistic_c_1": LogisticRegression(C=1, max_iter=2000),
        "decision_tree_depth_3": DecisionTreeClassifier(
            max_depth=3, min_samples_leaf=20, random_state=20261025
        ),
        "histogram_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=100,
            max_leaf_nodes=7,
            learning_rate=0.05,
            l2_regularization=1,
            random_state=20261025,
        ),
    }
    return {
        name: Pipeline(
            [
                (
                    "impute",
                    SimpleImputer(
                        strategy="median", keep_empty_features=True, add_indicator=True
                    ),
                ),
                ("scale", StandardScaler()),
                ("model", estimator),
            ]
        )
        for name, estimator in estimators.items()
    }


def _metrics(truth: IntArray, probability: FloatArray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(truth, probability)),
        "average_precision": float(average_precision_score(truth, probability)),
        "brier": float(brier_score_loss(truth, probability)),
        "log_loss": float(log_loss(truth, probability, labels=[0, 1])),
    }


def _log_loss_interval(
    truth: IntArray,
    probability: FloatArray,
    issuers: npt.NDArray[np.str_],
    baseline: float,
) -> tuple[float, float]:
    _, groups = np.unique(issuers, return_inverse=True)
    count = int(groups.max()) + 1
    random = np.random.default_rng(20261025)
    predicted = np.clip(probability, 1e-15, 1 - 1e-15)
    baseline_loss = -(truth * np.log(baseline) + (1 - truth) * np.log1p(-baseline))
    model_loss = -(truth * np.log(predicted) + (1 - truth) * np.log1p(-predicted))
    differences = [
        float(
            np.average(
                baseline_loss - model_loss,
                weights=np.bincount(random.integers(0, count, count), minlength=count)[
                    groups
                ],
            )
        )
        for _ in range(200)
    ]
    low, high = np.quantile(differences, [0.025, 0.975])
    return float(low), float(high)


def _partitions(panel: pl.DataFrame) -> dict[str, pl.DataFrame]:
    partitions = {
        name: panel.filter(
            (pl.col("partition") == name) & pl.col("target").is_not_null()
        )
        for name in ("train", "validation", "test")
    }
    seen: set[str] = set()
    for data in partitions.values():
        issuers = set(data["issuer_id"].to_list())
        if (
            len(issuers) < 10
            or issuers & seen
            or set(data["target"].to_list()) != {0, 1}
        ):
            message = "Each partition needs ten disjoint issuers and both classes"
            raise ValueError(message)
        if data.filter(pl.col("label_available_at") <= pl.col("filing_date")).height:
            message = "Financial labels must follow the origin filing"
            raise ValueError(message)
        seen.update(issuers)
    for earlier, later in (("train", "validation"), ("validation", "test")):
        latest_label = partitions[earlier]["label_available_at"].max()
        earliest_origin = partitions[later]["filing_date"].min()
        if (
            not isinstance(latest_label, date)
            or not isinstance(earliest_origin, date)
            or latest_label >= earliest_origin
        ):
            message = "Financial labels must mature before later-partition origins"
            raise ValueError(message)
    return partitions


def train_financial_component(
    panel: pl.DataFrame, output: Path, provenance: dict[str, str]
) -> dict[str, object]:
    """Fit four frozen candidates and evaluate the validation-selected model once.

    Args:
        panel: annual_financial_component_panel output for one target/cohort only.
        output: New artifact directory; existing experiments cannot be overwritten.
        provenance: Verified source/cohort/plan hashes retained by acquisition.
    Returns:
        Coverage, selection, metrics, issuer-bootstrap uncertainty and artifact
        hashes. A statistical pass alone never authorizes private-startup serving.
    Raises:
        ValueError: Target, issuer counts/independence or label maturity is invalid.
        OSError: Output cannot be created or model/evaluation files cannot be saved.
        polars.exceptions.PolarsError: Panel columns are invalid or absent.
    """
    if panel["component"].n_unique() != 1:
        message = "Train exactly one financial component per experiment"
        raise ValueError(message)
    partitions = _partitions(panel)
    features = {
        name: np.asarray(data.select(FINANCIAL_FEATURES).to_numpy(), dtype=float)
        for name, data in partitions.items()
    }
    truth = {
        name: np.asarray(data["target"].to_list(), dtype=np.int64)
        for name, data in partitions.items()
    }
    prevalence = float(truth["train"].mean())
    validation = {
        "training_prevalence": _metrics(
            truth["validation"], np.full(truth["validation"].shape, prevalence)
        )
    }
    output.mkdir(parents=True, exist_ok=False)
    panel.write_parquet(output / "panel.parquet")
    fitted = _candidates()
    artifacts = {}
    with threadpool_limits(limits=1):
        for name, model in fitted.items():
            model.fit(features["train"], truth["train"])
            validation[name] = _metrics(
                truth["validation"],
                np.asarray(
                    model.predict_proba(features["validation"])[:, 1], dtype=float
                ),
            )
            path = output / f"{name}.joblib"
            joblib.dump(model, path)
            with path.open("rb") as stream:
                artifacts[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        selected = min(validation, key=lambda name: validation[name]["log_loss"])
        probability = (
            np.full(truth["test"].shape, prevalence)
            if selected == "training_prevalence"
            else np.asarray(
                fitted[selected].predict_proba(features["test"])[:, 1], dtype=float
            )
        )
    test = _metrics(truth["test"], probability)
    baseline_test = _metrics(truth["test"], np.full(truth["test"].shape, prevalence))
    interval = _log_loss_interval(
        truth["test"],
        probability,
        np.asarray(partitions["test"]["issuer_id"].to_list(), dtype=str),
        prevalence,
    )
    baseline_validation = validation["training_prevalence"]
    result: dict[str, object] = {
        "schema_version": "sec-financial-component-v1",
        "component": panel["component"][0],
        "status": "research_models_trained",
        "eligible_for_serving": False,
        "provenance": provenance,
        "features": FINANCIAL_FEATURES,
        "coverage": panel.group_by("partition")
        .agg(
            pl.len().alias("origins"),
            pl.col("issuer_id").n_unique().alias("issuers"),
            pl.col("target").is_null().sum().alias("censored_origins"),
        )
        .sort("partition")
        .to_dicts(),
        "counts": {
            name: {
                "rows": data.height,
                "issuers": data["issuer_id"].n_unique(),
                "positive_rows": int(data["target"].sum()),
            }
            for name, data in partitions.items()
        },
        "training_prevalence": prevalence,
        "selected_model": selected,
        "validation": validation,
        "test": test,
        "test_prevalence_baseline": baseline_test,
        "test_log_loss_improvement_95pct_issuer_bootstrap": interval,
        "statistical_gate_passed": bool(
            selected != "training_prevalence"
            and interval[0] > 0
            and validation[selected]["log_loss"] < baseline_validation["log_loss"]
            and validation[selected]["brier"] < baseline_validation["brier"]
            and test["log_loss"] < baseline_test["log_loss"]
            and test["brier"] < baseline_test["brier"]
        ),
        "model_artifact_sha256": artifacts,
        "limitations": [
            "Historical US reporting issuers; not representative private startups.",
            "Targets require observed follow-up reports; attrition is not failure.",
            "Fiscal-year endpoints differ from exact calendar horizons from filing.",
            "Retrospective SEC snapshots can contain corrected source metadata.",
            "Issuer separation is not a completed corporate-family or scope audit.",
            "No operating-survival, paid-retention or complete resilience labels.",
        ],
    }
    (output / "evaluation.json").write_bytes(
        orjson.dumps(result, option=orjson.OPT_INDENT_2) + b"\n"
    )
    return result
