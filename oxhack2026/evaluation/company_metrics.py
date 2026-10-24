"""Descriptive binary-outcome research metrics, separate from probability serving."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from math import fsum, isfinite, log, log1p

from oxhack2026.evaluation.company_labels import LabelExclusion, select_company_labels
from oxhack2026.features.company_outcomes import COMPANY_OUTCOME_IDS, CompanyOutcomeId
from oxhack2026.features.definitions import require_utc
from oxhack2026.models.company_contracts import CompanyOutcomeLabel

LOG_LOSS_EPSILON = 1e-15
CALIBRATION_BIN_COUNT = 10


@dataclass(frozen=True)
class CompanyProbabilityForecast:
    """One experimental probability; this is not a public serving publication.

    Attributes:
        company_id: Stable identity for an exact company/origin join.
        outcome_id: One separately evaluated company endpoint.
        decision_at: UTC decision time used by the frozen experiment.
        probability: Finite probability in [0, 1], never an arbitrary success score.

    Chronological model fitting, source lineage and historical cohort validation
    are caller responsibilities. This lightweight metric input cannot prove them.
    """

    company_id: str
    outcome_id: CompanyOutcomeId
    decision_at: datetime
    probability: float

    def __post_init__(self) -> None:
        """Validate identity, endpoint, UTC time and bounded finite probability.

        Returns:
            None when this experimental input is valid.
        Raises:
            ValueError: An identity, endpoint, decision time or probability is invalid.
        """
        require_utc(self.decision_at)
        if not self.company_id or self.outcome_id not in COMPANY_OUTCOME_IDS:
            message = "Experimental probability requires company and outcome identity"
            raise ValueError(message)
        if (
            isinstance(self.probability, bool)
            or not isfinite(self.probability)
            or not 0 <= self.probability <= 1
        ):
            message = "Experimental probability must be finite and within [0, 1]"
            raise ValueError(message)


@dataclass(frozen=True)
class CompanyCalibrationBin:
    """Fixed-width reliability bin; an empty bin has null averages.

    Attributes:
        lower: Inclusive probability boundary.
        upper: Exclusive boundary, except the last bin includes probability one.
        count: Matched observed rows in the bin.
        mean_probability: Average prediction, or None without observations.
        observed_rate: Positive fraction, or None without observations.
    """

    lower: float
    upper: float
    count: int
    mean_probability: float | None
    observed_rate: float | None


@dataclass(frozen=True)
class CompanyProbabilityEvaluation:
    """Descriptive metrics with explicit follow-up and prediction coverage.

    Attributes:
        outcome_id: The single endpoint evaluated.
        evaluated_at: UTC label-knowledge cutoff.
        eligible_label_count: Mature observed labels available at that cutoff.
        label_exclusions: One reason per other scoped label, from shared selection.
        forecast_count: Number of input forecasts for this endpoint.
        forecasts_without_eligible_label: Forecasts excluded from scoring.
        labels_without_forecast: Eligible labels on which the experiment abstained.
        matched_count: Exact company/origin matches used by every reported metric.
        company_count: Distinct matched companies; repeated origins are dependent.
        family_count: Distinct matched ownership families.
        origin_count: Distinct matched decision times.
        positive_count: Positive labels among matched rows.
        brier_score: Mean squared probability error; None without matched rows.
        log_loss: Natural-log loss with fixed LOG_LOSS_EPSILON clipping, or None.
        roc_auc: Pairwise discrimination with half credit for ties; None for fewer
            than two observed classes. It never substitutes zero for undefined AUC.
        calibration: Ten fixed equal-width bins, retaining empty bins.

    These counts/metrics provide no confidence interval, model release decision,
    public probability eligibility or empirical validation without a real cohort.
    Compare models on identical matched rows and report abstention separately.
    """

    outcome_id: CompanyOutcomeId
    evaluated_at: datetime
    eligible_label_count: int
    label_exclusions: tuple[tuple[LabelExclusion, int], ...]
    forecast_count: int
    forecasts_without_eligible_label: int
    labels_without_forecast: int
    matched_count: int
    company_count: int
    family_count: int
    origin_count: int
    positive_count: int
    brier_score: float | None
    log_loss: float | None
    roc_auc: float | None
    calibration: tuple[CompanyCalibrationBin, ...]


def evaluate_company_probabilities(
    forecasts: Sequence[CompanyProbabilityForecast],
    labels: Sequence[CompanyOutcomeLabel],
    outcome_id: CompanyOutcomeId,
    evaluated_at: datetime,
) -> CompanyProbabilityEvaluation:
    """Score one endpoint using only mature, observed and available label vintages.

    Args:
        forecasts: Explicit frozen experimental predictions, without model fitting.
        labels: Source-adjudicated records from explicitly selected label vintages.
        outcome_id: Endpoint to evaluate independently; other endpoints are ignored.
        evaluated_at: UTC cutoff; unknown/immature/future-available labels are excluded.
    Returns:
        Coverage counts, Brier/log loss, tie-aware AUC and fixed reliability bins.
        Every metric uses the same exact company/origin matches. Each forecast or
        eligible label is counted once, even if other endpoints are supplied.
    Raises:
        ValueError: Cutoff/outcome is invalid or selected forecasts/labels contain
            duplicate company/origin keys. Vintages must be resolved upstream.
    """
    selection = select_company_labels(labels, outcome_id, evaluated_at)
    scoped = [row for row in forecasts if row.outcome_id == outcome_id]
    predictions = {(row.company_id, row.decision_at): row for row in scoped}
    if len(predictions) != len(scoped):
        message = "Select one experimental probability per company/outcome/origin"
        raise ValueError(message)
    matched = [
        (predictions[key].probability, label)
        for label in selection.labels
        if (key := (label.company_id, label.decision_at)) in predictions
    ]
    pairs = [(probability, label.value is True) for probability, label in matched]
    count = len(pairs)
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(CALIBRATION_BIN_COUNT)]
    for probability, truth in pairs:
        index = min(int(probability * CALIBRATION_BIN_COUNT), CALIBRATION_BIN_COUNT - 1)
        bins[index].append((probability, truth))
    return CompanyProbabilityEvaluation(
        outcome_id=outcome_id,
        evaluated_at=evaluated_at,
        eligible_label_count=len(selection.labels),
        label_exclusions=selection.excluded_counts,
        forecast_count=len(scoped),
        forecasts_without_eligible_label=len(scoped) - count,
        labels_without_forecast=len(selection.labels) - count,
        matched_count=count,
        company_count=len({label.company_id for _, label in matched}),
        family_count=len({label.family_id for _, label in matched}),
        origin_count=len({label.decision_at for _, label in matched}),
        positive_count=sum(truth for _, truth in pairs),
        brier_score=fsum((probability - truth) ** 2 for probability, truth in pairs)
        / count
        if count
        else None,
        log_loss=fsum(_log_loss(probability, truth) for probability, truth in pairs)
        / count
        if count
        else None,
        roc_auc=_roc_auc(pairs),
        calibration=tuple(
            CompanyCalibrationBin(
                lower=index / CALIBRATION_BIN_COUNT,
                upper=(index + 1) / CALIBRATION_BIN_COUNT,
                count=len(rows),
                mean_probability=fsum(probability for probability, _ in rows)
                / len(rows)
                if rows
                else None,
                observed_rate=sum(truth for _, truth in rows) / len(rows)
                if rows
                else None,
            )
            for index, rows in enumerate(bins)
        ),
    )


def _log_loss(probability: float, truth: bool) -> float:
    clipped = max(LOG_LOSS_EPSILON, min(1 - LOG_LOSS_EPSILON, probability))
    return -log(clipped) if truth else -log1p(-clipped)


def _roc_auc(pairs: list[tuple[float, bool]]) -> float | None:
    positives = sum(truth for _, truth in pairs)
    negatives = len(pairs) - positives
    if not positives or not negatives:
        return None
    negatives_below = 0
    favorable_pairs = 0.0
    for _, group in groupby(sorted(pairs), key=lambda pair: pair[0]):
        rows = list(group)
        group_positives = sum(truth for _, truth in rows)
        group_negatives = len(rows) - group_positives
        favorable_pairs += group_positives * (negatives_below + 0.5 * group_negatives)
        negatives_below += group_negatives
    return favorable_pairs / (positives * negatives)
