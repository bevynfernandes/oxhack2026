"""Portable cash-flow inference validates transforms and preserves missing inputs."""

from math import exp

import pytest
from pydantic import ValidationError

from oxhack2026.features.sec_financial_panel import FINANCIAL_FEATURES
from oxhack2026.models.financial_inference import (
    AnnualCashFlowModel,
    predict_annual_cash_flow,
)


def _model() -> AnnualCashFlowModel:
    return AnnualCashFlowModel(
        feature_names=FINANCIAL_FEATURES,
        medians=(2.0,) * 9,
        indicator_indices=(0,),
        means=(1.0,) * 9 + (0.0,),
        scales=(2.0,) * 10,
        coefficients=(1.0,) + (0.0,) * 8 + (-2.0,),
        intercept=0.5,
        training_artifact_sha256="0" * 64,
        evaluation_sha256="1" * 64,
    )


def test_training_transform_order_and_missing_indicator_affect_inference() -> None:
    """Imputation precedes indicator expansion, centering, scaling and logit."""
    observed = predict_annual_cash_flow(_model(), [2.0] * 9)
    missing = predict_annual_cash_flow(_model(), [None] + [2.0] * 8)
    assert observed == pytest.approx(1 / (1 + exp(-1)))
    assert missing == pytest.approx(0.5)
    assert _model().eligible_for_serving is False


@pytest.mark.parametrize("value", [-1e6, 1e6])
def test_large_finite_logits_do_not_overflow_sigmoid(value: float) -> None:
    """Both logistic tails remain bounded without evaluating an overflowing exp."""
    result = predict_annual_cash_flow(_model(), [value] + [2.0] * 8)
    assert 0 <= result <= 1


@pytest.mark.parametrize(
    "invalid", ["order", "length", "scale", "indicator", "release"]
)
def test_invalid_model_layout_and_release_claim_are_rejected(invalid: str) -> None:
    """Malformed transforms and a production-authority claim cannot validate."""
    payload = _model().model_dump()
    if invalid == "order":
        payload["feature_names"] = tuple(reversed(FINANCIAL_FEATURES))
    elif invalid == "length":
        payload["medians"] = (2.0,) * 8
    elif invalid == "scale":
        payload["scales"] = (0.0,) * 10
    elif invalid == "indicator":
        payload["indicator_indices"] = (9,)
    else:
        payload["eligible_for_serving"] = True
    with pytest.raises(ValidationError):
        AnnualCashFlowModel.model_validate(payload)


@pytest.mark.parametrize("features", [[1.0], [float("nan")] * 9, [float("inf")] * 9])
def test_invalid_inputs_do_not_generate_a_probability(
    features: list[float],
) -> None:
    """A damaged feature vector must fail before producing an apparent score."""
    with pytest.raises(ValueError):
        predict_annual_cash_flow(_model(), features)
