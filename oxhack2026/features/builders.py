"""Bounded C1 snapshots aggregated into versioned C2 features and separate labels."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from math import cos, log1p, pi, sin
from typing import Self

import polars as pl
from pydantic import model_validator

from oxhack2026.features.definitions import HISTORY_DAYS, require_utc
from oxhack2026.features.snapshots import daily_snapshot
from oxhack2026.models.contracts import (
    Contract,
    FeatureRow,
    ForecastMode,
    LabelRow,
    RowIdentity,
    TargetWindows,
)
from oxhack2026.storage.contracts import ObservationSeries

FEATURE_SCHEMA_VERSION = "downloads-features-v1"
_TOTAL_DAYS = (7, 28, 30, 56, 60, 84)


class FeatureRequest(Contract):
    """Frozen, verified package identity and exact windows for one feature row.

    Attributes:
        feature_row_id: Immutable caller-assigned row identity within the dataset.
        identity: Catalogue-resolved tool, organization, package and versions.
        windows: Validated Monday origin and fixed-lag target/reference windows.
        series: C1 daily download series for that exact package and ecosystem.

    Raises:
        ValueError: The series does not describe the selected package downloads.
    """

    feature_row_id: str
    identity: RowIdentity
    windows: TargetWindows
    series: ObservationSeries

    @model_validator(mode="after")
    def _validate_series(self) -> Self:
        if (
            self.series.entity_id != self.identity.package_id
            or self.series.entity_kind != "package"
            or self.series.ecosystem != self.identity.ecosystem
            or self.series.source != self.identity.ecosystem
            or self.series.unit != "downloads"
        ):
            message = "Feature series must match the frozen package and ecosystem"
            raise ValueError(message)
        return self


def request_grid(
    requests: Sequence[FeatureRequest], as_of: datetime | None = None
) -> pl.LazyFrame:
    """Project exact feature or label windows for the shared daily snapshot join.

    Args:
        requests: Unique frozen package/origin requests.
        as_of: Label-vintage UTC cutoff, or None for anchored feature histories.
    Returns:
        Typed lazy request grid, including a valid empty-batch schema.
    Raises:
        ValueError: IDs repeat or the supplied cutoff is not UTC.
    """
    if as_of is not None:
        require_utc(as_of)
    if len({row.feature_row_id for row in requests}) != len(requests):
        message = "Feature requests require unique row IDs"
        raise ValueError(message)
    return pl.DataFrame(
        {
            "request_id": [row.feature_row_id for row in requests],
            "series_id": [row.series.series_id for row in requests],
            "window_start": [
                row.windows.target.start
                if as_of is not None
                else row.windows.observation_window_end - timedelta(days=HISTORY_DAYS)
                for row in requests
            ],
            "window_end": [
                row.windows.target.end
                if as_of is not None
                else row.windows.observation_window_end
                for row in requests
            ],
            "query_at": [as_of or row.windows.decision_at for row in requests],
        },
        schema_overrides={
            "request_id": pl.String,
            "series_id": pl.String,
            "window_start": pl.Datetime("us", "UTC"),
            "window_end": pl.Datetime("us", "UTC"),
            "query_at": pl.Datetime("us", "UTC"),
        },
    ).lazy()


def _complete_total(condition: pl.Expr, expected: int) -> pl.Expr:
    values = pl.col("downloads").filter(condition)
    return pl.when(values.count() == expected).then(values.cast(pl.Int128).sum())


def _aggregates(daily: pl.LazyFrame) -> pl.DataFrame:
    daily = daily.with_columns(
        (pl.col("window_end") - pl.col("day")).dt.total_days().alias("days_ago"),
        pl.col("downloads").cast(pl.Float64).alias("count_float"),
    )
    totals = daily.group_by("request_id").agg(
        pl.col("downloads").count().alias("complete_days"),
        pl.col("revision_id")
        .drop_nulls()
        .sort_by(pl.col("day").filter(pl.col("revision_id").is_not_null())),
        (
            pl.col("day").filter(pl.col("downloads").is_not_null()).max()
            + pl.duration(days=1)
        ).alias("last_complete_end"),
        *[
            _complete_total(pl.col("days_ago") <= days, days)
            .cast(pl.Float64)
            .alias(f"downloads_{days}d")
            for days in _TOTAL_DAYS
        ],
        *[
            _complete_total(
                (pl.col("days_ago") > days) & (pl.col("days_ago") <= 2 * days),
                days,
            )
            .cast(pl.Float64)
            .alias(f"previous_{days}d")
            for days in (28, 30)
        ],
        *[
            pl.when(pl.col("downloads").count() == HISTORY_DAYS)
            .then(
                pl.col("count_float")
                .filter(pl.col("day").dt.weekday() == weekday)
                .sum()
                / pl.when(pl.col("count_float").sum() > 0).then(
                    pl.col("count_float").sum()
                )
            )
            .alias(f"weekday_share_{weekday}")
            for weekday in range(1, 8)
        ],
    )
    weekly = (
        daily.with_columns(((pl.col("days_ago") - 1) // 7).alias("week"))
        .group_by("request_id", "week")
        .agg(_complete_total(pl.lit(True), 7).cast(pl.Float64).alias("weekly_total"))
        .sort("request_id", "week", descending=[False, True])
        .with_columns(
            pl.col("weekly_total").log1p().diff().over("request_id").alias("change")
        )
        .group_by("request_id")
        .agg(
            pl.when(pl.col("change").count() == 11)
            .then(pl.col("change").std(ddof=1))
            .alias("weekly_log_change_std_11")
        )
    )
    return totals.join(weekly, on="request_id").collect()


def build_features(
    revisions: pl.LazyFrame,
    requests: Sequence[FeatureRequest],
    mode: ForecastMode,
) -> tuple[FeatureRow, ...]:
    """Build download-only predictors without fitting or consulting future labels.

    Args:
        revisions: Typed frozen C1 observation-frame projection.
        requests: Catalogue-resolved requests; every requested row is retained.
        mode: Reconstructed or actual-collection-bounded prospective semantics.
    Returns:
        Ordered C2 rows. Totals require every expected day; eligibility requires
        all 84. Weekly dispersion uses eleven adjacent log1p-total differences.
        Unknown verified package age remains null. Weekday shares for all-zero
        history remain null, and coverage/freshness are explicit predictors.
    Raises:
        ValueError: Request IDs repeat or the snapshot mode is unsupported.
        polars.exceptions.PolarsError: Input schemas are incompatible.
    """
    if not requests:
        return ()
    summaries = _aggregates(daily_snapshot(revisions, request_grid(requests), mode))
    indexed = {row["request_id"]: row for row in summaries.iter_rows(named=True)}
    results: list[FeatureRow] = []
    for request in requests:
        summary = indexed[request.feature_row_id]
        values = {
            name: summary[name]
            for name in summaries.columns
            if name.startswith(("downloads_", "weekday_share_", "weekly_log_"))
        }
        for days in (28, 30):
            current, previous = (
                summary[f"downloads_{days}d"],
                summary[f"previous_{days}d"],
            )
            values[f"log_growth_{days}d"] = (
                None
                if current is None or previous is None
                else log1p(current) - log1p(previous)
            )
        reference_days = (
            request.windows.reference.end - request.windows.reference.start
        ).days
        reference = values[f"downloads_{reference_days}d"]
        last_complete = summary["last_complete_end"]
        phase = (
            2 * pi * (request.windows.decision_at.timetuple().tm_yday - 1) / 365.2425
        )
        values.update(
            log_reference=None if reference is None else log1p(reference),
            verified_package_age_days=None,
            annual_sin=sin(phase),
            annual_cos=cos(phase),
            history_coverage=summary["complete_days"] / HISTORY_DAYS,
            observation_age_hours=None
            if last_complete is None
            else (request.windows.decision_at - last_complete).total_seconds() / 3600,
        )
        eligible = summary["complete_days"] == HISTORY_DAYS
        results.append(
            FeatureRow(
                feature_row_id=request.feature_row_id,
                identity=request.identity,
                windows=request.windows,
                mode=mode,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                values=values,
                complete_history_days=summary["complete_days"],
                source_revision_ids=tuple(summary["revision_id"]),
                forecast_eligible=eligible,
                reason_codes=() if eligible else ("insufficient_history",),
            )
        )
    return tuple(results)


def build_labels(
    revisions: pl.LazyFrame,
    requests: Sequence[FeatureRequest],
    mode: ForecastMode,
    as_of: datetime,
) -> tuple[LabelRow, ...]:
    """Aggregate separate target truth at an explicit evaluation-vintage cutoff.

    Args:
        revisions: Frozen C1 observation-frame projection, potentially with revisions.
        requests: Exact feature identities and target windows to label.
        mode: Availability and actual-collection policy for outcome selection.
        as_of: UTC outcome-vintage cutoff, independent of the feature decision.
    Returns:
        Ordered labels with selected revision IDs. Totals and availability remain
        null until every target day is complete and known; true zero stays zero.
    Raises:
        ValueError: Cutoff is not UTC, IDs repeat, or mode is unsupported.
        polars.exceptions.PolarsError: Input schemas are incompatible.
    """
    require_utc(as_of)
    if not requests:
        return ()
    summary = (
        daily_snapshot(revisions, request_grid(requests, as_of), mode)
        .group_by("request_id")
        .agg(
            pl.when(pl.col("downloads").count() == pl.len())
            .then(pl.col("downloads").cast(pl.Int128).sum())
            .alias("actual"),
            pl.col("knowledge_at").max().alias("available_at"),
            pl.col("revision_id").drop_nulls().sort().alias("revision_ids"),
        )
        .collect()
    )
    indexed = {row["request_id"]: row for row in summary.iter_rows(named=True)}
    return tuple(
        LabelRow(
            feature_row_id=request.feature_row_id,
            windows=request.windows,
            actual_downloads=indexed[request.feature_row_id]["actual"],
            available_at=indexed[request.feature_row_id]["available_at"]
            if indexed[request.feature_row_id]["actual"] is not None
            else None,
            outcome_revision_ids=tuple(indexed[request.feature_row_id]["revision_ids"]),
        )
        for request in requests
    )
