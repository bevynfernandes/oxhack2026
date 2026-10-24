"""Point-in-time annual-report timing features, without financial-value inference."""

from collections.abc import Mapping
from datetime import date

import polars as pl

DISCLOSURE_TIMING_FEATURES = (
    "report_lag_days",
    "previous_report_lag_days",
    "days_since_previous_annual_filing",
    "report_lag_change_days",
    "missing_previous_report",
)

_ANNUAL_FORMS = ("10K", "10K405", "10KSB", "10KSB40", "10KT")


def _sec_filing_columns(payload: object) -> pl.DataFrame:
    if not isinstance(payload, dict):
        message = "SEC filing history must be a columnar object"
        raise TypeError(message)
    columns = ("form", "filingDate", "reportDate")
    arrays: list[list[str]] = []
    for name in columns:
        values = payload.get(name)
        if not isinstance(values, list) or any(
            not isinstance(value, str) for value in values
        ):
            message = "SEC date/form fields must contain arrays of strings"
            raise ValueError(message)
        arrays.append(values)
    if len({len(values) for values in arrays}) != 1:
        message = "SEC filing history arrays have different lengths"
        raise ValueError(message)
    return pl.DataFrame(
        dict(zip(columns, arrays, strict=True)),
        schema=dict.fromkeys(columns, pl.String),
    )


def sec_disclosure_timing(
    payload: object,
    issuer_id: str,
    as_of: date,
    historical: Mapping[str, object] | None = None,
) -> pl.DataFrame:
    """Use SEC submissions metadata to reproduce the research timing features.

    Args:
        payload: Retained root SEC submissions JSON for the verified issuer.
        issuer_id: Independently verified ten-digit CIK, including leading zeros.
        as_of: End-of-day cutoff; later filing dates cannot affect these features.
        historical: Retained additional JSON pages, keyed by the exact filenames
            declared in filings.files. Every declared page must be supplied.
    Returns:
        Causal annual-report timing rows through the cutoff, using the same feature
        function as training. An empty history remains empty, never a zero score.
        Successful parsing does not authorize applying the research model.
    Raises:
        ValueError: Identity, pagination, arrays or annual-report dates are invalid.
        TypeError: Root or historical filing metadata is not a JSON object.
        polars.exceptions.PolarsError: Required dates cannot be parsed.
    """
    if (
        len(issuer_id) != 10
        or not issuer_id.isascii()
        or not issuer_id.isdigit()
        or not isinstance(payload, dict)
        or str(payload.get("cik", "")).zfill(10) != issuer_id
    ):
        message = "SEC submissions CIK does not match the verified issuer"
        raise ValueError(message)
    filings = payload.get("filings")
    if not isinstance(filings, dict) or not isinstance(filings.get("files"), list):
        message = "SEC submissions must declare recent and historical pages"
        raise TypeError(message)
    pages = [_sec_filing_columns(filings.get("recent"))]
    supplied = historical or {}
    seen: set[str] = set()
    for reference in filings["files"]:
        name = reference.get("name") if isinstance(reference, dict) else None
        if not isinstance(name, str) or name in seen or name not in supplied:
            message = "SEC submissions history is incomplete or ambiguous"
            raise ValueError(message)
        seen.add(name)
        pages.append(_sec_filing_columns(supplied[name]))
    frame = (
        pl.concat(pages)
        .filter(pl.col("form").str.replace_all("-", "").is_in(_ANNUAL_FORMS))
        .select(
            pl.lit(issuer_id).alias("issuer_id"),
            pl.col("filingDate").str.to_date().alias("filing_date"),
            pl.col("reportDate").str.to_date().alias("period_end"),
        )
        .filter(pl.col("filing_date") <= as_of)
    )
    return disclosure_timing_frame(frame)


def disclosure_timing_frame(filings: pl.DataFrame) -> pl.DataFrame:
    """Derive disclosure timing using strictly earlier reports for the same issuer.

    Args:
        filings: Columns issuer_id (String), filing_date (Date), period_end (Date).
            Include complete available annual filing history, not future outcomes.
    Returns:
        Unique, chronologically sorted issuer/filing rows with five day/indicator
        features. The first report has explicit missing previous-history values.
    Raises:
        ValueError: Required columns/types are absent, dates are null/reversed, or
            one issuer/date ambiguously refers to different reporting periods.
        polars.exceptions.PolarsError: Input operations cannot be evaluated.
    """
    required = {
        "issuer_id": pl.String,
        "filing_date": pl.Date,
        "period_end": pl.Date,
    }
    if any(filings.schema.get(key) != value for key, value in required.items()):
        message = "Disclosure timing requires issuer IDs and Date-typed filing periods"
        raise ValueError(message)
    frame = filings.select(*required).unique()
    invalid = frame.filter(
        pl.any_horizontal(pl.all().is_null())
        | (pl.col("filing_date") < pl.col("period_end"))
    )
    ambiguous = (
        frame.group_by("issuer_id", "filing_date")
        .agg(pl.col("period_end").n_unique().alias("periods"))
        .filter(pl.col("periods") > 1)
    )
    if invalid.height or ambiguous.height:
        message = "Annual filing dates must be complete, chronological and unambiguous"
        raise ValueError(message)
    return (
        frame.sort("issuer_id", "filing_date")
        .with_columns(
            (pl.col("filing_date") - pl.col("period_end"))
            .dt.total_days()
            .alias("report_lag_days")
        )
        .with_columns(
            pl.col("filing_date").shift(1).over("issuer_id").alias("previous_date"),
            pl.col("report_lag_days")
            .shift(1)
            .over("issuer_id")
            .alias("previous_report_lag_days"),
        )
        .with_columns(
            (pl.col("filing_date") - pl.col("previous_date"))
            .dt.total_days()
            .alias("days_since_previous_annual_filing"),
            (pl.col("report_lag_days") - pl.col("previous_report_lag_days")).alias(
                "report_lag_change_days"
            ),
            pl.col("previous_date")
            .is_null()
            .cast(pl.Int8)
            .alias("missing_previous_report"),
        )
        .drop("previous_date")
    )
