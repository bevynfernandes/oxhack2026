"""Per-tool realized diagnostics shared by batch scoring and reveal adapters."""

from datetime import datetime
from math import log1p

from oxhack2026.evaluation.contracts import OutcomeDiagnostics
from oxhack2026.features.definitions import MIN_REFERENCE_COUNT, require_utc
from oxhack2026.models.contracts import ForecastResult, MatureOutcome


def outcome_diagnostics(
    forecast: ForecastResult, outcome: MatureOutcome, as_of: datetime
) -> OutcomeDiagnostics:
    """Score one mature outcome without changing or revealing the forecast payload.

    Args:
        forecast: Immutable original prediction and baseline estimate.
        outcome: One selected complete outcome vintage, stored separately.
        as_of: UTC reveal/evaluation cutoff; later-available truth must be rejected.
    Returns:
        Raw-count and log-count absolute errors when estimates exist. Realized
        percentage growth stays null below the 1,000-reference ranking threshold.
    Raises:
        ValueError: If identity/windows differ, the cutoff is not UTC, or truth
            is incomplete or unavailable at that cutoff.
    """
    require_utc(as_of)
    label = outcome.label
    if (
        outcome.forecast_id != forecast.forecast_id
        or label.feature_row_id != forecast.feature_row_id
        or label.windows != forecast.windows
    ):
        message = "Outcome diagnostics require the exact frozen forecast and label"
        raise ValueError(message)
    actual, available_at = label.actual_downloads, label.available_at
    if actual is None or available_at is None or available_at > as_of:
        message = "Outcome is not fully available at the requested cutoff"
        raise ValueError(message)
    reference = forecast.reference_downloads
    prediction, baseline = (
        forecast.predicted_downloads,
        forecast.baseline_predicted_downloads,
    )
    growth = (
        100 * (actual / reference - 1)
        if reference is not None and reference >= MIN_REFERENCE_COUNT
        else None
    )
    actual_log = log1p(actual)
    return OutcomeDiagnostics(
        forecast_id=forecast.forecast_id,
        outcome_vintage=outcome.outcome_vintage,
        actual_downloads=actual,
        realized_growth_pct=growth,
        model_absolute_error=abs(prediction - actual)
        if prediction is not None
        else None,
        baseline_absolute_error=abs(baseline - actual)
        if baseline is not None
        else None,
        model_log_absolute_error=abs(log1p(prediction) - actual_log)
        if prediction is not None
        else None,
        baseline_log_absolute_error=abs(log1p(baseline) - actual_log)
        if baseline is not None
        else None,
        reason_codes=("missing_source",)
        if reference is None
        else (("low_reference_count",) if reference < MIN_REFERENCE_COUNT else ()),
    )
