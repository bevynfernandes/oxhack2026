"""C1 daily revisions selected by measurement and knowledge time using Polars."""

from collections.abc import Iterable

import polars as pl

from oxhack2026.models.contracts import ForecastMode
from oxhack2026.storage.contracts import ObservationRevision

_UTC = pl.Datetime("us", "UTC")
_OBSERVATION_SCHEMA: dict[str, pl.DataType] = {
    "revision_id": pl.String(),
    "series_id": pl.String(),
    "day": _UTC,
    "value": pl.Int64(),
    "completeness": pl.String(),
    "available_at": _UTC,
    "first_collected_at": _UTC,
    "retrieved_at": _UTC,
}


def observation_frame(revisions: Iterable[ObservationRevision]) -> pl.DataFrame:
    """Project C1 revisions into the minimal typed analytical observation interface.

    Args:
        revisions: Validated revisions from one bounded, frozen C1 dataset read.
    Returns:
        Typed daily observations, including explicit missing/partial values. Empty
        input retains the same Arrow-compatible schema. No vendor reads occur.
    Raises:
        ValueError: If duplicate revision IDs occur within the frozen input.
        polars.exceptions.PolarsError: If supplied records cannot match the schema.
    """
    frame = pl.from_dicts(
        (
            {
                "revision_id": row.revision_id,
                "series_id": row.series_id,
                "day": row.window.start,
                "value": row.value,
                "completeness": row.completeness,
                "available_at": row.available_at,
                "first_collected_at": row.first_collected_at,
                "retrieved_at": row.retrieved_at,
            }
            for row in revisions
        ),
        schema=_OBSERVATION_SCHEMA,
    )
    if frame["revision_id"].n_unique() != frame.height:
        message = "Frozen observations require unique immutable revision IDs"
        raise ValueError(message)
    return frame


def daily_snapshot(
    revisions: pl.LazyFrame, requests: pl.LazyFrame, mode: ForecastMode
) -> pl.LazyFrame:
    """Resolve daily vintages on bounded windows without rescanning full histories.

    Args:
        revisions: Observation-frame columns from a validated immutable C1 bundle.
        requests: Request ID, series_id, window_start/window_end, and query_at;
            timestamps are UTC microseconds and windows are midnight half-open.
            Feature queries use the decision cutoff and fixed anchored history.
            Labels use the separately chosen evaluation/outcome-vintage cutoff.
        mode: Reconstructed permits later-collected revisions whose documented
            availability bound was earlier. Prospective also requires actual
            collection before query_at. Neither mode admits future-available data.
    Returns:
        Lazy daily grid retaining every expected day, selected revision/provenance,
        and nullable downloads. Missing and partial counts stay null; real zeros
        remain zero. Latest eligible knowledge time wins; equal assumed bounds
        use latest actual collection/retrieval and stable revision-ID ordering.
    Raises:
        ValueError: If the mode is unsupported.
        polars.exceptions.PolarsError: On incompatible schemas at collection time.
    """
    if mode not in {"reconstructed", "prospective"}:
        message = "Snapshot mode must be reconstructed or prospective"
        raise ValueError(message)
    knowledge = pl.col("available_at")
    if mode == "prospective":
        knowledge = pl.max_horizontal("available_at", "first_collected_at")
    vintages = (
        revisions.select(*_OBSERVATION_SCHEMA)
        .with_columns(knowledge.alias("knowledge_at"))
        .sort(["knowledge_at", "first_collected_at", "retrieved_at", "revision_id"])
    )
    grid = (
        requests.with_columns(
            pl.datetime_ranges(
                "window_start",
                "window_end",
                interval="1d",
                closed="left",
                time_unit="us",
                time_zone="UTC",
            ).alias("day")
        )
        .explode("day", empty_as_null=False)
        .sort("query_at")
    )
    return grid.join_asof(
        vintages,
        left_on="query_at",
        right_on="knowledge_at",
        by=["series_id", "day"],
        strategy="backward",
        check_sortedness=False,
    ).with_columns(
        pl.when(pl.col("completeness") == "complete")
        .then(pl.col("value"))
        .otherwise(None)
        .alias("downloads")
    )
