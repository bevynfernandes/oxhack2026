"""Company prevalence is fitted from permitted training truth, never test outcomes."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from oxhack2026.features.company_outcomes import CompanyOutcomeId, company_horizon_end
from oxhack2026.models.company_baselines import (
    CompanyPredictionOrigin,
    prevalence_company_forecasts,
)
from oxhack2026.models.company_contracts import CompanyOutcomeLabel

OUTCOME: CompanyOutcomeId = "commercial_viability_12m_v1"
FIT_AT = datetime(2025, 1, 1, tzinfo=UTC)
DECISION = datetime(2022, 1, 1, tzinfo=UTC)


def _label(company: str, truth: bool, family: str = "training") -> CompanyOutcomeLabel:
    return CompanyOutcomeLabel(
        company_id=company,
        family_id=family,
        source_snapshot_id="synthetic-labels",
        outcome_id=OUTCOME,
        decision_at=DECISION,
        horizon_end=company_horizon_end(DECISION, OUTCOME),
        evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
        label_state="observed",
        value=truth,
        available_at=company_horizon_end(DECISION, OUTCOME),
        evidence_ids=("synthetic-evidence",),
        reason_codes=() if truth else ("verified_negative_cashflow",),
    )


def test_prevalence_retains_training_scope_exclusions_and_request_order() -> None:
    """Held-out companies and unavailable labels cannot change the fitted prior."""
    delayed = CompanyOutcomeLabel.model_validate(
        _label("delayed", True).model_dump()
        | {"available_at": FIT_AT + timedelta(days=1)}
    )
    labels = [
        _label("a", True),
        _label("b", True),
        _label("c", False),
        _label("reserved", False, "held-out"),
        delayed,
    ]
    origins = [
        CompanyPredictionOrigin("z", FIT_AT),
        CompanyPredictionOrigin("a", FIT_AT),
    ]

    result = prevalence_company_forecasts(
        labels, origins, OUTCOME, FIT_AT, frozenset({"held-out"})
    )

    assert result.probability == pytest.approx(2 / 3)
    assert len(result.training.labels) == 3
    assert dict(result.training.excluded_counts) == {
        "held_out_family": 1,
        "label_not_available_at_fit": 1,
    }
    assert [row.company_id for row in result.forecasts] == ["a", "z"]
    assert all(row.probability == result.probability for row in result.forecasts)
    assert (
        prevalence_company_forecasts(
            labels[::-1], origins[::-1], OUTCOME, FIT_AT, frozenset({"held-out"})
        )
        == result
    )


def test_later_test_truth_cannot_change_training_prevalence() -> None:
    """Even observed current test truth is purged from an earlier model fit."""
    test_origin = FIT_AT
    test = CompanyOutcomeLabel.model_validate(
        _label("test", True).model_dump()
        | {
            "decision_at": test_origin,
            "horizon_end": company_horizon_end(test_origin, OUTCOME),
            "available_at": company_horizon_end(test_origin, OUTCOME),
        }
    )
    request = [CompanyPredictionOrigin("test", test_origin)]
    baseline = prevalence_company_forecasts(
        [_label("train", False), test], request, OUTCOME, FIT_AT
    )
    changed_truth = CompanyOutcomeLabel.model_validate(
        test.model_dump() | {"value": False, "reason_codes": ("negative",)}
    )
    repeated = prevalence_company_forecasts(
        [_label("train", False), changed_truth], request, OUTCOME, FIT_AT
    )

    assert baseline == repeated
    assert baseline.probability == 0
    assert dict(baseline.training.excluded_counts) == {"horizon_not_elapsed_at_fit": 1}


@pytest.mark.parametrize("truth", [True, False])
def test_one_class_training_is_not_smoothed_using_test_outcomes(truth: bool) -> None:
    """A baseline's extreme prior remains explicit for proper scoring."""
    result = prevalence_company_forecasts(
        [_label("a", truth)],
        [CompanyPredictionOrigin("target", FIT_AT)],
        OUTCOME,
        FIT_AT,
    )

    assert result.probability == float(truth)
    assert result.forecasts[0].probability == float(truth)


def test_other_outcomes_and_unknowns_never_supply_training_negatives() -> None:
    """Financing truth cannot establish commercial cash-flow prevalence."""
    base = _label("a", True)
    other: CompanyOutcomeId = "financing_or_acquisition_24m_v1"
    funding = CompanyOutcomeLabel.model_validate(
        base.model_dump()
        | {
            "outcome_id": other,
            "horizon_end": company_horizon_end(DECISION, other),
            "available_at": company_horizon_end(DECISION, other),
        }
    )
    unknown = CompanyOutcomeLabel.model_validate(
        base.model_dump()
        | {
            "label_state": "unobserved",
            "value": None,
            "available_at": None,
            "reason_codes": ("missing_financials",),
        }
    )

    with pytest.raises(ValueError, match="mature observed training labels"):
        prevalence_company_forecasts([funding, unknown], [], OUTCOME, FIT_AT)


def test_pre_fit_and_duplicate_requests_fail_explicitly() -> None:
    """Post-origin fitting cannot retroactively manufacture a baseline prediction."""
    origin = CompanyPredictionOrigin("target", FIT_AT)
    labels = [_label("a", True)]

    with pytest.raises(ValueError, match="cannot follow"):
        prevalence_company_forecasts(
            labels,
            [replace(origin, decision_at=FIT_AT - timedelta(microseconds=1))],
            OUTCOME,
            FIT_AT,
        )
    with pytest.raises(ValueError, match="one baseline request"):
        prevalence_company_forecasts(labels, [origin, origin], OUTCOME, FIT_AT)


def test_invalid_origin_identity_and_time_fail_explicitly() -> None:
    """Empty identifiers and naive request times cannot enter an experiment."""
    with pytest.raises(ValueError, match="company identity"):
        CompanyPredictionOrigin("", FIT_AT)
    with pytest.raises(ValueError, match="UTC"):
        CompanyPredictionOrigin("target", FIT_AT.replace(tzinfo=None))
