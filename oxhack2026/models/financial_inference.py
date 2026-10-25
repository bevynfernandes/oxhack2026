"""Portable local inference for the experimental annual operating-cash-flow model."""

from collections.abc import Sequence
from datetime import date, datetime
from functools import lru_cache
from hashlib import sha256
from math import exp, fsum, isfinite
from pathlib import Path
from typing import Literal, Self

import orjson
import polars as pl
from pydantic import Field, FiniteFloat, model_validator

from oxhack2026.catalog.schemas import Identifier, UtcInstant
from oxhack2026.features.sec_financial_panel import (
    FINANCIAL_FEATURES,
    annual_financial_features,
)
from oxhack2026.features.sec_financials import sec_annual_financials
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


class CashFlowResearchEstimate(Contract):
    """Evidenced experimental component, separate from approved business forecasts.

    Attributes:
        status: Explicit research-estimate status, never validated private inference.
        issuer_id: Independently verified SEC issuer CIK.
        accession_number: Original annual report supplying the financial features.
        filing_date: Publication date of that annual report.
        period_end: Fiscal reporting period end; not a prediction-origin timestamp.
        as_of: UTC collection/inference cutoff.
        target: Versioned next-fiscal-year positive operating cash flow component.
        probability: Experimental conditional probability, not a five-lane score.
        architecture: Actual locally fitted classifier used for this output.
        model_sha256: Exact bundled fitted parameter bytes used for inference.
        evaluation_sha256: Exact frozen evaluation linked by the trained parameters.
        evidence_ids: Supporting mapping, submissions and financial-fact captures.
        limitations: Conditional follow-up, cohort transfer and horizon boundaries.
    Raises:
        ValueError: Dates contradict the source availability cutoff.
    """

    status: Literal["research_estimate"] = "research_estimate"
    issuer_id: str = Field(pattern=r"^[0-9]{10}$")
    accession_number: str = Field(pattern=r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
    filing_date: date
    period_end: date
    as_of: UtcInstant
    target: Literal["positive_operating_cash_flow_1fy"] = (
        "positive_operating_cash_flow_1fy"
    )
    probability: FiniteFloat = Field(ge=0, le=1)
    architecture: Literal["regularized_logistic_regression_c_0.1"] = (
        "regularized_logistic_regression_c_0.1"
    )
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evaluation_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_ids: tuple[Identifier, ...] = Field(min_length=3)
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_source_dates(self) -> Self:
        if not self.period_end <= self.filing_date <= self.as_of.date():
            message = (
                "Cash-flow estimate requires an original filing available by cutoff"
            )
            raise ValueError(message)
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            message = "Cash-flow estimate evidence references must be unique"
            raise ValueError(message)
        return self


@lru_cache(maxsize=1)
def _bundled_cash_flow_model() -> tuple[AnnualCashFlowModel, str]:
    path = (
        Path(__file__).with_name("bundled")
        / "financial_components_v1"
        / "positive_operating_cash_flow_1fy.model.json"
    )
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != "b0c276ed3db52019056b49896fed6f5a634ecea53dfd562e04d1601aeb441767":
        message = "Bundled cash-flow model digest does not match the verified artifact"
        raise ValueError(message)
    return AnnualCashFlowModel.model_validate(orjson.loads(raw)), digest


def estimate_annual_cash_flow(
    payload: object,
    filings: pl.DataFrame,
    issuer_id: str,
    as_of: datetime,
    evidence_ids: tuple[str, ...],
) -> CashFlowResearchEstimate:
    """Run the fitted research model on original-accession live financial features.

    Args:
        payload: Retained SEC companyfacts response for the verified issuer.
        filings: Complete original annual metadata from sec_annual_filing_metadata.
        issuer_id: Independently verified ten-digit CIK for the researched business.
        as_of: Aware UTC cutoff; latest annual period must be at most 550 days old.
        evidence_ids: Distinct retained mapping, submissions and fact evidence IDs.
    Returns:
        Evidenced, explicitly experimental next-fiscal-year cash-flow probability.
        This does not authorize an Overall score or private-startup forecasting.
    Raises:
        ValueError: Identity, facts, dates or model integrity fail; origin revenue,
            operating cash flow and assets are absent; or latest report is stale.
        TypeError: Source JSON structure is invalid.
        OSError: Bundled trained parameters cannot be read.
        polars.exceptions.PolarsError: Source frames cannot be processed.
    """
    observations = sec_annual_financials(payload, filings, issuer_id, as_of.date())
    latest = annual_financial_features(observations).tail(1)
    if latest.is_empty():
        message = "sec_no_original_annual_financials"
        raise ValueError(message)
    period_end = latest["period_end"][0]
    if (as_of.date() - period_end).days > 550:
        message = "sec_financial_statement_stale"
        raise ValueError(message)
    revenue, cash_flow, assets = latest.select(
        "revenue", "operating_cash_flow", "assets"
    ).row(0)
    if (
        revenue is None
        or revenue <= 0
        or cash_flow is None
        or assets is None
        or assets <= 0
    ):
        message = "sec_model_requires_origin_revenue_cash_flow_and_assets"
        raise ValueError(message)
    model, digest = _bundled_cash_flow_model()
    return CashFlowResearchEstimate(
        issuer_id=issuer_id,
        accession_number=latest["accession_number"][0],
        filing_date=latest["filing_date"][0],
        period_end=period_end,
        as_of=as_of,
        probability=predict_annual_cash_flow(
            model, latest.select(FINANCIAL_FEATURES).row(0)
        ),
        model_sha256=digest,
        evaluation_sha256=model.evaluation_sha256,
        evidence_ids=evidence_ids,
        limitations=(
            "Exploratory public-issuer model; not validated for private startups.",
            "Next-fiscal-year positive cash flow, conditional on observed follow-up.",
            "Fiscal-year endpoint differs from 12 months after this report.",
            "Test covered 25 issuers; corporate-family/scope review is incomplete.",
            "This component does not measure survival, unrestricted runway or Overall.",
        ),
    )
