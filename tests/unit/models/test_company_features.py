"""Company predictors preserve source cutoff, missingness and public access policy."""

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.features.company import company_feature_frame

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"


def _source() -> CompanySourceSnapshot:
    return CompanySourceSnapshot.model_validate_json(FIXTURE.read_bytes())


def _metric(
    frame: pl.DataFrame, metric_id: str = "sdk_downloads_30d_v1"
) -> dict[str, object]:
    return frame.filter(
        (pl.col("company_id") == "alpha") & (pl.col("metric_id") == metric_id)
    ).row(0, named=True)


def test_zero_missing_and_scope_survive_without_imputation() -> None:
    """A real zero is an observed predictor; missing cash flow remains null."""
    source = _source()

    frame = company_feature_frame(source)

    zero = _metric(frame)
    assert zero["value"] == 0.0
    assert zero["state"] == "observed"
    assert zero["scope"] == "product"
    assert zero["unit"] == "downloads"
    assert zero["evidence_ids"] == ["alpha-source"]
    missing = _metric(frame, "operating_cashflow_12m_usd_v1")
    assert missing["value"] is None
    assert missing["state"] == "missing"
    assert missing["currency"] == "USD"
    assert frame.height == len(source.metrics)
    assert zero["decision_at"] == source.as_of
    assert zero["source_snapshot_id"] == source.snapshot_id
    assert zero["cohort_version"] == source.cohort_version
    assert zero["source_mode"] == source.mode
    assert zero["synthetic"] is True
    assert frame.schema["decision_at"] == pl.Datetime("us", "UTC")
    assert "label_state" not in frame.columns
    assert "success_probability" not in frame.columns


@pytest.mark.parametrize(
    "access,review,expected",
    [
        ("restricted", "verified", "restricted"),
        ("public", "unreviewed", "unverified"),
        ("public", "disputed", "unverified"),
    ],
)
def test_restricted_or_unreviewed_values_are_not_model_inputs(
    access: str, review: str, expected: str
) -> None:
    """The presence of a numeric source value does not establish its usability."""
    payload = _source().model_dump(mode="json")
    payload["evidence"][0].update(access=access, review_state=review)
    if access == "restricted":
        payload["evidence"][0]["url"] = None
    source = CompanySourceSnapshot.model_validate(payload)

    result = _metric(company_feature_frame(source))

    assert result["state"] == expected
    assert result["value"] is None
    assert result["evidence_ids"] == []


@pytest.mark.parametrize("state", ["not_applicable", "conflicting"])
def test_nonobserved_source_state_is_retained(state: str) -> None:
    """Inapplicability and conflicting evidence are distinct from observed zero."""
    payload = _source().model_dump(mode="json")
    payload["metrics"][0].update(state=state, value=None, reason="Source review.")
    source = CompanySourceSnapshot.model_validate(payload)

    result = _metric(company_feature_frame(source))

    assert result["state"] == state
    assert result["value"] is None
    assert result["evidence_ids"] == []


def test_freshness_boundary_uses_measurement_time_at_frozen_cutoff() -> None:
    """Exactly maximum age remains usable; collection/recording cannot freshen it."""
    payload = _source().model_dump(mode="json")
    payload["metrics"][0]["window"]["end"] = "2025-01-29T00:00:00Z"
    payload["definitions"][0]["maximum_age_days"] = 3
    boundary = CompanySourceSnapshot.model_validate(payload)
    payload["definitions"][0]["maximum_age_days"] = 2
    stale = CompanySourceSnapshot.model_validate(payload)

    assert _metric(company_feature_frame(boundary))["state"] == "observed"
    result = _metric(company_feature_frame(stale))
    assert result["state"] == "stale"
    assert result["value"] is None


@pytest.mark.parametrize("value", [True, False])
def test_boolean_predictors_are_explicit_zero_or_one(value: bool) -> None:
    """A Boolean predictor is numeric without becoming a company-success score."""
    payload = _source().model_dump(mode="json")
    payload["definitions"][0]["value_kind"] = "boolean"
    for metric in payload["metrics"]:
        if metric["metric_id"] == payload["definitions"][0]["metric_id"]:
            metric["value"] = {"kind": "boolean", "value": value}
    source = CompanySourceSnapshot.model_validate(payload)

    assert _metric(company_feature_frame(source))["value"] == float(value)


@pytest.mark.parametrize(
    "value,state", [("1e1000", "numeric_overflow"), ("1e-1000", "numeric_underflow")]
)
def test_unrepresentable_values_stay_missing(value: str, state: str) -> None:
    """Exact source decimals cannot become infinite or a spurious model zero."""
    payload = _source().model_dump(mode="json")
    metric = next(
        row
        for row in payload["metrics"]
        if row["company_id"] == "alpha"
        and row["metric_id"] == "operating_cashflow_12m_usd_v1"
    )
    metric.update(
        state="observed",
        value={"kind": "decimal", "value": value},
        reason=None,
        evidence_ids=["alpha-source"],
    )
    source = CompanySourceSnapshot.model_validate(payload)

    result = _metric(company_feature_frame(source), "operating_cashflow_12m_usd_v1")

    assert result["state"] == state
    assert result["value"] is None


def test_source_order_does_not_change_features() -> None:
    """The exact publication deterministically defines the model-input rows."""
    source = _source()
    payload = source.model_dump(mode="json")
    for key in ("companies", "definitions", "metrics", "evidence"):
        payload[key].reverse()
    reordered = CompanySourceSnapshot.model_validate(payload)

    assert_frame_equal(company_feature_frame(source), company_feature_frame(reordered))
