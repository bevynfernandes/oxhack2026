"""Training-only prevalence comparator for separate company outcome experiments."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from oxhack2026.evaluation.company_labels import (
    CompanyLabelSelection,
    select_company_labels,
)
from oxhack2026.features.company_outcomes import CompanyOutcomeId
from oxhack2026.features.definitions import require_utc
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.company_predictions import CompanyProbabilityForecast


@dataclass(frozen=True)
class CompanyPredictionOrigin:
    """Exact company/UTC origin selected by a frozen historical experiment.

    Attributes:
        company_id: Stable company identity resolved by the source owner.
        decision_at: UTC prediction cutoff, no earlier than the model fit cutoff.
    """

    company_id: str
    decision_at: datetime

    def __post_init__(self) -> None:
        """Validate request identity and time.

        Returns:
            None when the origin is valid.
        Raises:
            ValueError: Company identity is empty or decision time is not UTC.
        """
        require_utc(self.decision_at)
        if not self.company_id:
            message = "Company prediction origin requires company identity"
            raise ValueError(message)


@dataclass(frozen=True)
class CompanyPrevalenceResult:
    """Experimental baseline with exact training eligibility and exclusions.

    Attributes:
        training: Outcome-specific mature labels available at the fit cutoff.
        probability: Their observed positive fraction, without test-label fitting.
        forecasts: The same training-only probability at each requested origin.
    """

    training: CompanyLabelSelection
    probability: float
    forecasts: tuple[CompanyProbabilityForecast, ...]


def prevalence_company_forecasts(
    labels: Sequence[CompanyOutcomeLabel],
    origins: Sequence[CompanyPredictionOrigin],
    outcome_id: CompanyOutcomeId,
    fit_at: datetime,
    held_out_families: frozenset[str] = frozenset(),
) -> CompanyPrevalenceResult:
    """Predict a constant training prevalence without using future or test labels.

    Args:
        labels: Source-adjudicated explicit label vintages, never directory statuses.
        origins: Company/origin requests from an explicitly frozen experiment.
        outcome_id: Endpoint to fit independently from the other company outcomes.
        fit_at: UTC training knowledge cutoff, no later than any requested decision.
        held_out_families: Families excluded from training for transfer evaluation;
            dated family/cohort identity must be verified upstream.
    Returns:
        Eligible training rows/exclusions and deterministic experimental forecasts.
        No smoothing, test prevalence, label imputation or public release decision
        is introduced. One-class training yields zero/one, not an invented prior.
    Raises:
        ValueError: No eligible training labels exist, origins duplicate or precede
            fitting, or shared label selection rejects invalid cutoffs/vintages.
    """
    training = select_company_labels(labels, outcome_id, fit_at, held_out_families)
    if not training.labels:
        message = "Prevalence baseline requires mature observed training labels"
        raise ValueError(message)
    if any(origin.decision_at < fit_at for origin in origins):
        message = "Prevalence fitting cannot follow a requested decision"
        raise ValueError(message)
    if len({(row.company_id, row.decision_at) for row in origins}) != len(origins):
        message = "Select one baseline request per company/origin"
        raise ValueError(message)
    probability = sum(row.value is True for row in training.labels) / len(
        training.labels
    )
    return CompanyPrevalenceResult(
        training=training,
        probability=probability,
        forecasts=tuple(
            CompanyProbabilityForecast(
                origin.company_id, outcome_id, origin.decision_at, probability
            )
            for origin in sorted(
                origins, key=lambda row: (row.decision_at, row.company_id)
            )
        ),
    )
