"""Portable local inference for the experimental annual operating-cash-flow model."""

from collections.abc import Sequence
from math import exp, fsum, isfinite
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from oxhack2026.features.sec_financial_panel import FINANCIAL_FEATURES
from oxhack2026.models.contracts import Contract


class AnnualCashFlowModel(Contract):
    """Non-executable fitted logistic parameters with train-only preprocessing.

    Attributes:
        schema_version: Portable parameter layout, independent of pickle/sklearn.
        target: Positive operating cash flow in the next annual reporting period.
        status: Experimental, conditional on observed reporting follow-up.
        feature_names: Exact order from the shared annual financial feature builder.
        medians: Training-only imputation values in original feature units.
        indicator_indices: Original columns with fitted missingness indicators.
        means: Training-only centering after imputation and indicator expansion.
        scales: Positive fitted standard deviations in expanded column order.
        coefficients: Logistic weights in the same expanded/standardized order.
        intercept: Fitted log-odds intercept.
        training_artifact_sha256: Digest of the original locally fitted pipeline.
        evaluation_sha256: Digest of its frozen held-out evaluation.
        eligible_for_serving: False until source/scope and transfer checks are done.
    Raises:
        ValueError: Feature order, transformer dimensions or scales are invalid.
    """

    schema_version: Literal["annual-cash-flow-logistic-v1"] = (
        "annual-cash-flow-logistic-v1"
    )
    target: Literal["positive_operating_cash_flow_1fy"] = (
        "positive_operating_cash_flow_1fy"
    )
    status: Literal["experimental_research"] = "experimental_research"
    feature_names: tuple[str, ...]
    medians: tuple[FiniteFloat, ...]
    indicator_indices: tuple[int, ...]
    means: tuple[FiniteFloat, ...]
    scales: tuple[FiniteFloat, ...]
    coefficients: tuple[FiniteFloat, ...]
    intercept: FiniteFloat
    training_artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evaluation_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    eligible_for_serving: Literal[False] = False

    @model_validator(mode="after")
    def _validate_parameters(self) -> Self:
        expanded_count = len(FINANCIAL_FEATURES) + len(self.indicator_indices)
        if (
            self.feature_names != FINANCIAL_FEATURES
            or len(self.medians) != len(FINANCIAL_FEATURES)
            or self.indicator_indices != tuple(sorted(set(self.indicator_indices)))
            or any(
                index < 0 or index >= len(FINANCIAL_FEATURES)
                for index in self.indicator_indices
            )
            or any(
                len(values) != expanded_count
                for values in (self.means, self.scales, self.coefficients)
            )
            or any(scale <= 0 for scale in self.scales)
        ):
            message = (
                "Cash-flow parameters must match the shared feature/transform layout"
            )
            raise ValueError(message)
        return self


def predict_annual_cash_flow(
    model: AnnualCashFlowModel, features: Sequence[float | None]
) -> float:
    """Reproduce fitted logistic inference without loading executable model files.

    Args:
        model: Validated fitted parameters and frozen provenance. Research-only;
            calling this function does not approve production or population transfer.
        features: Nine shared annual financial features in model.feature_names order;
            None is missing. Verify issuer, accession, scope and availability first.
    Returns:
        Experimental conditional probability of positive next-fiscal-year operating
        cash flow. It is not operating survival, cash runway or an Overall score.
    Raises:
        ValueError: Feature count is incorrect or an input is non-finite.
    """
    if len(features) != len(FINANCIAL_FEATURES) or any(
        value is not None and not isfinite(value) for value in features
    ):
        message = "Cash-flow inference requires nine finite-or-missing financial inputs"
        raise ValueError(message)
    expanded = [
        median if value is None else value
        for value, median in zip(features, model.medians, strict=True)
    ] + [float(features[index] is None) for index in model.indicator_indices]
    log_odds = model.intercept + fsum(
        (value - mean) / scale * coefficient
        for value, mean, scale, coefficient in zip(
            expanded, model.means, model.scales, model.coefficients, strict=True
        )
    )
    if log_odds >= 0:
        return 1 / (1 + exp(-log_odds))
    exponential = exp(log_odds)
    return exponential / (1 + exponential)
