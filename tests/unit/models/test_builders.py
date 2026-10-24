"""Saved C1-to-C2 feature and label tests with explicit synthetic daily history."""

from datetime import UTC, datetime, timedelta
from math import log1p

import polars as pl
import pytest

from oxhack2026.features.builders import FeatureRequest, build_features, build_labels
from oxhack2026.features.definitions import TargetId, target_windows
from oxhack2026.models.contracts import RowIdentity, TargetWindows, TimeWindow
from oxhack2026.storage.contracts import ObservationSeries

DECISION = datetime(2025, 1, 6, tzinfo=UTC)


def _request(target: TargetId = "downloads_next_30d_v1") -> FeatureRequest:
    boundaries = target_windows(DECISION, target)
    return FeatureRequest(
        feature_row_id=f"synthetic-{target}",
        identity=RowIdentity(
            tool_id="tool",
            organization_id="org",
            package_id="package",
            ecosystem="npm",
            dataset_version="synthetic-v1",
            mapping_version="mapping-v1",
        ),
        windows=TargetWindows(
            target_id=target,
            decision_at=DECISION,
            observation_window_end=boundaries.observation_end,
            reference=TimeWindow(
                start=boundaries.reference_start, end=boundaries.reference_end
            ),
            target=TimeWindow(start=boundaries.target_start, end=boundaries.target_end),
        ),
        series=ObservationSeries(
            series_id="series",
            source="npm",
            entity_kind="package",
            entity_id="package",
            ecosystem="npm",
            metric="daily_downloads",
            unit="downloads",
            cadence="day",
        ),
    )


def _observations(
    request: FeatureRequest, *, label: bool = False, value: int = 100
) -> pl.DataFrame:
    windows = request.windows
    start = (
        windows.target.start
        if label
        else windows.observation_window_end - timedelta(days=84)
    )
    end = windows.target.end if label else windows.observation_window_end
    days = [start + timedelta(days=index) for index in range((end - start).days)]
    return pl.DataFrame(
        {
            "revision_id": [f"synthetic-{day.date()}" for day in days],
            "series_id": ["series"] * len(days),
            "day": days,
            "value": [value] * len(days),
            "completeness": ["complete"] * len(days),
            "available_at": [day + timedelta(days=3) for day in days],
            "first_collected_at": [datetime(2026, 10, 24, tzinfo=UTC)] * len(days),
            "retrieved_at": [datetime(2026, 10, 24, tzinfo=UTC)] * len(days),
        }
    )


@pytest.mark.parametrize(
    "target", ["downloads_next_30d_v1", "downloads_trailing_28d_at_91d_v1"]
)
def test_complete_history_builds_exact_shared_features(target: TargetId) -> None:
    """Both targets share anchored predictors but use their own reference total."""
    request = _request(target)
    daily = _observations(request)

    (row,) = build_features(daily.lazy(), [request], "reconstructed")

    assert row.forecast_eligible is True
    assert row.complete_history_days == 84
    for days in (7, 28, 30, 56, 60, 84):
        assert row.values[f"downloads_{days}d"] == days * 100
    reference = 3000 if target == "downloads_next_30d_v1" else 2800
    assert row.values["log_reference"] == log1p(reference)
    assert row.values["log_growth_28d"] == row.values["log_growth_30d"] == 0
    assert row.values["weekly_log_change_std_11"] == 0
    assert row.values["observation_age_hours"] == 48
    assert row.values["history_coverage"] == 1
    assert row.values["verified_package_age_days"] is None
    for weekday in range(1, 8):
        assert row.values[f"weekday_share_{weekday}"] == pytest.approx(1 / 7)
    assert len(row.source_revision_ids) == 84


def test_missing_old_day_invalidates_history_without_shifting_anchor() -> None:
    """A gap outside recent windows still prevents learned forecasting."""
    request = _request()
    daily = _observations(request).slice(1)

    (row,) = build_features(daily.lazy(), [request], "reconstructed")

    assert row.forecast_eligible is False
    assert row.reason_codes == ("insufficient_history",)
    assert row.values["downloads_7d"] == 700
    assert row.values["downloads_84d"] is None
    assert row.values["weekly_log_change_std_11"] is None
    assert row.values["history_coverage"] == 83 / 84


def test_prospective_cannot_reuse_later_collection() -> None:
    """Historical availability assumptions never establish prospective collection."""
    request = _request()

    (row,) = build_features(_observations(request).lazy(), [request], "prospective")

    assert row.complete_history_days == 0
    assert row.values["downloads_7d"] is None
    assert row.values["observation_age_hours"] is None
    assert row.source_revision_ids == ()


def test_complete_zero_counts_remain_finite_and_eligible() -> None:
    """Low reference affects ranking later, not count-level forecast eligibility."""
    request = _request()

    (row,) = build_features(
        _observations(request, value=0).lazy(), [request], "reconstructed"
    )

    assert row.forecast_eligible is True
    assert row.values["downloads_84d"] == 0
    assert row.values["log_reference"] == 0
    assert row.values["weekday_share_1"] is None
    assert row.values["weekly_log_change_std_11"] == 0


@pytest.mark.parametrize(
    "target,days",
    [("downloads_next_30d_v1", 30), ("downloads_trailing_28d_at_91d_v1", 28)],
)
def test_labels_require_every_target_day_and_its_availability(
    target: TargetId, days: int
) -> None:
    """Target end alone is insufficient when the last day's lag has not elapsed."""
    request = _request(target)
    observations = _observations(request, label=True).lazy()
    mature_at = request.windows.target.end + timedelta(days=2)

    (immature,) = build_labels(
        observations, [request], "reconstructed", mature_at - timedelta(microseconds=1)
    )
    (mature,) = build_labels(observations, [request], "reconstructed", mature_at)

    assert immature.actual_downloads is immature.available_at is None
    assert mature.actual_downloads == days * 100
    assert mature.available_at == mature_at
    assert len(mature.outcome_revision_ids) == days


def test_label_zero_is_distinct_from_missing_and_prospective_unknown() -> None:
    """Neither absent observations nor future collection becomes a zero outcome."""
    request = _request()
    observations = _observations(request, label=True, value=0)
    as_of = request.windows.target.end + timedelta(days=2)

    (zero,) = build_labels(observations.lazy(), [request], "reconstructed", as_of)
    (missing,) = build_labels(
        observations.slice(1).lazy(), [request], "reconstructed", as_of
    )
    (uncollected,) = build_labels(observations.lazy(), [request], "prospective", as_of)

    assert zero.actual_downloads == 0
    assert missing.actual_downloads is missing.available_at is None
    assert uncollected.actual_downloads is uncollected.available_at is None


def test_totals_do_not_overflow_int64() -> None:
    """Aggregate counts are wider than individual C1 BIGINT daily measurements."""
    request = _request()
    maximum_count = (1 << 63) - 1
    daily = _observations(request, label=True, value=maximum_count)

    (label,) = build_labels(
        daily.lazy(),
        [request],
        "reconstructed",
        request.windows.target.end + timedelta(days=2),
    )

    assert label.actual_downloads == maximum_count * 30


def test_requests_reject_duplicate_ids_and_mismatched_packages() -> None:
    """Ambiguous rows and accidental cross-package histories fail explicitly."""
    request = _request()
    daily = _observations(request).lazy()

    with pytest.raises(ValueError, match="unique"):
        build_features(daily, [request, request], "reconstructed")
    with pytest.raises(ValueError, match="frozen package"):
        FeatureRequest.model_validate(
            request.model_dump()
            | {"identity": request.identity.model_dump() | {"package_id": "other"}}
        )


def test_empty_requests_and_absent_series_preserve_expected_behavior() -> None:
    """An empty batch yields no rows; an absent requested series stays explicit."""
    request = _request()
    empty = _observations(request).clear().lazy()

    assert build_features(empty, [], "reconstructed") == ()
    assert build_labels(empty, [], "reconstructed", DECISION) == ()
    (row,) = build_features(empty, [request], "reconstructed")
    assert row.complete_history_days == 0
    assert row.forecast_eligible is False


def test_multiple_origins_share_source_without_cross_contamination() -> None:
    """Vectorized aggregation keys every temporal statistic by its own request."""
    request = _request()
    later = FeatureRequest.model_validate(
        request.model_dump()
        | {
            "feature_row_id": "later-origin",
            "windows": {
                **request.windows.model_dump(),
                "decision_at": DECISION + timedelta(days=7),
                "observation_window_end": request.windows.observation_window_end
                + timedelta(days=7),
                "reference": {
                    "start": request.windows.reference.start + timedelta(days=7),
                    "end": request.windows.reference.end + timedelta(days=7),
                },
                "target": {
                    "start": request.windows.target.start + timedelta(days=7),
                    "end": request.windows.target.end + timedelta(days=7),
                },
            },
        }
    )
    source = _observations(request)

    first, second = build_features(source.lazy(), [request, later], "reconstructed")

    assert first.forecast_eligible is True
    assert second.complete_history_days == 77
    assert second.values["downloads_7d"] is None
    assert second.values["observation_age_hours"] == 216


def test_future_revision_cannot_change_features() -> None:
    """A later vendor correction never leaks through an earlier decision cutoff."""
    request = _request()
    source = _observations(request)
    future = source.tail(1).with_columns(
        pl.lit("future-correction").alias("revision_id"),
        pl.lit(999999).cast(pl.Int64).alias("value"),
        pl.lit(DECISION + timedelta(microseconds=1)).alias("available_at"),
    )

    original = build_features(source.lazy(), [request], "reconstructed")
    revised = build_features(
        pl.concat([source, future]).lazy(), [request], "reconstructed"
    )

    assert original == revised


def test_weekly_dispersion_uses_eleven_ordered_adjacent_changes() -> None:
    """Dispersion is the sample standard deviation of twelve weekly log totals."""
    request = _request()
    source = (
        _observations(request)
        .with_row_index("index")
        .with_columns((pl.col("index") // 7 + 1).cast(pl.Int64).alias("value"))
    )
    expected = pl.Series([log1p(7 * week) for week in range(1, 13)]).diff().std()

    (row,) = build_features(source.lazy(), [request], "reconstructed")

    assert row.values["weekly_log_change_std_11"] == pytest.approx(expected)
