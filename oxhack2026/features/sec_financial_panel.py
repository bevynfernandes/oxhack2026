"""Shared financial ratios and explicitly censored annual component labels."""

import hashlib
from typing import Literal

import polars as pl

from oxhack2026.features.sec_financials import ANNUAL_FINANCIAL_CONCEPTS

FinancialComponent = Literal["revenue_growth_2fy", "positive_operating_cash_flow_1fy"]
FINANCIAL_FEATURES = (
    "log_revenue",
    "log_assets",
    "operating_cash_flow_margin",
    "net_income_margin",
    "gross_margin",
    "liabilities_to_assets",
    "cash_to_assets",
    "current_ratio",
    "report_lag_days",
)
_KEYS = ["issuer_id", "accession_number", "filing_date", "period_end", "form"]
_RATIOS = {
    "operating_cash_flow_margin": ("operating_cash_flow", "revenue"),
    "net_income_margin": ("net_income", "revenue"),
    "gross_margin": ("gross_profit", "revenue"),
    "liabilities_to_assets": ("liabilities", "assets"),
    "cash_to_assets": ("cash_and_equivalents", "assets"),
    "current_ratio": ("current_assets", "current_liabilities"),
}


def annual_financial_features(observations: pl.DataFrame) -> pl.DataFrame:
    """Project accession-specific observations into causal financial model inputs.

    Args:
        observations: Long rows from sec_annual_financials for one or more issuers.
    Returns:
        One row per original filing, retaining raw metrics and nine model features.
        Missing/conflicting values and invalid denominators become null, not zero.
        This function uses no endpoint labels and performs no fitted imputation.
    Raises:
        ValueError: A filing has duplicate metric rows or non-finite observed values.
        polars.exceptions.PolarsError: Required observation columns are absent.
    """
    if (
        observations.select("issuer_id", "accession_number", "metric")
        .is_duplicated()
        .any()
    ):
        message = "Annual financial observations have duplicate filing/metric rows"
        raise ValueError(message)
    if observations.filter(
        (pl.col("status") == "observed")
        & (pl.col("value").is_null() | ~pl.col("value").is_finite())
    ).height:
        message = "Observed annual financial values must be finite and present"
        raise ValueError(message)
    frame = (
        observations.with_columns(
            pl.when(pl.col("status") == "observed")
            .then(pl.col("value"))
            .otherwise(None)
            .alias("value")
        )
        .pivot(on="metric", index=_KEYS, values="value")
        .with_columns(
            *[
                pl.lit(None, dtype=pl.Float64).alias(metric)
                for metric in ANNUAL_FINANCIAL_CONCEPTS
                if metric not in observations["metric"].unique()
            ]
        )
    )
    return (
        frame.with_columns(
            *[
                pl.when(pl.col(metric) > 0)
                .then(pl.col(metric).log1p())
                .otherwise(None)
                .alias(f"log_{metric}")
                for metric in ("revenue", "assets")
            ],
            *[
                pl.when(pl.col(denominator) > 0)
                .then(pl.col(numerator) / pl.col(denominator))
                .otherwise(None)
                .alias(feature)
                for feature, (numerator, denominator) in _RATIOS.items()
            ],
            (pl.col("filing_date") - pl.col("period_end"))
            .dt.total_days()
            .cast(pl.Float64)
            .alias("report_lag_days"),
        )
        .with_columns(
            *[
                pl.when(pl.col(feature).is_finite())
                .then(pl.col(feature))
                .otherwise(None)
                .alias(feature)
                for feature in FINANCIAL_FEATURES
            ]
        )
        .sort("issuer_id", "filing_date", "accession_number")
    )


def annual_financial_component_panel(
    observations: pl.DataFrame, component: FinancialComponent
) -> pl.DataFrame:
    """Attach original-filing annual targets with fixed issuer and temporal cuts.

    Args:
        observations: Original annual financial observations, including missing rows.
        component: Two-fiscal-year revenue growth of at least 10%, or positive
            next-fiscal-year operating cash flow. Neither means business survival.
    Returns:
        Shared origin features, endpoint accession/date and nullable binary target.
        Endpoint period must be within 14 days of its fiscal-calendar anniversary.
        All censored origins remain visible. Partition maturity uses the endpoint
        filing date; issuer SHA256 buckets and year cuts match the frozen plan.
    Raises:
        ValueError: Component is unsupported or observations are ambiguous/invalid.
        polars.exceptions.PolarsError: Required columns or dates are invalid.
    """
    if component not in ("revenue_growth_2fy", "positive_operating_cash_flow_1fy"):
        message = "Unsupported SEC financial component target"
        raise ValueError(message)
    frame = annual_financial_features(observations)
    metric = "revenue" if component == "revenue_growth_2fy" else "operating_cash_flow"
    years = "2y" if component == "revenue_growth_2fy" else "1y"
    endpoints = (
        frame.sort("filing_date", "accession_number")
        .unique(subset=["issuer_id", "period_end"], keep="first")
        .select(
            "issuer_id",
            pl.col("period_end").alias("endpoint_period_end"),
            pl.col("filing_date").alias("label_available_at"),
            pl.col("accession_number").alias("endpoint_accession_number"),
            pl.col(metric).alias("endpoint_value"),
        )
        .sort("endpoint_period_end")
    )
    joined = (
        frame.with_columns(
            pl.col("period_end").dt.offset_by(years).alias("target_period")
        )
        .sort("target_period")
        .join_asof(
            endpoints,
            left_on="target_period",
            right_on="endpoint_period_end",
            by="issuer_id",
            strategy="nearest",
            tolerance="14d",
            check_sortedness=False,
        )
    )
    observed = pl.col("endpoint_value").is_not_null() & (
        pl.col("label_available_at") > pl.col("filing_date")
    )
    if component == "revenue_growth_2fy":
        observed &= (pl.col("revenue") > 0) & (pl.col("endpoint_value") >= 0)
        target = (pl.col("endpoint_value") / pl.col("revenue")) >= 1.1
    else:
        target = pl.col("endpoint_value") > 0
    buckets = pl.DataFrame(
        {
            "issuer_id": frame["issuer_id"].unique(),
        }
    ).with_columns(
        pl.col("issuer_id")
        .map_elements(
            lambda cik: hashlib.sha256(cik.encode()).digest()[0] % 10,
            return_dtype=pl.Int64,
        )
        .alias("issuer_bucket")
    )
    return (
        joined.join(buckets, on="issuer_id")
        .with_columns(
            pl.when(observed)
            .then(target.cast(pl.Int8))
            .otherwise(None)
            .alias("target"),
            pl.lit(component).alias("component"),
        )
        .with_columns(
            pl.when(
                (pl.col("issuer_bucket") <= 5)
                & pl.col("filing_date").dt.year().is_between(2011, 2014)
                & (
                    pl.col("label_available_at").is_null()
                    | (pl.col("label_available_at") < pl.date(2018, 1, 1))
                )
            )
            .then(pl.lit("train"))
            .when(
                pl.col("issuer_bucket").is_between(6, 7)
                & pl.col("filing_date").dt.year().is_between(2018, 2019)
                & (
                    pl.col("label_available_at").is_null()
                    | (pl.col("label_available_at") < pl.date(2023, 1, 1))
                )
            )
            .then(pl.lit("validation"))
            .when(
                (pl.col("issuer_bucket") >= 8)
                & pl.col("filing_date").dt.year().is_between(2023, 2024)
                & (
                    pl.col("label_available_at").is_null()
                    | (pl.col("label_available_at") <= pl.date(2026, 9, 30))
                )
            )
            .then(pl.lit("test"))
            .otherwise(pl.lit("excluded"))
            .alias("partition")
        )
        .sort("issuer_id", "filing_date", "accession_number")
    )
