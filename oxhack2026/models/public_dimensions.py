"""Portable research models for observable dimensions, never success probabilities."""

import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from itertools import pairwise
from math import exp, fsum, isfinite, log, sqrt
from typing import Literal, Self

from pydantic import Field, model_validator

from oxhack2026.models.contracts import Contract
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS, SpecialistGroupId


@dataclass(frozen=True)
class DimensionRow:
    """One reconstructed numeric example with an independent future measurement.

    Attributes:
        subject_id: Exact public SDK or SEC issuer identity.
        split_group: Related subjects kept in one partition.
        origin: Last date used in predictors.
        target_end: Last date used in the outcome; not a claimed filing timestamp.
        values: Complete finite predictors in recipe feature order.
        target: Observable dimension outcome, not company survival.
    """

    subject_id: str
    split_group: str
    origin: date
    target_end: date
    values: tuple[float, ...]
    target: float


class NumericRecipe(Contract):
    """Predeclared small ridge-regression experiment.

    Attributes:
        dimension: Product dimension supported by this proxy.
        target: Exact observable target description and transform.
        feature_names: Frozen predictor order.
        train_end: Latest complete training target date.
        validation_end: Latest complete validation target date.
        test_end: Latest complete final-test target date.
        baseline_index: Feature containing the persistence prediction in target units.
        limitations: Source, selection and generalization limitations.
    """

    dimension: SpecialistGroupId
    target: str
    feature_names: tuple[str, ...]
    train_end: date
    validation_end: date
    test_end: date
    baseline_index: int
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_recipe(self) -> Self:
        if (
            not self.train_end < self.validation_end < self.test_end
            or not self.feature_names
            or len(self.feature_names) != len(set(self.feature_names))
            or not 0 <= self.baseline_index < len(self.feature_names)
        ):
            message = (
                "Numeric recipe requires ordered cutoffs and unique baseline features"
            )
            raise ValueError(message)
        return self


class NumericDimensionModel(Contract):
    """Portable standardized ridge model plus a training-outcome percentile scale.

    Attributes:
        schema_version: Frozen parameter and scoring recipe.
        recipe: Explicit features, endpoint and applicability.
        alpha: Penalty chosen using validation MAE, never final-test results.
        means: Training-only feature means.
        scales: Training-only positive feature scales.
        coefficients: Standardized regression coefficients.
        intercept: Regression intercept in target units.
        reference_targets: Sorted training outcomes for descriptive index percentiles.
        source_sha256: Digest of the retained source manifest.
        training_subjects: Subjects used for fitting, to audit separation.
        recommended_predictor: Validation-only choice of ridge or persistence.
    """

    schema_version: Literal["public-dimension-ridge-v1"] = "public-dimension-ridge-v1"
    recipe: NumericRecipe
    alpha: float
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    reference_targets: tuple[float, ...]
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    training_subjects: tuple[str, ...]
    recommended_predictor: Literal["ridge", "persistence"] = "ridge"

    @model_validator(mode="after")
    def _validate_parameters(self) -> Self:
        if (
            any(
                len(values) != len(self.recipe.feature_names)
                for values in (self.means, self.scales, self.coefficients)
            )
            or any(scale <= 0 for scale in self.scales)
            or self.alpha <= 0
            or not self.reference_targets
            or tuple(sorted(self.reference_targets)) != self.reference_targets
        ):
            message = (
                "Numeric parameters must match ordered features and reference targets"
            )
            raise ValueError(message)
        return self


class EntitySentimentModel(Contract):
    """TF-IDF multinomial logistic sentiment model without executable pickle data.

    Attributes:
        schema_version: Frozen tokenizer, context and probability recipe.
        classes: Ordered annotated sentiment names.
        vocabulary: Training-only lowercase unigram/bigram vocabulary.
        idf: Training-only inverse document frequencies.
        coefficients: Class-specific logistic coefficients in vocabulary order.
        intercepts: Class-specific logistic intercepts.
        source_sha256: Exact FinEntity raw-byte digest.
        limitations: News-domain and company-context applicability constraints.
    """

    schema_version: Literal["entity-tfidf-logistic-v1"] = "entity-tfidf-logistic-v1"
    classes: tuple[str, ...]
    vocabulary: dict[str, int]
    idf: tuple[float, ...]
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_parameters(self) -> Self:
        count = len(self.vocabulary)
        if (
            set(self.classes) != {"Positive", "Neutral", "Negative"}
            or len(self.classes) != 3
            or not count
            or set(self.vocabulary.values()) != set(range(count))
            or len(self.idf) != count
            or any(value <= 0 for value in self.idf)
            or len(self.coefficients) != 3
            or len(self.intercepts) != 3
            or any(len(row) != count for row in self.coefficients)
        ):
            message = (
                "Sentiment parameters require a complete ordered three-class vocabulary"
            )
            raise ValueError(message)
        return self


class EntityAnnotation(Contract):
    """Public dataset entity span and human sentiment annotation.

    Attributes:
        start: Inclusive source character offset.
        end: Exclusive source character offset.
        label: Human sentiment annotation for this entity, not the whole sentence.
        value: Entity surface name used for string-disjoint evaluation.
        tag: Original redundant dataset label retained during validation.
    """

    start: int
    end: int
    label: Literal["Positive", "Neutral", "Negative"]
    value: str
    tag: str


class AnnotatedNews(Contract):
    """One public FinEntity article.

    Attributes:
        content: Exact source text.
        annotations: Human entity-span annotations.
    """

    content: str
    annotations: tuple[EntityAnnotation, ...]


def subject_partition(split_group: str) -> Literal["train", "validation", "test"]:
    """Assign a stable related-subject group before outcomes are examined.

    Args:
        split_group: Stable issuer, SDK owner or annotated company identity.
    Returns:
        Deterministic 60/20/20 hash partition; actual row counts need not match.
    Raises:
        ValueError: The split-group identity is empty.
    """
    if not split_group.strip():
        message = "Partition assignment requires a nonempty subject group"
        raise ValueError(message)
    bucket = (
        int(sha256(split_group.casefold().strip().encode()).hexdigest()[:8], 16) % 10
    )
    return "train" if bucket < 6 else "validation" if bucket < 8 else "test"


def predict_numeric_dimension(
    model: NumericDimensionModel, values: Sequence[float]
) -> float:
    """Predict an observable proxy using frozen preprocessing.

    Args:
        model: Fitted portable numeric dimension model.
        values: Complete predictors in the model's declared feature order.
    Returns:
        Predicted transformed outcome; this is not a company-success probability.
    Raises:
        ValueError: Inputs are nonfinite or parameter dimensions disagree.
    """
    if len(values) != len(model.recipe.feature_names) or any(
        not isfinite(value) for value in values
    ):
        message = "Numeric dimension predictors must be finite"
        raise ValueError(message)
    if model.recommended_predictor == "persistence":
        return values[model.recipe.baseline_index]
    return model.intercept + fsum(
        coefficient * (value - mean) / scale
        for value, mean, scale, coefficient in zip(
            values, model.means, model.scales, model.coefficients, strict=True
        )
    )


def dimension_percentile(model: NumericDimensionModel, prediction: float) -> float:
    """Convert a prediction to its descriptive training-outcome midrank percentile.

    Args:
        model: Fitted model with a sorted, nonempty training reference distribution.
        prediction: Predicted outcome in the same transformed target units.
    Returns:
        A 0-100 peer-reference index, never a calibrated outcome probability.
    Raises:
        ValueError: The reference distribution is empty.
    """
    reference = model.reference_targets
    if not reference or not isfinite(prediction):
        message = "A dimension percentile requires training reference outcomes"
        raise ValueError(message)
    return (
        50
        * (bisect_left(reference, prediction) + bisect_right(reference, prediction))
        / len(reference)
    )


def _regression_metrics(
    truth: Sequence[float], predictions: Sequence[float]
) -> dict[str, float]:
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  # type: ignore[import-untyped]

    return {
        "mae": float(mean_absolute_error(truth, predictions)),
        "rmse": float(np.sqrt(mean_squared_error(truth, predictions))),
        "r2": float(r2_score(truth, predictions)),
    }


def partition_numeric_rows(
    recipe: NumericRecipe, rows: Sequence[DimensionRow]
) -> dict[str, list[DimensionRow]]:
    """Apply the frozen subject/time split before any estimator sees outcomes.

    Args:
        recipe: Frozen chronology and feature/target declaration.
        rows: Reconstructed examples with strictly future targets.
    Returns:
        Supported company-disjoint train, validation and test rows.
    Raises:
        ValueError: Origins repeat, target order reverses or support is inadequate.
    """
    if not recipe.train_end < recipe.validation_end < recipe.test_end:
        message = "Numeric recipe cutoffs must be ordered"
        raise ValueError(message)
    partitions: dict[str, list[DimensionRow]] = {
        name: [] for name in ("train", "validation", "test")
    }
    seen: set[tuple[str, date]] = set()
    for row in rows:
        key = (row.subject_id, row.origin)
        if key in seen or row.target_end <= row.origin:
            message = (
                "Numeric examples require unique origins and strictly future targets"
            )
            raise ValueError(message)
        seen.add(key)
        partition = subject_partition(row.split_group)
        lower, upper = {
            "train": (date.min, recipe.train_end),
            "validation": (recipe.train_end, recipe.validation_end),
            "test": (recipe.validation_end, recipe.test_end),
        }[partition]
        if lower < row.origin < row.target_end <= upper:
            partitions[partition].append(row)
    if any(len(partition) < 10 for partition in partitions.values()):
        message = "Each numeric partition requires at least ten eligible observations"
        raise ValueError(message)
    subjects = [
        {row.subject_id for row in partition} for partition in partitions.values()
    ]
    if any(subjects[i] & subjects[j] for i in range(3) for j in range(i)):
        message = "Numeric training, validation and test subjects must be disjoint"
        raise ValueError(message)
    return partitions


def fit_numeric_dimension(
    recipe: NumericRecipe, rows: Sequence[DimensionRow], source_sha256: str
) -> tuple[NumericDimensionModel, dict[str, object]]:
    """Fit ridge candidates and evaluate untouched later, disjoint-subject data.

    Args:
        recipe: Frozen feature, target, baseline and date definitions.
        rows: Reconstructed examples with nonoverlapping predictor/outcome windows.
        source_sha256: Retained dataset-manifest digest.
    Returns:
        Portable parameters and validation/test comparisons with a persistence baseline.
        Captures do not prove historical availability or private-company validity.
    Raises:
        ValueError: Rows, dates, support or finite numeric values are invalid.
    """
    import numpy as np
    from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
    from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

    partitions = partition_numeric_rows(recipe, rows)
    matrices = {
        name: np.array([row.values for row in partition], dtype=np.float64)
        for name, partition in partitions.items()
    }
    truth = {
        name: np.array([row.target for row in partition])
        for name, partition in partitions.items()
    }
    if any(
        values.ndim != 2
        or values.shape[1] != len(recipe.feature_names)
        or not np.isfinite(values).all()
        or not np.isfinite(truth[name]).all()
        for name, values in matrices.items()
    ):
        message = (
            "Numeric training inputs and truth must be finite and correctly ordered"
        )
        raise ValueError(message)
    scaler = StandardScaler().fit(matrices["train"])
    features = {name: scaler.transform(matrix) for name, matrix in matrices.items()}
    candidates = []
    for alpha in (0.1, 1.0, 10.0, 100.0):
        estimator = Ridge(alpha=alpha).fit(features["train"], truth["train"])
        loss = float(
            np.mean(
                np.abs(estimator.predict(features["validation"]) - truth["validation"])
            )
        )
        candidates.append((loss, alpha, estimator))
    _, alpha, estimator = min(candidates, key=lambda item: (item[0], item[1]))
    model = NumericDimensionModel(
        recipe=recipe,
        alpha=alpha,
        means=tuple(scaler.mean_.tolist()),
        scales=tuple(scaler.scale_.tolist()),
        coefficients=tuple(estimator.coef_.tolist()),
        intercept=float(estimator.intercept_),
        reference_targets=tuple(sorted(truth["train"].tolist())),
        source_sha256=source_sha256,
        training_subjects=tuple(
            sorted({row.subject_id for row in partitions["train"]})
        ),
        recommended_predictor=(
            "ridge"
            if np.mean(
                np.abs(estimator.predict(features["validation"]) - truth["validation"])
            )
            < np.mean(
                np.abs(
                    matrices["validation"][:, recipe.baseline_index]
                    - truth["validation"]
                )
            )
            else "persistence"
        ),
    )
    report: dict[str, object] = {
        "mode": "reconstructed",
        "point_in_time_validated": False,
        "counts": {name: len(partition) for name, partition in partitions.items()},
        "subjects": {
            name: sorted({row.subject_id for row in partition})
            for name, partition in partitions.items()
        },
        "validation_mae_by_alpha": {str(alpha): loss for loss, alpha, _ in candidates},
        "limitations": recipe.limitations,
        "recommended_predictor": model.recommended_predictor,
    }
    for name in ("validation", "test"):
        predictions = estimator.predict(features[name])
        baseline = matrices[name][:, recipe.baseline_index]
        report[name] = {
            "ridge": _regression_metrics(truth[name].tolist(), predictions.tolist()),
            "persistence": _regression_metrics(truth[name].tolist(), baseline.tolist()),
            "training_mean": _regression_metrics(
                truth[name].tolist(), [float(truth["train"].mean())] * len(truth[name])
            ),
            "constant_zero": _regression_metrics(
                truth[name].tolist(), [0.0] * len(truth[name])
            ),
            "beats_persistence_mae": bool(
                np.mean(np.abs(predictions - truth[name]))
                < np.mean(np.abs(baseline - truth[name]))
            ),
        }
    return model, report


def entity_context(text: str, start: int, end: int) -> str:
    """Replace the target entity with a marker and retain a bounded local context.

    Args:
        text: Source headline or news sentence.
        start: Inclusive target character offset.
        end: Exclusive target character offset.
    Returns:
        At most 160 characters on either side of a neutral target marker.
    Raises:
        ValueError: Entity offsets are outside the nonempty source span.
    """
    if not 0 <= start < end <= len(text):
        message = "Entity offsets must identify a nonempty source span"
        raise ValueError(message)
    return f"{text[max(0, start - 160) : start]} targetentity {text[end : end + 160]}"


def predict_entity_sentiment(
    model: EntitySentimentModel, contexts: Sequence[str]
) -> tuple[dict[str, float], ...]:
    """Apply portable TF-IDF and class weights to company-specific news contexts.

    Args:
        model: Frozen training vocabulary, IDF and multinomial weights.
        contexts: Entity contexts produced by entity_context, not raw mention counts.
    Returns:
        Class probability dictionaries in input order; no company-health claim.
    Raises:
        ValueError: A context is empty.
    """
    if not contexts:
        return ()
    if any(not context.strip() for context in contexts):
        message = "Sentiment inference requires nonempty company-specific text"
        raise ValueError(message)
    predictions = []
    for context in contexts:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", context.lower())
            if not unicodedata.combining(character)
        )
        tokens = re.findall(r"(?u)\b\w\w+\b", normalized)
        counts = Counter(tokens)
        counts.update(f"{left} {right}" for left, right in pairwise(tokens))
        vector = {
            index: (1 + log(count)) * model.idf[index]
            for term, count in counts.items()
            if (index := model.vocabulary.get(term)) is not None
        }
        norm = sqrt(fsum(value * value for value in vector.values())) or 1
        logits = [
            intercept
            + fsum(weights[index] * value / norm for index, value in vector.items())
            for weights, intercept in zip(
                model.coefficients, model.intercepts, strict=True
            )
        ]
        maximum = max(logits)
        exponentials = [exp(value - maximum) for value in logits]
        total = fsum(exponentials)
        predictions.append(
            dict(
                zip(
                    model.classes,
                    (value / total for value in exponentials),
                    strict=True,
                )
            )
        )
    return tuple(predictions)


def partition_sentiment_articles(
    articles: Sequence[AnnotatedNews],
) -> tuple[dict[str, list[tuple[str, str, str]]], Counter[str]]:
    """Deduplicate articles and keep entity-surface strings disjoint across splits.

    Args:
        articles: Human entity/sentiment annotations and exact source text.
    Returns:
        Context/label/entity rows and explicit article exclusion counts.
    Raises:
        ValueError: Span labels conflict, offsets fail or a partition lacks a class.
    """
    partitions: dict[str, list[tuple[str, str, str]]] = {
        name: [] for name in ("train", "validation", "test")
    }
    seen: set[str] = set()
    excluded: Counter[str] = Counter()
    for article in articles:
        identity = " ".join(article.content.casefold().split())
        if identity in seen:
            excluded["duplicate_article"] += 1
            continue
        seen.add(identity)
        assignments = {
            subject_partition(annotation.value.strip())
            for annotation in article.annotations
        }
        if len(assignments) != 1:
            excluded["cross_partition_or_empty_article"] += 1
            continue
        partition = assignments.pop()
        spans: dict[tuple[int, int], str] = {}
        for annotation in article.annotations:
            span = (annotation.start, annotation.end)
            if span in spans:
                if spans[span] != annotation.label:
                    message = "Conflicting labels for an identical entity span"
                    raise ValueError(message)
                continue
            spans[span] = annotation.label
            partitions[partition].append(
                (
                    entity_context(article.content, annotation.start, annotation.end),
                    annotation.label,
                    annotation.value.casefold().strip(),
                )
            )
    if any(
        {row[1] for row in rows} != {"Positive", "Neutral", "Negative"}
        for rows in partitions.values()
    ):
        message = "Every sentiment partition must contain all three annotated classes"
        raise ValueError(message)
    return partitions, excluded


def fit_entity_sentiment(
    articles: Sequence[AnnotatedNews], source_sha256: str
) -> tuple[EntitySentimentModel, dict[str, object]]:
    """Train an entity-specific text classifier with deduped, string-disjoint tests.

    Args:
        articles: Original human-annotated FinEntity news articles.
        source_sha256: Exact retained dataset byte digest.
    Returns:
        Portable parameters and held-out sentiment metrics, including a prior baseline.
        Entity strings and articles are disjoint; aliases/ownership are unaudited.
    Raises:
        ValueError: Offsets, contradictory annotations or partition support are invalid.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        log_loss,
    )

    partitions, excluded = partition_sentiment_articles(articles)
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        strip_accents="unicode",
        sublinear_tf=True,
        min_df=2,
        max_features=20000,
    )
    matrices = {
        "train": vectorizer.fit_transform([row[0] for row in partitions["train"]])
    }
    matrices.update(
        {
            name: vectorizer.transform([row[0] for row in partitions[name]])
            for name in ("validation", "test")
        }
    )
    truth = {name: [row[1] for row in rows] for name, rows in partitions.items()}
    candidates = []
    for regularization in (0.1, 1.0, 10.0):
        estimator = LogisticRegression(C=regularization, max_iter=2000).fit(
            matrices["train"], truth["train"]
        )
        loss = -float(
            f1_score(
                truth["validation"],
                estimator.predict(matrices["validation"]),
                average="macro",
                zero_division=0,
            )
        )
        candidates.append((loss, regularization, estimator))
    _, regularization, estimator = min(candidates, key=lambda item: (item[0], item[1]))
    limitations = (
        "Human-labeled financial news, not HN comments or company health.",
        "Entity strings are disjoint; ownership and aliases are not verified.",
        "Mixed-partition articles are excluded; subset difficulty can differ.",
        "Entity offsets and text are required; mention counts cannot give sentiment.",
    )
    model = EntitySentimentModel(
        classes=tuple(estimator.classes_.tolist()),
        vocabulary=vectorizer.vocabulary_,
        idf=tuple(vectorizer.idf_.tolist()),
        coefficients=tuple(tuple(row) for row in estimator.coef_.tolist()),
        intercepts=tuple(estimator.intercept_.tolist()),
        source_sha256=source_sha256,
        limitations=limitations,
    )
    report: dict[str, object] = {
        "target": "Human-annotated target-entity sentiment in English financial news",
        "counts": {name: len(rows) for name, rows in partitions.items()},
        "entity_counts": {
            name: len({row[2] for row in rows}) for name, rows in partitions.items()
        },
        "class_counts": {name: dict(Counter(labels)) for name, labels in truth.items()},
        "exclusions": dict(excluded),
        "selected_C": regularization,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "limitations": limitations,
    }
    class_counts = Counter(truth["train"])
    prior = np.array(
        [class_counts[label] / len(truth["train"]) for label in model.classes]
    )
    for name in ("validation", "test"):
        probabilities = estimator.predict_proba(matrices[name])
        predictions = estimator.classes_[probabilities.argmax(axis=1)]
        baseline = np.tile(prior, (len(truth[name]), 1))
        report[name] = {
            "accuracy": float(accuracy_score(truth[name], predictions)),
            "balanced_accuracy": float(
                balanced_accuracy_score(truth[name], predictions)
            ),
            "macro_f1": float(
                f1_score(truth[name], predictions, average="macro", zero_division=0)
            ),
            "log_loss": float(
                log_loss(truth[name], probabilities, labels=model.classes)
            ),
            "confusion_matrix": confusion_matrix(
                truth[name], predictions, labels=model.classes
            ).tolist(),
            "class_order": model.classes,
            "prior_accuracy": float(
                accuracy_score(
                    truth[name], [model.classes[int(prior.argmax())]] * len(truth[name])
                )
            ),
            "prior_macro_f1": float(
                f1_score(
                    truth[name],
                    [model.classes[int(prior.argmax())]] * len(truth[name]),
                    average="macro",
                    zero_division=0,
                )
            ),
            "prior_log_loss": float(
                log_loss(truth[name], baseline, labels=model.classes)
            ),
        }
    return model, report


def combine_dimension_index(
    scores: Mapping[SpecialistGroupId, float | None],
) -> float | None:
    """Calculate the user-selected equal-weight descriptive five-dimension index.

    Args:
        scores: All five named 0-100 dimension indices; missing values stay None.
    Returns:
        Arithmetic mean when all five dimensions exist, otherwise None.
        Equal weighting is a disclosed product choice, not learned success probability.
    Raises:
        ValueError: Groups are missing/extra or a score is nonfinite/outside 0-100.
    """
    if set(scores) != set(SPECIALIST_GROUP_IDS):
        message = "AScore requires exactly the five declared dimensions"
        raise ValueError(message)
    values = [value for value in scores.values() if value is not None]
    if any(
        isinstance(value, bool) or not isfinite(value) or not 0 <= value <= 100
        for value in values
    ):
        message = "Dimension scores must be finite numbers between zero and 100"
        raise ValueError(message)
    return (
        fsum(values) / len(SPECIALIST_GROUP_IDS)
        if len(values) == len(SPECIALIST_GROUP_IDS)
        else None
    )
