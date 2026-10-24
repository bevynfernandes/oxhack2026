"""Reveal diagnostics use immutable matching truth and enforce availability."""

from datetime import UTC, datetime, timedelta
from math import log1p
from pathlib import Path

import pytest

from oxhack2026.evaluation.metrics import outcome_diagnostics
from oxhack2026.models.contracts import ForecastResult, MatureOutcome

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/models"


def _records() -> tuple[ForecastResult, MatureOutcome]:
    return (
        ForecastResult.model_validate_json((FIXTURES / "ready.json").read_bytes()),
        MatureOutcome.model_validate_json(
            (FIXTURES / "mature-outcome.json").read_bytes()
        ),
    )


def test_realized_growth_and_errors() -> None:
    """Independently verify the reveal calculations without touching predictions."""
    forecast, outcome = _records()
    original = forecast.model_dump_json()

    metrics = outcome_diagnostics(forecast, outcome, datetime(2025, 2, 7, tzinfo=UTC))

    assert metrics.actual_downloads == 3900
    assert metrics.realized_growth_pct == pytest.approx(30)
    assert metrics.model_absolute_error == 300
    assert metrics.baseline_absolute_error == 900
    assert metrics.model_log_absolute_error == pytest.approx(log1p(3900) - log1p(3600))
    assert metrics.baseline_log_absolute_error == pytest.approx(
        log1p(3900) - log1p(3000)
    )
    assert forecast.model_dump_json() == original


def test_future_available_truth_cannot_be_revealed() -> None:
    """A completed outcome still waits for its explicit availability timestamp."""
    forecast, outcome = _records()

    with pytest.raises(ValueError, match="requested cutoff"):
        outcome_diagnostics(
            forecast,
            outcome,
            datetime(2025, 2, 7, tzinfo=UTC) - timedelta(microseconds=1),
        )


def test_unavailable_forecast_errors_remain_null() -> None:
    """A missing model estimate is not a zero estimate when actual truth arrives."""
    forecast, outcome = _records()
    unavailable = ForecastResult.model_validate(
        forecast.model_dump()
        | {
            "forecast_status": "unavailable",
            "predicted_downloads": None,
            "predicted_growth_pct": None,
            "ranking_eligible": False,
            "baseline_predicted_downloads": None,
        }
    )

    metrics = outcome_diagnostics(
        unavailable, outcome, datetime(2025, 2, 7, tzinfo=UTC)
    )

    assert metrics.model_absolute_error is None
    assert metrics.baseline_absolute_error is None
    assert metrics.realized_growth_pct == pytest.approx(30)


def test_low_reference_realized_percentage_stays_null() -> None:
    """Low denominators expose count errors without unstable displayed percentages."""
    forecast, outcome = _records()
    low = ForecastResult.model_validate(
        forecast.model_dump()
        | {
            "reference_downloads": 999,
            "predicted_growth_pct": None,
            "ranking_eligible": False,
        }
    )

    metrics = outcome_diagnostics(low, outcome, datetime(2025, 2, 7, tzinfo=UTC))

    assert metrics.realized_growth_pct is None
    assert metrics.model_absolute_error == 300
    assert metrics.reason_codes == ("low_reference_count",)


def test_matching_outcome_identity_required() -> None:
    """A different forecast's actuals cannot score this result."""
    forecast, outcome = _records()
    other = MatureOutcome.model_validate(
        outcome.model_dump() | {"forecast_id": "other"}
    )

    with pytest.raises(ValueError, match="exact frozen"):
        outcome_diagnostics(forecast, other, datetime(2025, 2, 7, tzinfo=UTC))


def test_zero_actual_is_valid() -> None:
    """Complete zero-download outcomes are valid truth, not missing labels."""
    forecast, outcome = _records()
    zero = MatureOutcome.model_validate(
        outcome.model_dump()
        | {
            "label": outcome.label.model_dump() | {"actual_downloads": 0},
        }
    )

    metrics = outcome_diagnostics(forecast, zero, datetime(2025, 2, 7, tzinfo=UTC))

    assert metrics.actual_downloads == 0
    assert metrics.realized_growth_pct == -100
    assert metrics.model_absolute_error == 3600
