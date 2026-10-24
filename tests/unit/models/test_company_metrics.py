"""Binary company metrics use mature exact joins and expose missing follow-up."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import log

import pytest

from oxhack2026.evaluation.company_metrics import (
    CompanyProbabilityForecast,
    evaluate_company_probabilities,
)
from oxhack2026.features.company_outcomes import CompanyOutcomeId, company_horizon_end
from oxhack2026.models.company_contracts import CompanyOutcomeLabel

OUTCOME: CompanyOutcomeId = "commercial_viability_12m_v1"
DECISION = datetime(2024, 1, 1, tzinfo=UTC)
EVALUATED = datetime(2026, 1, 1, tzinfo=UTC)


def _label(company: str, truth: bool) -> CompanyOutcomeLabel:
    return CompanyOutcomeLabel(
        company_id=company,
        family_id="synthetic-family",
        source_snapshot_id="synthetic-labels",
        outcome_id=OUTCOME,
        decision_at=DECISION,
        horizon_end=company_horizon_end(DECISION, OUTCOME),
        evaluated_at=EVALUATED,
        label_state="observed",
        value=truth,
        available_at=company_horizon_end(DECISION, OUTCOME),
        evidence_ids=("synthetic-evidence",),
        reason_codes=() if truth else ("verified_negative_cashflow",),
    )


def _forecast(company: str, probability: float) -> CompanyProbabilityForecast:
    return CompanyProbabilityForecast(company, OUTCOME, DECISION, probability)


def test_scores_and_reliability_use_the_same_exact_matches() -> None:
    """Known four-row experiment has hand-computable proper scores and tied AUC."""
    labels = [
        _label("a", False),
        _label("b", True),
        _label("c", False),
        _label("d", True),
    ]
    predictions = [
        _forecast("a", 0.1),
        _forecast("b", 0.5),
        _forecast("c", 0.5),
        _forecast("d", 0.9),
    ]

    result = evaluate_company_probabilities(predictions, labels, OUTCOME, EVALUATED)

    assert result.matched_count == result.eligible_label_count == 4
    assert result.brier_score == pytest.approx(0.13)
    assert result.log_loss == pytest.approx(-(2 * log(0.9) + 2 * log(0.5)) / 4)
    assert result.roc_auc == 0.875
    assert result.positive_count == 2
    assert result.company_count == 4
    assert result.family_count == result.origin_count == 1
    assert (
        result.forecasts_without_eligible_label == result.labels_without_forecast == 0
    )
    middle = result.calibration[5]
    assert (middle.lower, middle.upper, middle.count) == (0.5, 0.6, 2)
    assert middle.mean_probability == middle.observed_rate == 0.5
    assert result.calibration[0].mean_probability is None
    assert sum(row.count for row in result.calibration) == result.matched_count
    assert (
        evaluate_company_probabilities(
            predictions[::-1], labels[::-1], OUTCOME, EVALUATED
        )
        == result
    )


def test_unknown_follow_up_and_abstention_are_counted_separately() -> None:
    """Unknown companies neither become negatives nor disappear from coverage."""
    known = _label("known", True)
    abstained = _label("abstained", False)
    unknown = CompanyOutcomeLabel.model_validate(
        _label("unknown", False).model_dump()
        | {
            "label_state": "unobserved",
            "value": None,
            "available_at": None,
            "reason_codes": ("no_follow_up",),
        }
    )
    delayed = CompanyOutcomeLabel.model_validate(
        _label("delayed", True).model_dump() | {"available_at": EVALUATED}
    )
    predictions = [
        _forecast(company, 0.8) for company in ("known", "unknown", "delayed")
    ]

    result = evaluate_company_probabilities(
        predictions,
        [known, abstained, unknown, delayed],
        OUTCOME,
        EVALUATED - timedelta(microseconds=1),
    )

    assert result.matched_count == 1
    assert result.forecasts_without_eligible_label == 2
    assert result.labels_without_forecast == 1
    assert dict(result.label_exclusions) == {
        "unobserved": 1,
        "label_not_available_at_fit": 1,
    }
    assert result.brier_score == pytest.approx(0.04)
    assert result.roc_auc is None


def test_no_mature_matches_produces_undefined_metrics_not_perfect_scores() -> None:
    """An empty or immature cohort never receives zero error or a false AUC."""
    label = _label("a", True)

    result = evaluate_company_probabilities(
        [_forecast("a", 0.9)],
        [label],
        OUTCOME,
        label.horizon_end - timedelta(microseconds=1),
    )

    assert result.matched_count == result.eligible_label_count == 0
    assert result.brier_score is result.log_loss is result.roc_auc is None
    assert dict(result.label_exclusions) == {"horizon_not_elapsed_at_fit": 1}
    assert len(result.calibration) == 10
    assert all(
        row.count == 0 and row.observed_rate is None for row in result.calibration
    )


@pytest.mark.parametrize(
    "probabilities,auc", [((0.5, 0.5), 0.5), ((1.0, 0.0), 0.0), ((0.0, 1.0), 1.0)]
)
def test_auc_ties_reverse_and_perfect_ordering(
    probabilities: tuple[float, float], auc: float
) -> None:
    """AUC uses positive-negative pairs with half credit for exact ties."""
    result = evaluate_company_probabilities(
        [
            _forecast("negative", probabilities[0]),
            _forecast("positive", probabilities[1]),
        ],
        [_label("negative", False), _label("positive", True)],
        OUTCOME,
        EVALUATED,
    )

    assert result.roc_auc == auc
    assert result.calibration[-1].upper == 1.0
    assert result.log_loss is not None
    if probabilities == (1.0, 0.0):
        assert result.brier_score == 1.0
        assert result.log_loss > 34


def test_other_outcomes_are_never_pooled_and_origins_never_cross_join() -> None:
    """An outcome/company match alone is insufficient without the exact decision."""
    forecast = _forecast("a", 0.4)
    other = replace(forecast, outcome_id="operating_growth_24m_v1")
    later = replace(forecast, decision_at=DECISION + timedelta(days=1))

    result = evaluate_company_probabilities(
        [other, later],
        [_label("a", True)],
        OUTCOME,
        EVALUATED,
    )

    assert result.forecast_count == result.forecasts_without_eligible_label == 1
    assert result.labels_without_forecast == 1
    assert result.matched_count == 0


def test_duplicate_predictions_and_label_vintages_are_rejected() -> None:
    """A duplicated vintage cannot silently reweight scores or pick favorable truth."""
    forecast = _forecast("a", 0.5)
    label = _label("a", True)

    with pytest.raises(ValueError, match="one experimental probability"):
        evaluate_company_probabilities(
            [forecast, forecast], [label], OUTCOME, EVALUATED
        )
    with pytest.raises(ValueError, match="one explicit label vintage"):
        evaluate_company_probabilities([forecast], [label, label], OUTCOME, EVALUATED)


@pytest.mark.parametrize("probability", [-0.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_probabilities_fail_before_scoring(probability: float) -> None:
    """Nonfinite, Boolean and out-of-range inputs are never clipped into validity."""
    with pytest.raises(ValueError, match="finite and within"):
        _forecast("a", probability)


def test_invalid_identity_and_naive_decision_fail_explicitly() -> None:
    """Experiments retain the same UTC and identity requirements as labels."""
    with pytest.raises(ValueError, match="company and outcome"):
        _forecast("", 0.5)
    with pytest.raises(ValueError, match="UTC"):
        replace(_forecast("a", 0.5), decision_at=DECISION.replace(tzinfo=None))
