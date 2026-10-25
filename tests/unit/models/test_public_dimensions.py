"""Saved model checks use artificial examples, independently of real-data metrics."""

from datetime import date

import pytest

from oxhack2026.models.public_dimensions import (
    AnnotatedNews,
    DimensionRow,
    EntityAnnotation,
    EntitySentimentModel,
    NumericDimensionModel,
    NumericRecipe,
    combine_dimension_index,
    dimension_percentile,
    entity_context,
    fit_entity_sentiment,
    fit_numeric_dimension,
    predict_entity_sentiment,
    predict_numeric_dimension,
    subject_partition,
)
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS


def _groups(partition: str) -> list[str]:
    return [
        name
        for index in range(200)
        if subject_partition(name := f"synthetic-{index}") == partition
    ][:3]


def _numeric_rows() -> tuple[DimensionRow, ...]:
    return tuple(
        DimensionRow(
            group,
            group,
            date(year, month, 1),
            date(year, month, 20),
            (float(month), float(month * 2)),
            float(month * 3 + 2),
        )
        for partition, year in (("train", 2020), ("validation", 2022), ("test", 2024))
        for group in _groups(partition)
        for month in range(1, 7)
    )


def _recipe() -> NumericRecipe:
    return NumericRecipe(
        dimension="adoption_retention",
        target="Synthetic linear target only",
        feature_names=("first", "second"),
        baseline_index=1,
        train_end=date(2021, 1, 1),
        validation_end=date(2023, 1, 1),
        test_end=date(2025, 1, 1),
        limitations=("Synthetic test data only",),
    )


def _articles() -> tuple[AnnotatedNews, ...]:
    articles = []
    for partition in ("train", "validation", "test"):
        for group in _groups(partition):
            for label, words in (
                ("Positive", "profits excellent growth success"),
                ("Negative", "losses terrible decline bankruptcy"),
                ("Neutral", "meeting scheduled appointment statement"),
            ):
                articles.append(
                    AnnotatedNews(
                        content=f"{group} reported {words}",
                        annotations=(
                            EntityAnnotation.model_validate(
                                {
                                    "start": 0,
                                    "end": len(group),
                                    "value": group,
                                    "label": label,
                                    "tag": label,
                                }
                            ),
                        ),
                    )
                )
    return tuple(articles)


def test_numeric_fit_portable_prediction_and_reference_percentile() -> None:
    """Real ridge fitting, JSON restoration and scalar inference agree."""
    model, report = fit_numeric_dimension(_recipe(), _numeric_rows(), "a" * 64)
    restored = NumericDimensionModel.model_validate_json(model.model_dump_json())

    assert predict_numeric_dimension(restored, (3, 6)) == pytest.approx(11, abs=0.02)
    assert 0 <= dimension_percentile(restored, 11) <= 100
    assert report["counts"] == {"train": 18, "validation": 18, "test": 18}
    assert restored == model
    assert model.recommended_predictor == "ridge"


def test_final_truth_cannot_change_numeric_coefficients_or_selection() -> None:
    """Only validation chooses regularization and baseline fallback."""
    rows = _numeric_rows()
    first, _ = fit_numeric_dimension(_recipe(), rows, "a" * 64)
    changed = tuple(
        DimensionRow(
            row.subject_id,
            row.split_group,
            row.origin,
            row.target_end,
            row.values,
            -100,
        )
        if subject_partition(row.split_group) == "test"
        else row
        for row in rows
    )

    second, _ = fit_numeric_dimension(_recipe(), changed, "a" * 64)

    assert first == second


def test_invalid_numeric_rows_and_parameters_fail() -> None:
    """Missing support, duplicate origins and unsafe artifacts cannot produce scores."""
    rows = _numeric_rows()
    with pytest.raises(ValueError, match="ten"):
        fit_numeric_dimension(_recipe(), (), "a" * 64)
    with pytest.raises(ValueError, match="unique origins"):
        fit_numeric_dimension(_recipe(), (*rows, rows[0]), "a" * 64)
    model, _ = fit_numeric_dimension(_recipe(), rows, "a" * 64)
    with pytest.raises(ValueError, match="parameters"):
        NumericDimensionModel.model_validate(model.model_dump() | {"scales": (0, 1)})
    with pytest.raises(ValueError, match="finite"):
        predict_numeric_dimension(model, (float("nan"), 2))
    with pytest.raises(ValueError):
        NumericRecipe.model_validate(_recipe().model_dump() | {"baseline_index": 3})


def test_sentiment_fit_roundtrip_and_correct_target_context() -> None:
    """Portable TF-IDF inference preserves class probabilities after JSON loading."""
    model, report = fit_entity_sentiment(_articles(), "b" * 64)
    restored = EntitySentimentModel.model_validate_json(model.model_dump_json())
    context = entity_context("ACME reported excellent growth profits success", 0, 4)

    prediction = predict_entity_sentiment(restored, (context,))[0]

    assert sum(prediction.values()) == pytest.approx(1)
    assert max(prediction, key=lambda label: prediction[label]) == "Positive"
    assert predict_entity_sentiment(model, (context,)) == predict_entity_sentiment(
        restored, (context,)
    )
    assert report["counts"] == {"train": 9, "validation": 9, "test": 9}
    assert predict_entity_sentiment(model, ()) == ()


def test_sentiment_rejects_bad_spans_missing_classes_and_empty_inference() -> None:
    """Missing text or labels cannot silently produce a confident neutral score."""
    with pytest.raises(ValueError, match="offsets"):
        entity_context("ACME", 0, 9)
    with pytest.raises(ValueError, match="three"):
        fit_entity_sentiment((), "b" * 64)
    model, _ = fit_entity_sentiment(_articles(), "b" * 64)
    with pytest.raises(ValueError, match="nonempty"):
        predict_entity_sentiment(model, ("",))
    with pytest.raises(ValueError, match="vocabulary"):
        EntitySentimentModel.model_validate(model.model_dump() | {"idf": ()})


def test_portable_sentiment_matches_sklearn_unicode_tfidf_and_softmax() -> None:
    """Sparse portable inference matches the training library, including unknowns."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

    model = EntitySentimentModel(
        classes=("Negative", "Neutral", "Positive"),
        vocabulary={"targetentity": 0, "cafe": 1, "targetentity cafe": 2},
        idf=(1, 2, 3),
        coefficients=((1, -2, 0.4), (0, 0.5, -1), (-1, 2, 0.3)),
        intercepts=(0.2, 0, -0.1),
        source_sha256="a" * 64,
        limitations=("Test parameters",),
    )
    contexts = ("targetentity CAFÉ café", "targetentity cafe", "unknown words 你好")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        strip_accents="unicode",
        sublinear_tf=True,
        vocabulary=model.vocabulary,
    )
    vectorizer.idf_ = np.array(model.idf)
    logits = vectorizer.transform(contexts) @ np.array(model.coefficients).T
    logits += np.array(model.intercepts)
    logits -= logits.max(axis=1, keepdims=True)
    expected = np.exp(logits)
    expected /= expected.sum(axis=1, keepdims=True)
    actual = predict_entity_sentiment(model, contexts)
    for prediction, probabilities in zip(actual, expected, strict=True):
        assert prediction == pytest.approx(
            dict(zip(model.classes, probabilities.tolist(), strict=True)), abs=1e-14
        )


def test_index_has_explicit_equal_weights_and_abstains_on_missing_groups() -> None:
    """Missing observations do not become zero scores or renormalized weights."""
    scores = dict.fromkeys(SPECIALIST_GROUP_IDS, 80.0)
    assert combine_dimension_index(scores) == 80
    assert combine_dimension_index(scores | {"financial_health": None}) is None
    with pytest.raises(ValueError, match="five"):
        combine_dimension_index({})
    with pytest.raises(ValueError, match="finite"):
        combine_dimension_index(scores | {"financial_health": float("nan")})
    assert subject_partition("Synthetic-1") == subject_partition("synthetic-1")
    with pytest.raises(ValueError, match="nonempty"):
        subject_partition("")
