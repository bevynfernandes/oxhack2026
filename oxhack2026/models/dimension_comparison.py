"""Sequential architecture comparisons on fixed public dimension datasets."""

import logging
import pickle
from collections.abc import Sequence
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Protocol, Self, cast
from warnings import catch_warnings, simplefilter

import numpy as np
import orjson
from pydantic import TypeAdapter

from oxhack2026.models.dimension_datasets import (
    build_financial_dataset,
    build_sdk_datasets,
)
from oxhack2026.models.public_dimensions import (
    AnnotatedNews,
    DimensionRow,
    NumericRecipe,
    partition_numeric_rows,
    partition_sentiment_articles,
)
from oxhack2026.models.public_training import _source_manifest, public_dimension_recipes

_LOGGER = logging.getLogger(__name__)


class _Estimator(Protocol):
    def fit(self, values: object, truth: object) -> Self: ...

    def predict(self, values: object) -> object: ...


class _Classifier(_Estimator, Protocol):
    classes_: object

    def predict_proba(self, values: object) -> object: ...


def _regressors() -> list[tuple[str, _Estimator]]:
    from catboost import CatBoostRegressor  # type: ignore[import-untyped]
    from sklearn.dummy import DummyRegressor  # type: ignore[import-untyped]
    from sklearn.ensemble import (  # type: ignore[import-untyped]
        ExtraTreesRegressor,
        HistGradientBoostingRegressor,
        RandomForestRegressor,
    )
    from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge  # type: ignore[import-untyped]
    from sklearn.neural_network import MLPRegressor  # type: ignore[import-untyped]
    from sklearn.pipeline import make_pipeline  # type: ignore[import-untyped]
    from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
    from sklearn.svm import SVR  # type: ignore[import-untyped]
    from sklearn.tree import DecisionTreeRegressor  # type: ignore[import-untyped]

    estimators: list[tuple[str, object]] = [
        ("training_mean", DummyRegressor(strategy="mean")),
        ("training_median", DummyRegressor(strategy="median")),
        *((f"ridge_{alpha}", Ridge(alpha=alpha)) for alpha in (0.1, 1, 10, 100)),
        ("elastic_net", ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=10000)),
        ("huber", HuberRegressor(alpha=0.01, max_iter=1000)),
        (
            "decision_tree",
            DecisionTreeRegressor(max_depth=3, min_samples_leaf=10, random_state=42),
        ),
        (
            "random_forest",
            RandomForestRegressor(
                n_estimators=100,
                max_depth=4,
                min_samples_leaf=10,
                random_state=42,
                n_jobs=1,
            ),
        ),
        (
            "extra_trees",
            ExtraTreesRegressor(
                n_estimators=100,
                max_depth=4,
                min_samples_leaf=10,
                random_state=42,
                n_jobs=1,
            ),
        ),
        (
            "hist_gradient_boosting",
            HistGradientBoostingRegressor(
                max_iter=150,
                max_leaf_nodes=7,
                min_samples_leaf=10,
                l2_regularization=5,
                learning_rate=0.05,
                early_stopping=False,
                random_state=42,
            ),
        ),
        (
            "catboost",
            CatBoostRegressor(
                iterations=200,
                depth=3,
                learning_rate=0.03,
                l2_leaf_reg=5,
                thread_count=1,
                random_seed=42,
                verbose=False,
                allow_writing_files=False,
            ),
        ),
        ("rbf_svr", SVR(C=1, epsilon=0.1)),
        (
            "small_mlp",
            MLPRegressor(
                hidden_layer_sizes=(16, 8),
                alpha=0.1,
                solver="lbfgs",
                max_iter=1000,
                max_fun=20000,
                random_state=42,
            ),
        ),
    ]
    return [
        (name, cast(_Estimator, make_pipeline(StandardScaler(), estimator)))
        for name, estimator in estimators
    ]


def _classification_metrics(
    truth: object, probabilities: object, classes: object
) -> dict[str, object]:
    from sklearn.metrics import (  # type: ignore[import-untyped]
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        log_loss,
    )

    probabilities = np.asarray(probabilities, dtype=np.float64)
    classes = np.asarray(classes)
    predictions = classes[probabilities.argmax(axis=1)]
    return {
        "accuracy": float(accuracy_score(truth, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predictions)),
        "macro_f1": float(
            f1_score(truth, predictions, average="macro", zero_division=0)
        ),
        "log_loss": float(log_loss(truth, probabilities, labels=classes)),
        "class_order": classes.tolist(),
        "confusion_matrix": confusion_matrix(
            truth, predictions, labels=classes
        ).tolist(),
    }


def _regression_metrics(truth: object, prediction: object) -> dict[str, float]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    return {
        "mae": float(mean_absolute_error(truth, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(truth, prediction))),
        "r2": float(r2_score(truth, prediction)),
    }


def compare_numeric_architectures(
    recipe: NumericRecipe,
    rows: Sequence[DimensionRow],
    output: Path,
) -> dict[str, object]:
    """Fit fifteen fixed numeric candidates sequentially, choosing by validation MAE.

    Args:
        recipe: Shared frozen feature, outcome and subject/time split definitions.
        rows: Same reconstructed data used by the interpretable baseline experiment.
        output: Retained trusted-local candidate weights and comparison directory.
    Returns:
        Every validation/test result, fitting failure and validation-only selection.
        Earlier test results were inspected, so this is exploratory model comparison,
        not a new confirmatory evaluation or public serving approval.
    Raises:
        ValueError: Data partitions or finite feature/target values are invalid.
        OSError: Artifacts cannot be retained.
    """
    from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]

    partitions = partition_numeric_rows(recipe, rows)
    features = {
        name: np.array([row.values for row in values])
        for name, values in partitions.items()
    }
    truth = {
        name: np.array([row.target for row in values])
        for name, values in partitions.items()
    }
    if any(
        values.ndim != 2
        or values.shape[1] != len(recipe.feature_names)
        or not np.isfinite(values).all()
        or not np.isfinite(truth[name]).all()
        for name, values in features.items()
    ):
        message = "Architecture comparison requires finite, correctly ordered inputs"
        raise ValueError(message)
    output.mkdir(parents=True, exist_ok=True)
    candidates: dict[str, dict[str, object]] = {}
    losses = []
    for order, (name, estimator) in enumerate(_regressors()):
        try:
            with catch_warnings():
                simplefilter("error", ConvergenceWarning)
                estimator.fit(features["train"], truth["train"])
        except (ConvergenceWarning, ValueError, np.linalg.LinAlgError) as error:
            _LOGGER.error(
                "%s/%s fit failed: %s",
                recipe.dimension,
                name,
                type(error).__name__,
                exc_info=True,
            )
            candidates[name] = {"status": "fit_failed", "reason": type(error).__name__}
            continue
        validation = _regression_metrics(
            truth["validation"], estimator.predict(features["validation"])
        )
        test = _regression_metrics(truth["test"], estimator.predict(features["test"]))
        content = pickle.dumps(estimator, protocol=pickle.HIGHEST_PROTOCOL)
        model_path = output / f"{recipe.dimension}-{name}.trusted-local.pkl"
        model_path.write_bytes(content)
        candidates[name] = {
            "status": "fitted",
            "validation": validation,
            "test": test,
            "model_path": str(model_path),
            "model_sha256": sha256(content).hexdigest(),
            "model_format": "Python pickle, own trusted-local research artifact only",
        }
        losses.append((validation["mae"], order, name))
    for name, predictions in (
        (
            "persistence",
            {
                split: values[:, recipe.baseline_index]
                for split, values in features.items()
            },
        ),
        (
            "constant_zero",
            {split: np.zeros(len(values)) for split, values in features.items()},
        ),
    ):
        validation = _regression_metrics(truth["validation"], predictions["validation"])
        candidates[name] = {
            "status": "baseline",
            "validation": validation,
            "test": _regression_metrics(truth["test"], predictions["test"]),
        }
        losses.append((validation["mae"], -1, name))
    selected = min(losses)[2]
    report: dict[str, object] = {
        "recipe": recipe.model_dump(mode="json"),
        "counts": {name: len(values) for name, values in partitions.items()},
        "subject_counts": {
            name: len({row.subject_id for row in values})
            for name, values in partitions.items()
        },
        "selection_metric": "validation MAE only; simpler baseline wins an exact tie",
        "selected": selected,
        "candidates": candidates,
        "test_usage": "Exploratory; previously inspected benchmark, not confirmatory",
        "public_serving_approved": False,
    }
    (output / f"{recipe.dimension}.comparison.json").write_bytes(
        orjson.dumps(report, option=orjson.OPT_INDENT_2)
    )
    return report


def _classifiers(
    groups: Sequence[str], truth: Sequence[str]
) -> list[tuple[str, _Classifier]]:
    from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold  # type: ignore[import-untyped]
    from sklearn.naive_bayes import ComplementNB, MultinomialNB  # type: ignore[import-untyped]
    from sklearn.neural_network import MLPClassifier
    from sklearn.svm import LinearSVC

    folds = tuple(GroupKFold(n_splits=3).split(np.zeros(len(truth)), truth, groups))
    estimators: list[tuple[str, object]] = [
        *(
            (
                f"logistic_{regularization}_{weight or 'natural'}",
                LogisticRegression(
                    C=regularization, class_weight=weight, max_iter=2000
                ),
            )
            for weight in (None, "balanced")
            for regularization in (0.1, 1, 10)
        ),
        ("multinomial_nb_01", MultinomialNB(alpha=0.1)),
        ("multinomial_nb_1", MultinomialNB(alpha=1)),
        ("complement_nb", ComplementNB(alpha=1)),
        (
            "calibrated_linear_svm",
            CalibratedClassifierCV(
                LinearSVC(C=1, class_weight="balanced", max_iter=5000),
                cv=folds,
                method="sigmoid",
            ),
        ),
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=100,
                max_depth=20,
                min_samples_leaf=2,
                class_weight="balanced",
                n_jobs=1,
                random_state=42,
            ),
        ),
        (
            "small_mlp",
            MLPClassifier(
                hidden_layer_sizes=(16,),
                alpha=0.1,
                max_iter=300,
                early_stopping=True,
                random_state=42,
            ),
        ),
    ]
    return [(name, cast(_Classifier, estimator)) for name, estimator in estimators]


def compare_sentiment_architectures(
    articles: Sequence[AnnotatedNews], output: Path
) -> dict[str, object]:
    """Compare twelve text classifiers using the identical training-only vocabulary.

    Args:
        articles: Original FinEntity human annotations and news text.
        output: Retained trusted-local classifier/vectorizer and metric directory.
    Returns:
        Validation macro-F1 selection and all exploratory held-out comparisons.
        SVM probability calibration uses entity-grouped folds inside training only.
    Raises:
        ValueError: The shared article split or vectorization is invalid.
        OSError: Model/evaluation artifacts cannot be retained.
    """
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

    partitions, exclusions = partition_sentiment_articles(articles)
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        strip_accents="unicode",
        sublinear_tf=True,
        min_df=2,
        max_features=20000,
    )
    features = {
        "train": vectorizer.fit_transform([row[0] for row in partitions["train"]])
    }
    features.update(
        {
            name: vectorizer.transform([row[0] for row in partitions[name]])
            for name in ("validation", "test")
        }
    )
    truth = {name: [row[1] for row in values] for name, values in partitions.items()}
    groups = [row[2] for row in partitions["train"]]
    output.mkdir(parents=True, exist_ok=True)
    candidates: dict[str, dict[str, object]] = {}
    selection = []
    for order, (name, estimator) in enumerate(_classifiers(groups, truth["train"])):
        try:
            with catch_warnings():
                simplefilter("error", ConvergenceWarning)
                estimator.fit(features["train"], truth["train"])
        except (ConvergenceWarning, ValueError) as error:
            _LOGGER.error(
                "Sentiment/%s fit failed: %s", name, type(error).__name__, exc_info=True
            )
            candidates[name] = {"status": "fit_failed", "reason": type(error).__name__}
            continue
        validation = _classification_metrics(
            truth["validation"],
            estimator.predict_proba(features["validation"]),
            estimator.classes_,
        )
        test = _classification_metrics(
            truth["test"], estimator.predict_proba(features["test"]), estimator.classes_
        )
        content = pickle.dumps(
            {"vectorizer": vectorizer, "classifier": estimator},
            protocol=pickle.HIGHEST_PROTOCOL,
        )
        path = output / f"attention_sentiment-{name}.trusted-local.pkl"
        path.write_bytes(content)
        candidates[name] = {
            "status": "fitted",
            "validation": validation,
            "test": test,
            "model_path": str(path),
            "model_sha256": sha256(content).hexdigest(),
        }
        selection.append(
            (
                -float(cast(float, validation["macro_f1"])),
                float(cast(float, validation["log_loss"])),
                order,
                name,
            )
        )
    if not selection:
        message = "No sentiment architecture converged successfully"
        raise ValueError(message)
    report: dict[str, object] = {
        "selected": min(selection)[3],
        "candidates": candidates,
        "counts": {name: len(values) for name, values in partitions.items()},
        "exclusions": dict(exclusions),
        "selection_metric": "validation macro-F1, then validation log loss",
        "test_usage": "Exploratory; previously inspected benchmark, not confirmatory",
        "public_serving_approved": False,
    }
    (output / "attention_sentiment.comparison.json").write_bytes(
        orjson.dumps(report, option=orjson.OPT_INDENT_2)
    )
    return report


def compare_public_architectures(
    root: Path, cohort_path: Path, output: Path
) -> dict[str, object]:
    """Run all architecture experiments sequentially on exactly verified public data.

    Args:
        root: Retained raw public captures.
        cohort_path: Original declared SDK cohort, unchanged by model performance.
        output: Candidate model and comparison artifact directory.
    Returns:
        Summary with source/code hashes, selected candidates and actual fit counts.
    Raises:
        ValueError: Source integrity, support or experiment definitions fail.
        OSError: Raw sources or retained artifacts cannot be accessed.
    """
    manifest, digest = _source_manifest(root, cohort_path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "sources.json").write_bytes(manifest)
    sdk, _ = build_sdk_datasets(root, cohort_path)
    financial, _ = build_financial_dataset(root)
    reports = {}
    for recipe in public_dimension_recipes():
        _LOGGER.warning("Comparing numeric architectures for %s", recipe.dimension)
        reports[recipe.dimension] = compare_numeric_architectures(
            recipe,
            financial
            if recipe.dimension == "financial_health"
            else sdk[recipe.dimension],
            output,
        )
    articles = TypeAdapter(tuple[AnnotatedNews, ...]).validate_json(
        (root / "finentity.json").read_bytes()
    )
    reports["attention_sentiment"] = compare_sentiment_architectures(articles, output)
    summary: dict[str, object] = {
        "schema_version": "public-dimension-architecture-comparison-v1",
        "source_manifest_sha256": digest,
        "code_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                Path(__file__).with_name("public_dimensions.py"),
                Path(__file__).with_name("dimension_datasets.py"),
                Path(__file__).with_name("public_training.py"),
            )
        },
        "libraries": {
            name: version(name)
            for name in ("numpy", "scikit-learn", "catboost", "polars")
        },
        "experiments": reports,
        "public_serving_approved": False,
    }
    (output / "comparison.json").write_bytes(
        orjson.dumps(summary, option=orjson.OPT_INDENT_2)
    )
    return summary
