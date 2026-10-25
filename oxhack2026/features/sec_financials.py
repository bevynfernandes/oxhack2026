"""Accession-specific annual financial observations shared by training and serving."""

import math
import re
from collections import defaultdict
from datetime import date

import polars as pl

from oxhack2026.features.disclosure_timing import ANNUAL_DISCLOSURE_FORMS

ANNUAL_FINANCIAL_CONCEPTS = {
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "net_income": ("NetIncomeLoss",),
    "gross_profit": ("GrossProfit",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "cash_and_equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
}
_DURATION_METRICS = frozenset(
    ("revenue", "operating_cash_flow", "net_income", "gross_profit")
)
_FILING_SCHEMA = pl.Schema(
    {
        "accession_number": pl.String,
        "filing_date": pl.Date,
        "period_end": pl.Date,
        "form": pl.String,
    }
)
_OUTPUT_SCHEMA = pl.Schema(
    {
        "issuer_id": pl.String(),
        **_FILING_SCHEMA,
        "metric": pl.String(),
        "value": pl.Float64(),
        "period_start": pl.Date(),
        "unit": pl.String(),
        "concepts": pl.List(pl.String),
        "status": pl.String(),
    }
)


def _annual_filings(filings: pl.DataFrame, as_of: date) -> pl.DataFrame:
    if any(filings.schema.get(key) != value for key, value in _FILING_SCHEMA.items()):
        message = "Annual financials require accession/form strings and Date periods"
        raise ValueError(message)
    if (
        filings.select(*_FILING_SCHEMA)
        .filter(pl.any_horizontal(pl.all().is_null()))
        .height
    ):
        message = "Annual financial filing metadata cannot contain nulls"
        raise ValueError(message)
    frame = (
        filings.select(*_FILING_SCHEMA)
        .filter(pl.col("filing_date") <= as_of)
        .filter(pl.col("form").str.replace_all("-", "").is_in(ANNUAL_DISCLOSURE_FORMS))
        .unique()
    )
    invalid = frame.filter(
        pl.any_horizontal(pl.all().is_null())
        | (pl.col("filing_date") < pl.col("period_end"))
        | ~pl.col("accession_number").str.contains(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
    )
    if invalid.height or frame["accession_number"].n_unique() != frame.height:
        message = "Annual financial filing metadata is invalid or ambiguous"
        raise ValueError(message)
    return frame.sort("filing_date", "accession_number")


def _financial_fact_index(
    payload: object, issuer_id: str
) -> dict[tuple[str, str], list[tuple[str, dict[str, object]]]]:
    if (
        re.fullmatch(r"[0-9]{10}", issuer_id) is None
        or not isinstance(payload, dict)
        or str(payload.get("cik", "")).zfill(10) != issuer_id
    ):
        message = "SEC companyfacts CIK does not match the verified issuer"
        raise ValueError(message)
    facts = payload.get("facts")
    taxonomy = facts.get("us-gaap", {}) if isinstance(facts, dict) else None
    if not isinstance(taxonomy, dict):
        message = "SEC companyfacts must declare a facts object"
        raise TypeError(message)
    indexed: dict[tuple[str, str], list[tuple[str, dict[str, object]]]] = defaultdict(
        list
    )
    for metric, concepts in ANNUAL_FINANCIAL_CONCEPTS.items():
        for concept in concepts:
            entry = taxonomy.get(concept, {})
            units = entry.get("units", {}) if isinstance(entry, dict) else None
            observations = units.get("USD", []) if isinstance(units, dict) else None
            if not isinstance(observations, list):
                message = "SEC financial concept units must contain arrays"
                raise TypeError(message)
            for observation in observations:
                if not isinstance(observation, dict):
                    message = "SEC financial facts must be objects"
                    raise TypeError(message)
                accession = observation.get("accn")
                if isinstance(accession, str):
                    indexed[(accession, metric)].append((concept, observation))
    return indexed


def _resolve_metric(
    candidates: list[tuple[str, dict[str, object]]],
    metric: str,
    filing_date: date,
    period_end: date,
    form: str,
) -> dict[str, object]:
    observations: set[tuple[float, date | None]] = set()
    concepts: set[str] = set()
    for concept, fact in candidates:
        if (
            fact.get("filed") != filing_date.isoformat()
            or fact.get("end") != period_end.isoformat()
            or fact.get("form") != form
        ):
            continue
        start = fact.get("start")
        period_start = date.fromisoformat(start) if isinstance(start, str) else None
        if metric in _DURATION_METRICS:
            if (
                period_start is None
                or not 335 <= (period_end - period_start).days <= 395
            ):
                continue
        elif start is not None:
            continue
        value = fact.get("val")
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            message = "SEC financial values must be finite numbers"
            raise ValueError(message)
        observations.add((float(value), period_start))
        concepts.add(concept)
    value, period_start = (
        next(iter(observations)) if len(observations) == 1 else (None, None)
    )
    return {
        "metric": metric,
        "value": value,
        "period_start": period_start,
        "unit": "USD",
        "concepts": sorted(concepts),
        "status": (
            "observed"
            if len(observations) == 1
            else "conflicting"
            if observations
            else "missing"
        ),
    }


def sec_annual_financials(
    payload: object, filings: pl.DataFrame, issuer_id: str, as_of: date
) -> pl.DataFrame:
    """Extract original annual USD facts without substituting future restatements.

    Args:
        payload: Retained SEC companyfacts JSON; only standard consolidated US-GAAP
            concepts are supported. The API can omit custom or older facts.
        filings: Independently retained submissions metadata for this issuer, with
            accession_number/form String and filing_date/period_end Date columns.
            Include original annual reports; amendments and interim forms are ignored.
        issuer_id: Verified ten-digit SEC CIK; name similarity is insufficient.
        as_of: Inclusive end-of-day availability cutoff, not an intraday benchmark.
    Returns:
        One row per eligible filing and metric, with original accession, period,
        source concepts and observed/missing/conflicting status. Annual duration
        facts must end at the filing's report date and span 335-395 days. Conflicting
        values or periods remain null; duplicate identical facts are harmless.
        Cash here is reported cash/equivalents, not verified unrestricted runway.
        Current API data is a retrospective reconstruction, not a vintage snapshot.
    Raises:
        ValueError: Issuer, metadata, fact schema, numeric value or date is invalid.
        TypeError: Facts, units or observation JSON has an invalid structure.
        polars.exceptions.PolarsError: Input frame operations cannot be evaluated.
    """
    annual = _annual_filings(filings, as_of)
    indexed = _financial_fact_index(payload, issuer_id)
    rows = [
        {
            "issuer_id": issuer_id,
            **filing,
            **_resolve_metric(
                indexed.get((filing["accession_number"], metric), []),
                metric,
                filing["filing_date"],
                filing["period_end"],
                filing["form"],
            ),
        }
        for filing in annual.iter_rows(named=True)
        for metric in ANNUAL_FINANCIAL_CONCEPTS
    ]
    return pl.DataFrame(rows, schema=_OUTPUT_SCHEMA)
