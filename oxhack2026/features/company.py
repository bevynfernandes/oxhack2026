"""Model-input projection from exact company sources, without labels or imputation."""

from math import isfinite

import polars as pl

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.features.company_policy import company_metric_state

FEATURE_VERSION = "company-metric-features-v1"
_SCHEMA: dict[str, pl.DataType] = {
    "company_id": pl.String(),
    "metric_id": pl.String(),
    "observation_id": pl.String(),
    "metric_family": pl.String(),
    "scope": pl.String(),
    "unit": pl.String(),
    "currency": pl.String(),
    "value": pl.Float64(),
    "state": pl.String(),
    "measurement_end": pl.Datetime("us", "UTC"),
    "available_at": pl.Datetime("us", "UTC"),
    "collected_at": pl.Datetime("us", "UTC"),
    "evidence_ids": pl.List(pl.String),
    "source_snapshot_id": pl.String(),
    "decision_at": pl.Datetime("us", "UTC"),
    "cohort_version": pl.String(),
    "source_mode": pl.String(),
    "synthetic": pl.Boolean(),
    "feature_version": pl.String(),
}


def company_feature_frame(snapshot: CompanySourceSnapshot) -> pl.DataFrame:
    """Project typed metrics into a deterministic long-form numerical feature frame.

    Args:
        snapshot: Exact C1 publication loaded through its validated raw-byte reader.
            C1 already enforces company/source links, complete metric inventory,
            source availability and actual collection policy at its frozen cutoff.
    Returns:
        One row per company/metric, including unavailable and inapplicable rows.
        Only verified public, fresh observed values enter Float64 predictors;
        Boolean predictors use 0/1. Missingness is explicit and never imputed.
        Original units/scope and source/observation/evidence IDs remain attached.
        Overflow/underflow becomes a null with an explicit reason; C1 retains exact
        financial decimals. Source order never changes output order or feature names.

        This is a model-input projection, not a source record or serving contract.
        It contains no future labels, family assumptions, cohort eligibility or
        fitted preprocessing. Experiment code must separately resolve historical
        inclusion/families, freeze definitions/units, and fit preprocessing only
        on its training fold. Contemporary survivors are not a historical cohort.
    Raises:
        KeyError: Required source/definition references are absent from invalid input.
        ValueError: Invalid source values violate the validated C1 precondition.
    """
    definitions = {row.metric_id: row for row in snapshot.definitions}
    evidence = {row.evidence_id: row for row in snapshot.evidence}
    rows = []
    for observation in snapshot.metrics:
        definition = definitions[observation.metric_id]
        state: str = company_metric_state(
            observation, definition, evidence, snapshot.as_of
        )
        value: float | None = None
        if state == "observed":
            if observation.value is None:
                message = "Observed company metric requires a value"
                raise ValueError(message)
            else:
                try:
                    value = float(observation.value.value)
                except OverflowError:
                    state = "numeric_overflow"
                if value is not None and not isfinite(value):
                    value = None
                    state = "numeric_overflow"
                elif value == 0 and observation.value.value != 0:
                    value = None
                    state = "numeric_underflow"
        rows.append(
            {
                "company_id": observation.company_id,
                "metric_id": observation.metric_id,
                "observation_id": observation.observation_id,
                "metric_family": definition.family,
                "scope": definition.scope,
                "unit": definition.unit,
                "currency": definition.currency,
                "value": value,
                "state": state,
                "measurement_end": observation.measurement_end,
                "available_at": observation.available_at,
                "collected_at": observation.collected_at,
                "evidence_ids": sorted(observation.evidence_ids)
                if state == "observed"
                else [],
                "source_snapshot_id": snapshot.snapshot_id,
                "decision_at": snapshot.as_of,
                "cohort_version": snapshot.cohort_version,
                "source_mode": snapshot.mode,
                "synthetic": snapshot.synthetic,
                "feature_version": FEATURE_VERSION,
            }
        )
    return pl.DataFrame(rows, schema=_SCHEMA).sort("company_id", "metric_id")
