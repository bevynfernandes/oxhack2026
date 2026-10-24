"""Calendar horizons for the separate company-level outcomes in issue #19."""

from calendar import monthrange
from datetime import datetime
from typing import Literal

from oxhack2026.features.definitions import require_utc

CompanyOutcomeId = Literal[
    "operating_growth_24m_v1",
    "commercial_viability_12m_v1",
    "financing_or_acquisition_24m_v1",
]
_HORIZON_MONTHS: dict[CompanyOutcomeId, int] = {
    "operating_growth_24m_v1": 24,
    "commercial_viability_12m_v1": 12,
    "financing_or_acquisition_24m_v1": 24,
}


def company_horizon_end(
    decision_at: datetime, outcome_id: CompanyOutcomeId
) -> datetime:
    """Return the exact calendar anniversary, clamping an absent leap-day date.

    Args:
        decision_at: Aware UTC company assessment cutoff; any weekday/time is valid.
        outcome_id: One of the separate versioned company outcome definitions.
    Returns:
        Twelve- or twenty-four-month anniversary at the same UTC time of day.
        February 29 becomes February 28 when the target year is not a leap year.
    Raises:
        ValueError: Cutoff is not UTC, outcome is unsupported, or the anniversary
            exceeds Python's supported datetime range.
    """
    require_utc(decision_at)
    months = _HORIZON_MONTHS.get(outcome_id)
    if months is None:
        message = "Unsupported company outcome definition"
        raise ValueError(message)
    year = decision_at.year + months // 12
    day = min(decision_at.day, monthrange(year, decision_at.month)[1])
    return decision_at.replace(year=year, day=day)
