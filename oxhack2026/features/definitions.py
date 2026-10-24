"""Exact target windows and eligibility constants shared by batch and API code."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

TargetId = Literal["downloads_next_30d_v1", "downloads_trailing_28d_at_91d_v1"]
Ecosystem = Literal["npm", "pypi"]
HISTORY_DAYS = 84
MIN_REFERENCE_COUNT = 1000
SHORTLIST_SIZE = 5
MIN_HEADLINE_ORGANIZATIONS = 10


def require_utc(value: datetime) -> datetime:
    """Validate an aware UTC instant and return it unchanged.

    Args:
        value: Timestamp to validate.
    Returns:
        The supplied timestamp.
    Raises:
        ValueError: When timezone information is absent or offset is not zero.
    """
    if value.utcoffset() != timedelta(0):
        message = "Timestamp must be timezone-aware UTC"
        raise ValueError(message)
    return value


def require_decision(value: datetime) -> datetime:
    """Validate a Monday midnight UTC decision origin.

    Args:
        value: Decision timestamp.
    Returns:
        The validated timestamp.
    Raises:
        ValueError: If the timestamp is not Monday 00:00:00 UTC.
    """
    require_utc(value)
    midnight = datetime.combine(value.date(), datetime.min.time(), UTC)
    if value.weekday() != 0 or value != midnight:
        message = "Decision origin must be Monday 00:00:00 UTC"
        raise ValueError(message)
    return value


@dataclass(frozen=True)
class TargetWindows:
    """Half-open feature, reference, and outcome windows in UTC."""

    observation_end: datetime
    history_start: datetime
    reference_start: datetime
    reference_end: datetime
    target_start: datetime
    target_end: datetime


def target_windows(decision_at: datetime, target_id: TargetId) -> TargetWindows:
    """Construct fixed-lag windows without shifting for missing observations.

    Args:
        decision_at: Monday midnight UTC.
        target_id: Versioned target definition.
    Returns:
        Exact half-open windows specified by PLAN.md section 3.
    Raises:
        ValueError: If the origin or target is unsupported.
    """
    require_decision(decision_at)
    anchor = decision_at - timedelta(hours=48)
    if target_id == "downloads_next_30d_v1":
        reference_days, start_days, end_days = 30, 0, 30
    elif target_id == "downloads_trailing_28d_at_91d_v1":
        reference_days, start_days, end_days = 28, 63, 91
    else:
        message = "Unsupported target definition"
        raise ValueError(message)
    return TargetWindows(
        observation_end=anchor,
        history_start=anchor - timedelta(days=HISTORY_DAYS),
        reference_start=anchor - timedelta(days=reference_days),
        reference_end=anchor,
        target_start=decision_at + timedelta(days=start_days),
        target_end=decision_at + timedelta(days=end_days),
    )
