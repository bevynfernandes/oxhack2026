"""Research-only bankruptcy classifiers from public annual-report timing metadata."""

import argparse
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
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from oxhack2026.features.disclosure_timing import (
    DISCLOSURE_TIMING_FEATURES,
    disclosure_timing_frame,
)

SOURCE_SHA256 = "bde2184a88e3130e1dec7e06b2e04072c23adced0ef36f323e3bdd600a5d1608"
FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


class _Classifier(Protocol):
    def fit(self, features: FloatArray, truth: IntArray) -> Self:
        """Fit on the supplied numeric features and binary targets; return self."""
        ...

    def predict_proba(self, features: FloatArray) -> FloatArray:
        """Return two class probabilities for each supplied numeric feature row."""
        ...


def disclosure_bankruptcy_panel(source: pl.DataFrame) -> pl.DataFrame:
    """Join causal disclosure features to a recorded next-calendar-year filing.

    Args:
        source: Original ECL CSV read with String columns, preserving event dates.
    Returns:
        Eligible rows, source references, event targets and frozen partitions.
        Unused origins remain explicitly excluded. No source event is a feature.
    Raises:
        polars.exceptions.PolarsError: The source schema or dates are invalid.
        ValueError: No usable annual filing history exists.
    """
    dates = [f"bankruptcy_date_{number}" for number in (1, 2, 3)]
    frame = source.with_columns(
        pl.col("cik").str.replace(r"\.0$", "").str.zfill(10).alias("issuer_id"),
        pl.col("filing_date").str.to_date(strict=False),
        pl.col("period_of_report").str.to_date(strict=False).alias("period_end"),
        *[pl.col(name).str.to_date(strict=False) for name in dates],
    ).filter(
        pl.col("filing_date").is_not_null()
        & pl.col("period_end").is_not_null()
        & (pl.col("filing_date") >= pl.col("period_end"))
        & pl.col("issuer_id").str.contains(r"^[0-9]{10}$")
    )
    conflicting = (
        frame.group_by("issuer_id", "filing_date")
        .agg(pl.col("period_end").n_unique().alias("periods"))
        .filter(pl.col("periods") > 1)
        .select("issuer_id", "filing_date")
    )
    frame = frame.join(conflicting, on=["issuer_id", "filing_date"], how="anti")
    history = disclosure_timing_frame(
        frame.select("issuer_id", "filing_date", "period_end")
    )
    if history.is_empty():
        message = "No usable annual filing history"
        raise ValueError(message)
    buckets = pl.DataFrame(
        [
            {
                "issuer_id": issuer,
                "bucket": hashlib.sha256(issuer.encode()).digest()[0] % 10,
            }
            for issuer in history["issuer_id"].unique().to_list()
        ]
    )
    frame = (
        frame.join(history, on=["issuer_id", "filing_date", "period_end"])
        .join(buckets, on="issuer_id")
        .with_columns(pl.col("filing_date").dt.offset_by("1y").alias("label_end"))
    )
    before = pl.any_horizontal(
        *[(pl.col(name) <= pl.col("filing_date")).fill_null(False) for name in dates]
    )
    target = pl.any_horizontal(
        *[
            (
                (pl.col(name) > pl.col("filing_date"))
                & (pl.col(name) <= pl.col("label_end"))
            ).fill_null(False)
            for name in dates
        ]
    )
    frame = frame.with_columns(target.cast(pl.Int8).alias("target")).filter(
        pl.col("qualified").eq("Yes")
        & pl.col("can_label").eq("True")
        & ~before
        & (pl.col("target") == pl.col("label").eq("True").cast(pl.Int8))
    )
    return (
        frame.with_columns(
            pl.when(
                (pl.col("bucket") <= 5)
                & (pl.col("filing_date") <= pl.date(2006, 12, 31))
                & (pl.col("label_end") < pl.date(2008, 1, 1))
            )
            .then(pl.lit("train"))
            .when(
                pl.col("bucket").is_between(6, 7)
                & pl.col("filing_date").dt.year().is_between(2008, 2013)
                & (pl.col("label_end") < pl.date(2015, 1, 1))
            )
            .then(pl.lit("validation"))
            .when(
                pl.col("bucket").is_between(8, 9)
                & pl.col("filing_date").dt.year().is_between(2015, 2017)
            )
            .then(pl.lit("test"))
            .otherwise(pl.lit("excluded"))
            .alias("partition")
        )
        .unique(subset=["issuer_id", "filing_date", "period_end"])
        .sort("issuer_id", "filing_date")
    )


def _metrics(truth: IntArray, probability: FloatArray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(truth, probability)),
        "average_precision": float(average_precision_score(truth, probability)),
        "brier": float(brier_score_loss(truth, probability)),
        "log_loss": float(log_loss(truth, probability, labels=[0, 1])),
    }


def _precision_interval(
    truth: IntArray, probability: FloatArray, issuers: npt.NDArray[np.str_]
) -> tuple[float, float]:
    _, groups = np.unique(issuers, return_inverse=True)
    count = int(groups.max()) + 1
    random = np.random.default_rng(20261025)
    differences = []
    for _ in range(200):
        weights = np.bincount(random.integers(0, count, count), minlength=count)[groups]
        if weights[truth == 1].sum() == 0 or weights[truth == 0].sum() == 0:
            continue
        prevalence = float(np.average(truth, weights=weights))
        differences.append(
            float(average_precision_score(truth, probability, sample_weight=weights))
            - prevalence
        )
    low, high = np.quantile(differences, [0.025, 0.975])
    return float(low), float(high)


def train_disclosure_risk(
    panel: pl.DataFrame, output: Path, source_sha256: str
) -> dict[str, object]:
    """Fit the frozen candidate set sequentially, then evaluate one chosen model.

    Args:
        panel: Output of disclosure_bankruptcy_panel, with frozen issuer/time cuts.
        output: New directory for fitted local artifacts, panel and JSON evaluation.
        source_sha256: Digest of the input CSV verified by the calling acquisition.
    Returns:
        Selection, held-out metrics, uncertainty and explicit research-only status.
        Saved joblib files contain locally fitted weights; never load untrusted ones.
    Raises:
        ValueError: Event counts, temporal maturity or issuer independence fail.
        OSError: Artifact writes fail or output already exists.
        polars.exceptions.PolarsError: Panel columns are invalid.
    """
    names = ("train", "validation", "test")
    partitions = {name: panel.filter(pl.col("partition") == name) for name in names}
    counts = {}
    previous_issuers: set[str] = set()
    for name, data in partitions.items():
        issuers = set(data["issuer_id"].to_list())
        positives = data.filter(pl.col("target") == 1)["issuer_id"].n_unique()
        negatives = data.filter(pl.col("target") == 0)["issuer_id"].n_unique()
        minimum = 20 if name == "train" else 10
        if issuers & previous_issuers or min(positives, negatives) < minimum:
            message = "Disclosure benchmark lacks independent issuers or event counts"
            raise ValueError(message)
        previous_issuers.update(issuers)
        counts[name] = {
            "rows": data.height,
            "issuers": len(issuers),
            "positive_issuers": positives,
            "positive_rows": int(data["target"].sum()),
        }
    for earlier, later in (("train", "validation"), ("validation", "test")):
        latest_label = partitions[earlier]["label_end"].max()
        earliest_origin = partitions[later]["filing_date"].min()
        if (
            not isinstance(latest_label, date)
            or not isinstance(earliest_origin, date)
            or latest_label >= earliest_origin
        ):
            message = "Labels must mature before later-partition prediction origins"
            raise ValueError(message)
    features = {
        name: np.asarray(
            data.select(DISCLOSURE_TIMING_FEATURES).to_numpy(), dtype=float
        )
        for name, data in partitions.items()
    }
    truth = {
        name: np.asarray(data["target"].to_list(), dtype=np.int64)
        for name, data in partitions.items()
    }
    prevalence = float(truth["train"].mean())
    baseline_validation = _metrics(
        truth["validation"], np.full(len(truth["validation"]), prevalence)
    )
    output.mkdir(parents=True, exist_ok=False)
    panel.write_parquet(output / "panel.parquet")
    candidates: list[tuple[str, _Classifier]] = [
        (
            f"logistic_c_{penalty}",
            Pipeline(
                [
                    (
                        "impute",
                        SimpleImputer(strategy="median", keep_empty_features=True),
                    ),
                    ("scale", StandardScaler()),
                    ("model", LogisticRegression(C=penalty, max_iter=2000)),
                ]
            ),
        )
        for penalty in (0.01, 0.1, 1.0)
    ]
    candidates.append(
        (
            "histogram_gradient_boosting",
            Pipeline(
                [
                    (
                        "model",
                        HistGradientBoostingClassifier(
                            max_iter=100,
                            max_leaf_nodes=7,
                            learning_rate=0.05,
                            l2_regularization=1.0,
                            random_state=20261025,
                        ),
                    ),
                ]
            ),
        )
    )
    validation = {"training_prevalence": baseline_validation}
    fitted: dict[str, _Classifier] = {}
    artifacts = {}
    with threadpool_limits(limits=1):
        for name, model in candidates:
            model.fit(features["train"], truth["train"])
            probabilities = np.asarray(
                model.predict_proba(features["validation"])[:, 1], dtype=float
            )
            validation[name] = _metrics(truth["validation"], probabilities)
            fitted[name] = model
            path = output / f"{name}.joblib"
            joblib.dump(model, path)
            with path.open("rb") as stream:
                artifacts[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        selected = min(validation, key=lambda name: validation[name]["log_loss"])
        prediction = (
            np.full(len(truth["test"]), prevalence)
            if selected == "training_prevalence"
            else np.asarray(
                fitted[selected].predict_proba(features["test"])[:, 1], dtype=float
            )
        )
    baseline_test = _metrics(truth["test"], np.full(len(truth["test"]), prevalence))
    test_metrics = _metrics(truth["test"], prediction)
    interval = _precision_interval(
        truth["test"],
        prediction,
        np.asarray(partitions["test"]["issuer_id"].to_list(), dtype=str),
    )
    result: dict[str, object] = {
        "schema_version": "disclosure-bankruptcy-experiment-v1",
        "status": "research_models_trained",
        "eligible_for_serving": False,
        "target": "Recorded next-calendar-year Chapter 7/11 filing in the ECL cohort",
        "source_sha256": source_sha256,
        "features": DISCLOSURE_TIMING_FEATURES,
        "counts": counts,
        "training_prevalence": prevalence,
        "validation": validation,
        "selected_model": selected,
        "test": test_metrics,
        "test_prevalence_baseline": baseline_test,
        "test_ap_improvement_95pct_issuer_bootstrap": interval,
        "statistical_gate_passed": bool(
            interval[0] > 0
            and validation[selected]["brier"] < baseline_validation["brier"]
            and validation[selected]["log_loss"] < baseline_validation["log_loss"]
            and test_metrics["brier"] < baseline_test["brier"]
            and test_metrics["log_loss"] < baseline_test["log_loss"]
            and selected != "training_prevalence"
        ),
        "model_artifact_sha256": artifacts,
        "limitations": [
            "Selected US reporting firms, not private startups or all bankruptcies.",
            "Recorded Chapter 11 is not permanent operating-business cessation.",
            "Issuer identities are disjoint; historical corporate families unaudited.",
            "Independent event audit and live source parity still required.",
            (
                f"Only {counts['test']['positive_issuers']} positive test issuers; "
                "interval uncertainty remains material."
            ),
            "Disclosure timing is not a complete financial-health measurement.",
        ],
    }
    (output / "evaluation.json").write_bytes(
        orjson.dumps(result, option=orjson.OPT_INDENT_2)
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    with arguments.source.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != SOURCE_SHA256:
            message = "Use the pinned ECL source or explicitly version a new experiment"
            raise ValueError(message)
    data = pl.read_csv(arguments.source, infer_schema_length=0)
    train_disclosure_risk(
        disclosure_bankruptcy_panel(data), arguments.output, SOURCE_SHA256
    )
