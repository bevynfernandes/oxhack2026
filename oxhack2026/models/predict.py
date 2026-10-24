"""Immutable baseline forecast batches from frozen C1 observations."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

import polars as pl

from oxhack2026.features.builders import (
    FEATURE_SCHEMA_VERSION,
    FeatureRequest,
    request_grid,
)
from oxhack2026.features.definitions import HISTORY_DAYS, MIN_REFERENCE_COUNT
from oxhack2026.features.snapshots import daily_snapshot
from oxhack2026.models.baselines import damped_trend, persistence, weekday_seasonal
from oxhack2026.models.contracts import ForecastMode, ForecastResult, ReasonCode

BaselineKind = Literal["persistence", "weekday_seasonal", "damped_trend"]


@dataclass(frozen=True)
class BaselineSpec:
    """Frozen baseline kind, experiment, batch/model identity and collection mode."""

    kind: BaselineKind
    model_id: str
    experiment_id: str
    batch_id: str
    mode: ForecastMode


def baseline_forecasts(
    revisions: pl.LazyFrame,
    requests: Sequence[FeatureRequest],
    spec: BaselineSpec,
) -> tuple[ForecastResult, ...]:
    """Produce count-level exploratory forecasts without dropping missing tools.

    Args:
        revisions: Frozen, typed C1 observation projection, never a live vendor read.
        requests: Catalogue-resolved identities and exact target windows.
        spec: Predeclared baseline and immutable output identity.
    Returns:
        Ordered pre-reveal C2 results. All baselines share the 84-complete-day
        eligibility rule, and low-reference tools retain count forecasts with
        growth/ranking disabled. Intervals remain absent pending empirical gates.
    Raises:
        ValueError: Baseline/identities are invalid, request IDs repeat, scope is
            mixed, or counts cannot satisfy the baseline's numerical contract.
        polars.exceptions.PolarsError: Input schemas are incompatible.
    """
    if spec.kind not in {"persistence", "weekday_seasonal", "damped_trend"}:
        message = "Unsupported predeclared baseline"
        raise ValueError(message)
    if not all((spec.model_id, spec.experiment_id, spec.batch_id)):
        message = "Baseline output requires immutable model, experiment and batch IDs"
        raise ValueError(message)
    if not requests:
        return ()
    if (
        len(
            {
                (
                    row.identity.ecosystem,
                    row.identity.dataset_version,
                    row.identity.mapping_version,
                    row.windows,
                )
                for row in requests
            }
        )
        != 1
    ):
        message = (
            "A baseline batch requires one frozen ecosystem, dataset and target origin"
        )
        raise ValueError(message)
    summaries = (
        daily_snapshot(revisions, request_grid(requests), spec.mode)
        .group_by("request_id")
        .agg(pl.col("downloads").sort_by("day"))
        .collect()
    )
    indexed = {
        row["request_id"]: row["downloads"] for row in summaries.iter_rows(named=True)
    }
    results: list[ForecastResult] = []
    for request in requests:
        history: list[int | None] = indexed[request.feature_row_id]
        complete = len(history) == HISTORY_DAYS and all(
            value is not None for value in history
        )
        days = (request.windows.reference.end - request.windows.reference.start).days
        reference = (
            sum(value for value in history[-days:] if value is not None)
            if complete
            else None
        )
        prediction: float | None = None
        if reference is not None:
            previous = sum(
                value for value in history[-2 * days : -days] if value is not None
            )
            prediction = _baseline_prediction(
                spec.kind, history, (reference, previous), request
            )
        rankable = reference is not None and reference >= MIN_REFERENCE_COUNT
        reasons: list[ReasonCode] = ["unvalidated_interval"]
        if not complete:
            reasons.append("insufficient_history")
        elif not rankable:
            reasons.append("low_reference_count")
        digest = sha256(
            f"{spec.batch_id}:{spec.model_id}:{request.feature_row_id}".encode()
        ).hexdigest()
        results.append(
            ForecastResult(
                forecast_id=f"forecast-{digest}",
                batch_id=spec.batch_id,
                identity=request.identity,
                windows=request.windows,
                feature_row_id=request.feature_row_id,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                model_id=spec.model_id,
                experiment_id=spec.experiment_id,
                mode=spec.mode,
                evidence_status="exploratory",
                reference_downloads=reference,
                predicted_downloads=prediction,
                predicted_growth_pct=100 * (prediction / reference - 1)
                if rankable and prediction is not None and reference is not None
                else None,
                estimate_kind="baseline",
                baseline_model_id=spec.model_id,
                baseline_predicted_downloads=prediction,
                forecast_status="ready" if prediction is not None else "unavailable",
                ranking_eligible=rankable,
                reason_codes=tuple(reasons),
                data_age_hours=None if not complete else 48,
            )
        )
    return tuple(results)


def _baseline_prediction(
    kind: BaselineKind,
    history: Sequence[int | None],
    counts: tuple[int, int],
    request: FeatureRequest,
) -> float:
    reference, previous = counts
    if kind == "persistence":
        return persistence(reference)
    if kind == "weekday_seasonal":
        return weekday_seasonal(history[-28:], request.windows)
    return damped_trend(reference, previous, request.windows)
