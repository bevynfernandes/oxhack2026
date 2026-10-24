"""Predeclared aggregate baselines from PLAN.md; no fitting or vendor calls."""

from collections.abc import Sequence
from math import expm1, fsum, log, log1p

from oxhack2026.models.contracts import TargetWindows

_MAX_COUNT = (1 << 63) - 1
_LOG_TWO = log(2)


def _require_count(value: int | None) -> int:
    if type(value) is not int or not 0 <= value <= _MAX_COUNT:
        message = "Download counts must be complete nonnegative BIGINT integers"
        raise ValueError(message)
    return value


def persistence(reference_downloads: int) -> float:
    """Forecast the unchanged reference-window total.

    Args:
        reference_downloads: Complete, nonnegative reference count.
    Returns:
        Reference count as a numerical baseline estimate.
    Raises:
        ValueError: If the count is missing, negative, or not a BIGINT integer.
    """
    return float(_require_count(reference_downloads))


def weekday_seasonal(
    history_downloads: Sequence[int | None], windows: TargetWindows
) -> float:
    """Apply four-week weekday means to the exact aggregate target window.

    Args:
        history_downloads: Exactly 28 daily counts in chronological order ending
            at the exclusive observation anchor, with no missing days.
        windows: Validated fixed-lag reference and target boundaries.
    Returns:
        Sum of weekday expectations over the 30-day or trailing-28-day target.
    Raises:
        ValueError: If history is not exactly 28 complete nonnegative integer days.
    """
    if len(history_downloads) != 28:
        message = "Weekday seasonality requires exactly 28 anchored daily observations"
        raise ValueError(message)
    weekday_sums = [0] * 7
    first_weekday = windows.observation_window_end.weekday()
    for index, count in enumerate(history_downloads):
        weekday_sums[(first_weekday + index) % 7] += _require_count(count)
    days = (windows.target.end - windows.target.start).days
    whole_weeks, remaining_days = divmod(days, 7)
    target_weekday = windows.target.start.weekday()
    return fsum(
        weekday_sums[weekday]
        / 4
        * (whole_weeks + ((weekday - target_weekday) % 7 < remaining_days))
        for weekday in range(7)
    )


def recent_log_growth(reference_downloads: int, previous_downloads: int) -> float:
    """Measure adjacent nonoverlapping reference-window log growth.

    Args:
        reference_downloads: Complete count in the current reference window.
        previous_downloads: Complete count in the equally long preceding window.
    Returns:
        Difference of log1p counts, finite even when one complete window is zero.
    Raises:
        ValueError: If either count is missing, negative, or not a BIGINT integer.
    """
    return log1p(_require_count(reference_downloads)) - log1p(
        _require_count(previous_downloads)
    )


def damped_trend(
    reference_downloads: int, previous_downloads: int, windows: TargetWindows
) -> float:
    """Forecast clipped adjacent log growth, damped and scaled by window midpoints.

    Args:
        reference_downloads: Complete current reference total.
        previous_downloads: Complete immediately preceding equal-length total.
        windows: Validated target/reference windows; each target has its own scale.
    Returns:
        Nonnegative aggregate estimate after clipping log growth to +/-log(2),
        damping by 0.5, and scaling by midpoint distance / reference duration.
    Raises:
        ValueError: If either count is missing, negative, or not a BIGINT integer.
    """
    growth = recent_log_growth(reference_downloads, previous_downloads)
    reference_midpoint = (
        windows.reference.start + (windows.reference.end - windows.reference.start) / 2
    )
    target_midpoint = (
        windows.target.start + (windows.target.end - windows.target.start) / 2
    )
    midpoint_scale = (target_midpoint - reference_midpoint) / (
        windows.reference.end - windows.reference.start
    )
    residual = 0.5 * min(_LOG_TWO, max(-_LOG_TWO, growth)) * midpoint_scale
    return max(0.0, expm1(log1p(reference_downloads) + residual))
