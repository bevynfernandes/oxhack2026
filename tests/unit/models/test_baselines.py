"""Independent formula and exact-tie comparator checks on synthetic counts."""

from datetime import timedelta
from math import expm1, fsum, log, log1p
from pathlib import Path

import orjson
import pytest

from oxhack2026.evaluation.comparators import (
    expected_shortlist_growth,
    selection_weights,
)
from oxhack2026.models.baselines import (
    damped_trend,
    persistence,
    recent_log_growth,
    weekday_seasonal,
)
from oxhack2026.models.contracts import ForecastResult, TargetId, TargetWindows

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/models"


def _windows(target_id: TargetId = "downloads_next_30d_v1") -> TargetWindows:
    payload = orjson.loads((FIXTURES / "ready.json").read_bytes())["windows"]
    if target_id == "downloads_trailing_28d_at_91d_v1":
        payload.update(
            target_id=target_id,
            reference={"start": "2024-12-07T00:00:00Z", "end": "2025-01-04T00:00:00Z"},
            target={"start": "2025-03-10T00:00:00Z", "end": "2025-04-07T00:00:00Z"},
        )
    return TargetWindows.model_validate(payload)


@pytest.mark.parametrize("count", [0, 1, 1000, (1 << 63) - 1])
def test_persistence_preserves_reference(count: int) -> None:
    """Persistence is the complete reference count, including an explicit zero."""
    assert persistence(count) == float(count)


@pytest.mark.parametrize("count", [-1, 1 << 63])
def test_invalid_baseline_counts(count: int) -> None:
    """Negative or overflowing source counts cannot become predictions."""
    with pytest.raises(ValueError, match="BIGINT"):
        persistence(count)


@pytest.mark.parametrize(
    "target_id", ["downloads_next_30d_v1", "downloads_trailing_28d_at_91d_v1"]
)
def test_weekday_seasonality_uses_actual_target_calendar(target_id: TargetId) -> None:
    """Different weekday levels are summed over the target dates, not 30*mean."""
    windows = _windows(target_id)
    history_start = windows.observation_window_end - timedelta(days=28)
    history = [
        10 * ((history_start + timedelta(days=day)).weekday() + 1) for day in range(28)
    ]
    days = (windows.target.end - windows.target.start).days
    expected = sum(
        10 * ((windows.target.start + timedelta(days=day)).weekday() + 1)
        for day in range(days)
    )

    assert weekday_seasonal(history, windows) == expected


@pytest.mark.parametrize("history", [[0] * 28, [5] * 28])
def test_weekday_seasonal_zero_and_constant(history: list[int]) -> None:
    """Complete zero differs from missing; constant daily levels scale by duration."""
    assert weekday_seasonal(history, _windows()) == history[0] * 30


@pytest.mark.parametrize(
    "history", [[1] * 27, [1] * 29, [1] * 27 + [None], [1] * 27 + [-1]]
)
def test_incomplete_weekday_history_rejected(history: list[int | None]) -> None:
    """Do not shift the anchor or fill absent daily observations with zeros."""
    with pytest.raises(ValueError):
        weekday_seasonal(history, _windows())


@pytest.mark.parametrize(
    ("reference", "previous"), [(1000, 1000), (0, 0), (0, 1000), (1000, 0)]
)
def test_recent_log_growth(reference: int, previous: int) -> None:
    """Recent growth uses log1p, preserving genuine zero-count windows."""
    assert recent_log_growth(reference, previous) == pytest.approx(
        log1p(reference) - log1p(previous)
    )


@pytest.mark.parametrize(
    ("reference", "previous"), [(3000, 2000), (2000, 3000), (10000, 1), (1, 10000)]
)
@pytest.mark.parametrize(
    ("target_id", "midpoint_days", "duration"),
    [
        ("downloads_next_30d_v1", 32, 30),
        ("downloads_trailing_28d_at_91d_v1", 93, 28),
    ],
)
def test_damped_trend_formula(
    reference: int,
    previous: int,
    target_id: TargetId,
    midpoint_days: int,
    duration: int,
) -> None:
    """Use independently calculated target-specific midpoint scaling and clipping."""
    growth = min(log(2), max(-log(2), log1p(reference) - log1p(previous)))
    expected = max(0, expm1(log1p(reference) + 0.5 * growth * midpoint_days / duration))

    assert damped_trend(reference, previous, _windows(target_id)) == pytest.approx(
        expected
    )


def test_no_trend_equals_persistence() -> None:
    """Zero recent log growth reduces exactly to the persistence baseline."""
    assert damped_trend(3000, 3000, _windows()) == pytest.approx(persistence(3000))
    assert damped_trend(0, 1000, _windows()) == 0


def test_persistence_ties_equal_uniform_random() -> None:
    """All tied forecasts receive exact k/n inclusion instead of alphabetical slots."""
    scores = {str(index): 0.0 for index in range(10)}
    actual = {str(index): float(index) for index in range(10)}

    weights = selection_weights(scores)

    assert set(weights.values()) == {0.5}
    assert fsum(weights.values()) == 5
    assert expected_shortlist_growth(scores, actual) == 4.5


def test_partial_boundary_ties() -> None:
    """Candidates above the boundary are certain; tied candidates split slots."""
    scores = {"first": 3.0, "second": 2.0, "third": 2.0, "last": 0.0}

    assert selection_weights(scores, 2) == {"first": 1.0, "second": 0.5, "third": 0.5}
    assert (
        expected_shortlist_growth(
            scores, {"first": 10.0, "second": 2.0, "third": 4.0, "last": -1.0}, 2
        )
        == 6.5
    )


def test_small_and_empty_comparators() -> None:
    """Small universes select every candidate; empty selections remain undefined."""
    assert selection_weights({"a": 1.0, "b": 0.0}) == {"a": 1.0, "b": 1.0}
    assert selection_weights({}, 5) == {}
    assert selection_weights({"a": 1.0}, 0) == {}
    assert expected_shortlist_growth({}, {}) is None


@pytest.mark.parametrize("limit", [-1, 6])
def test_invalid_comparator_size(limit: int) -> None:
    """The predeclared research budget stays bounded at five."""
    with pytest.raises(ValueError):
        selection_weights({"a": 0.0}, limit)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_comparator_values(value: float) -> None:
    """Nonfinite comparator scores and truth cannot contaminate evaluation."""
    with pytest.raises(ValueError):
        selection_weights({"a": value})
    with pytest.raises(ValueError):
        expected_shortlist_growth({"a": 0.0}, {"a": value})


def test_comparator_universes_must_match() -> None:
    """No comparator may gain an advantage by silently dropping hard candidates."""
    with pytest.raises(ValueError, match="identical candidates"):
        expected_shortlist_growth({"a": 1.0}, {"b": 1.0})


def test_baselines_import_without_mutating_forecast() -> None:
    """Numerical stages consume counts without changing a frozen forecast payload."""
    forecast = ForecastResult.model_validate_json(
        (FIXTURES / "ready.json").read_bytes()
    )
    before = forecast.model_dump_json()

    assert persistence(3000) == forecast.baseline_predicted_downloads
    assert forecast.model_dump_json() == before
