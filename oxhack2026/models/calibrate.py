"""Chronological CQR calculations and empirical serving gates, without fitting."""

from dataclasses import dataclass
from math import ceil, isfinite

import numpy as np
from numpy.typing import NDArray

from oxhack2026.models.contracts import ModelReference

_NOMINAL_COVERAGE = 0.8
_MAX_LOG_TARGET = float(np.log(np.finfo(np.float64).max))


@dataclass(frozen=True)
class CQRCalibration:
    """Frozen correction paired to an exact model artifact, not only a model name.

    Attributes:
        calibration_id: Immutable calibration run identifier.
        model_id: Frozen fitted model identifier.
        model_sha256: SHA-256 of the model artifact used for calibration predictions.
        log_correction: Nonnegative finite-sample widening on log-target scale.
        prediction_count: Number of chronological calibration predictions.
        crossing_rate: Fraction with crossed input quantiles before sorting.
    """

    calibration_id: str
    model_id: str
    model_sha256: str
    log_correction: float
    prediction_count: int
    crossing_rate: float


@dataclass(frozen=True)
class CalibratedBand:
    """Experimental aggregate interval endpoints; this is not a serving approval.

    Attributes:
        lower: Nonnegative lower count endpoint per prediction.
        upper: Ordered upper count endpoint per prediction.
        crossing_rate: Input crossing rate before quantile sorting.
    """

    lower: NDArray[np.float64]
    upper: NDArray[np.float64]
    crossing_rate: float


@dataclass(frozen=True)
class SubgroupCoverage:
    """Empirical coverage and support for one preregistered major subgroup.

    Attributes:
        row_count: Number of mature predictions in the subgroup.
        origin_count: Distinct weekly origins covered by those rows.
        coverage: Fraction of actuals contained in the interval, between zero and one.
    """

    row_count: int
    origin_count: int
    coverage: float


@dataclass(frozen=True)
class IntervalEvidence:
    """Evidence supplied by a frozen chronological evaluation for interval gating.

    Attributes:
        calibration_count: Number of calibration predictions.
        calibration_origins: Distinct calibration weekly origins.
        calibration_organizations: Distinct organizations in calibration.
        test_coverage: Overall final empirical coverage for the nominal 80% band.
        interval_score: Evaluated model interval score (lower is better).
        baseline_interval_score: Calibrated baseline score on identical candidates.
        subgroups: Preregistered major subgroup coverage and support.
    """

    calibration_count: int
    calibration_origins: int
    calibration_organizations: int
    test_coverage: float
    interval_score: float
    baseline_interval_score: float
    subgroups: tuple[SubgroupCoverage, ...] = ()


def _ordered_quantiles(
    predictions: NDArray[np.float64],
) -> tuple[NDArray[np.float64], float]:
    if predictions.ndim != 2 or predictions.shape[1] != 3 or not predictions.shape[0]:
        message = "Quantiles require a nonempty (n, 3) array on log-target scale"
        raise ValueError(message)
    if not np.isfinite(predictions).all():
        message = "Quantile predictions must be finite"
        raise ValueError(message)
    crossing = (predictions[:, 0] > predictions[:, 1]) | (
        predictions[:, 1] > predictions[:, 2]
    )
    return np.sort(predictions, axis=1), float(np.mean(crossing))


def fit_cqr(
    model: ModelReference,
    predictions: NDArray[np.float64],
    actual_log_downloads: NDArray[np.float64],
    calibration_id: str,
) -> CQRCalibration:
    """Fit the exact nominal-80% CQR correction using chronological calibration rows.

    Args:
        model: Frozen model reference that generated all calibration predictions.
        predictions: Shape (n, 3) quantiles on log1p(target downloads), after adding
            each reference log count to residual-model quantile predictions.
        actual_log_downloads: Shape (n,) mature log1p outcome counts, chronologically
            held out from model fitting and available before the test boundary.
        calibration_id: Immutable run ID bound to this correction and its model.
    Returns:
        Correction at ceil(0.8*(n+1)) in nonnegative sorted conformity scores,
        plus the observed quantile crossing rate. No model refitting occurs.
    Raises:
        ValueError: For invalid shapes/nonfinite values, insufficient calibration
            rows for the finite-sample order statistic, or a missing run ID.
    """
    ordered, crossing = _ordered_quantiles(predictions)
    count = predictions.shape[0]
    if (
        actual_log_downloads.shape != (count,)
        or not np.isfinite(actual_log_downloads).all()
        or np.any(actual_log_downloads < 0)
        or not calibration_id
    ):
        message = "Calibration requires finite nonnegative log targets and a run ID"
        raise ValueError(message)
    rank = ceil(_NOMINAL_COVERAGE * (count + 1))
    if rank > count:
        message = "Insufficient rows for the finite-sample CQR order statistic"
        raise ValueError(message)
    scores = np.maximum(
        ordered[:, 0] - actual_log_downloads,
        actual_log_downloads - ordered[:, 2],
    )
    np.maximum(scores, 0, out=scores)
    correction = float(np.partition(scores, rank - 1)[rank - 1])
    return CQRCalibration(
        calibration_id=calibration_id,
        model_id=model.model_id,
        model_sha256=model.model_artifact.sha256,
        log_correction=correction,
        prediction_count=count,
        crossing_rate=crossing,
    )


def apply_cqr(
    calibration: CQRCalibration,
    model: ModelReference,
    predictions: NDArray[np.float64],
) -> CalibratedBand:
    """Apply one frozen model/calibrator pair and invert its aggregate count bands.

    Args:
        calibration: Saved chronological correction for the frozen fitted model.
        model: The unchanged model artifact, including its SHA-256 digest.
        predictions: Shape (n, 3) log-target quantile predictions from that model.
    Returns:
        Ordered nonnegative count endpoints and input crossing rate. Endpoints
        are conformally adjusted intervals, not calibrated p10/p90 estimates.
    Raises:
        ValueError: For a mismatched pair, invalid correction/quantiles, or an
            inverse transform that would overflow. Serving still needs gate checks.
    """
    if (
        calibration.model_id != model.model_id
        or calibration.model_sha256 != model.model_artifact.sha256
        or not isfinite(calibration.log_correction)
        or calibration.log_correction < 0
    ):
        message = "Calibration must remain paired with its unchanged model artifact"
        raise ValueError(message)
    ordered, crossing = _ordered_quantiles(predictions)
    lower = np.maximum(0, ordered[:, 0] - calibration.log_correction)
    upper = np.maximum(0, ordered[:, 2] + calibration.log_correction)
    if np.any(upper >= _MAX_LOG_TARGET):
        message = "Calibrated interval cannot be represented as finite count endpoints"
        raise ValueError(message)
    np.expm1(lower, out=lower)
    np.expm1(upper, out=upper)
    return CalibratedBand(lower, upper, crossing)


def interval_serving_reasons(evidence: IntervalEvidence) -> tuple[str, ...]:
    """Apply the plan's support, coverage, subgroup, and baseline interval-score gates.

    Args:
        evidence: Empirical final evaluation of the unchanged model/calibrator pair
            against the preregistered calibrated baseline on identical candidates.
    Returns:
        Stable rejection codes; empty only if all stated numerical gates pass.
        This does not establish distribution-free coverage or statistical superiority.
    Raises:
        ValueError: If counts, coverage, or interval scores are invalid.
    """
    counts = (
        evidence.calibration_count,
        evidence.calibration_origins,
        evidence.calibration_organizations,
    )
    scores = (evidence.interval_score, evidence.baseline_interval_score)
    if (
        any(count < 0 for count in counts)
        or evidence.calibration_origins > evidence.calibration_count
        or evidence.calibration_organizations > evidence.calibration_count
        or not isfinite(evidence.test_coverage)
        or not 0 <= evidence.test_coverage <= 1
        or any(not isfinite(score) or score < 0 for score in scores)
        or any(
            group.row_count < 0
            or group.origin_count < 0
            or group.origin_count > group.row_count
            or not isfinite(group.coverage)
            or not 0 <= group.coverage <= 1
            for group in evidence.subgroups
        )
    ):
        message = (
            "Interval evidence requires valid support counts, coverage, and scores"
        )
        raise ValueError(message)
    reasons: list[str] = []
    if evidence.calibration_count < 500:
        reasons.append("insufficient_calibration_predictions")
    if evidence.calibration_origins < 26:
        reasons.append("insufficient_calibration_origins")
    if evidence.calibration_organizations < 30:
        reasons.append("insufficient_calibration_organizations")
    if not 0.75 <= evidence.test_coverage <= 0.90:
        reasons.append("overall_coverage_outside_gate")
    if any(
        group.row_count >= 100 and group.origin_count >= 13 and group.coverage < 0.70
        for group in evidence.subgroups
    ):
        reasons.append("supported_subgroup_undercoverage")
    if evidence.interval_score > evidence.baseline_interval_score:
        reasons.append("interval_score_worse_than_baseline")
    return tuple(reasons)
