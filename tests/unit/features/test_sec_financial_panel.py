"""Financial ratios remain causal and follow-up gaps remain censored."""

from datetime import date

import polars as pl
import pytest

from oxhack2026.features.sec_financial_panel import (
    FINANCIAL_FEATURES,
    annual_financial_component_panel,
    annual_financial_features,
)
from oxhack2026.features.sec_financials import ANNUAL_FINANCIAL_CONCEPTS


def _observations() -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for offset in range(3):
        values = {
            "revenue": [100.0, 120.0, 121.0][offset],
            "operating_cash_flow": [10.0, -5.0, 3.0][offset],
            "assets": 200.0,
            "liabilities": 80.0,
            "cash_and_equivalents": 20.0,
            "current_assets": 50.0,
            "current_liabilities": 25.0,
            "gross_profit": 60.0,
            "net_income": 5.0,
        }
        rows.extend(
            {
                "issuer_id": "0000000002",
                "accession_number": f"0000000002-{11 + offset:02d}-000001",
                "filing_date": date(2011 + offset, 2, 1),
                "period_end": date(2010 + offset, 12, 31),
                "form": "10-K",
                "metric": metric,
                "value": values[metric],
                "status": "observed",
            }
            for metric in ANNUAL_FINANCIAL_CONCEPTS
        )
    return pl.DataFrame(rows)


def test_origin_ratios_do_not_depend_on_future_reports() -> None:
    """The first filing's shared inputs are identical with or without later data."""
    observations = _observations()
    all_features = annual_financial_features(observations)
    origin_only = annual_financial_features(
        observations.filter(pl.col("filing_date") == date(2011, 2, 1))
    )
    assert all_features.head(1).equals(origin_only)
    first = all_features.row(0, named=True)
    assert first["operating_cash_flow_margin"] == 0.1
    assert first["liabilities_to_assets"] == 0.4
    assert first["cash_to_assets"] == 0.1
    assert first["current_ratio"] == 2
    assert first["report_lag_days"] == 32


def test_invalid_denominators_and_conflicting_values_stay_null() -> None:
    """Zero denominators and conflict status cannot become financial ratios."""
    observations = _observations().with_columns(
        pl.when(pl.col("metric").is_in(["revenue", "assets", "current_liabilities"]))
        .then(0.0)
        .otherwise(pl.col("value"))
        .alias("value"),
        pl.when(pl.col("metric") == "net_income")
        .then(pl.lit("conflicting"))
        .otherwise(pl.col("status"))
        .alias("status"),
    )
    result = annual_financial_features(observations)
    assert result.select(FINANCIAL_FEATURES[:-1]).null_count().row(0) == (3,) * 8
    assert result["net_income"].null_count() == 3


def test_growth_uses_two_fiscal_year_endpoint_and_retains_censoring() -> None:
    """An observed revenue increase gets a label; missing follow-up is never failure."""
    result = annual_financial_component_panel(_observations(), "revenue_growth_2fy")
    assert result["target"].to_list() == [1, None, None]
    assert result["partition"].to_list() == ["train", "train", "train"]
    first = result.row(0, named=True)
    assert first["endpoint_accession_number"] == "0000000002-13-000001"
    assert first["label_available_at"] == date(2013, 2, 1)
    assert first["revenue"] == 100


def test_cash_flow_zero_is_negative_but_absence_is_censored() -> None:
    """Next-period reported zero differs from an unavailable endpoint."""
    observations = _observations().with_columns(
        pl.when(
            (pl.col("period_end") == date(2011, 12, 31))
            & (pl.col("metric") == "operating_cash_flow")
        )
        .then(0.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    result = annual_financial_component_panel(
        observations, "positive_operating_cash_flow_1fy"
    )
    assert result["target"].to_list() == [0, 1, None]


def test_fiscal_calendar_tolerance_and_label_maturity_are_enforced() -> None:
    """An endpoint beyond the period tolerance cannot label a different fiscal year."""
    observations = _observations().with_columns(
        pl.when(pl.col("period_end") == date(2012, 12, 31))
        .then(pl.lit(date(2012, 11, 30)))
        .otherwise(pl.col("period_end"))
        .alias("period_end")
    )
    result = annual_financial_component_panel(observations, "revenue_growth_2fy")
    assert result["target"].null_count() == result.height
    late = _observations().with_columns(
        pl.when(pl.col("filing_date") == date(2013, 2, 1))
        .then(pl.lit(date(2018, 2, 1)))
        .otherwise(pl.col("filing_date"))
        .alias("filing_date")
    )
    result = annual_financial_component_panel(late, "revenue_growth_2fy")
    assert result.row(0, named=True)["partition"] == "excluded"


@pytest.mark.parametrize("invalid", ["duplicate", "nonfinite"])
def test_invalid_observations_fail_explicitly(invalid: str) -> None:
    """Ambiguous or non-finite source observations cannot enter the panel."""
    observations = _observations()
    if invalid == "duplicate":
        observations = pl.concat([observations, observations.head(1)])
    else:
        observations = observations.with_columns(pl.lit(float("nan")).alias("value"))
    with pytest.raises(ValueError):
        annual_financial_features(observations)
