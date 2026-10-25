"""Annual financial observations preserve original filing identity and missingness."""

from copy import deepcopy
from datetime import date

import polars as pl
import pytest

from oxhack2026.features.sec_financials import (
    sec_annual_filing_metadata,
    sec_annual_financials,
)

_CIK = "0000001750"
_ACCESSION = "0000001750-20-000001"


def _filings() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "accession_number": [_ACCESSION],
            "filing_date": [date(2020, 2, 1)],
            "period_end": [date(2019, 12, 31)],
            "form": ["10-K"],
        }
    )


def _fact(**changes: object) -> dict[str, object]:
    return {
        "accn": _ACCESSION,
        "form": "10-K",
        "filed": "2020-02-01",
        "start": "2019-01-01",
        "end": "2019-12-31",
        "val": 100,
        **changes,
    }


def _payload(facts: list[dict[str, object]]) -> dict[str, object]:
    return {"cik": 1750, "facts": {"us-gaap": {"Revenues": {"units": {"USD": facts}}}}}


def test_original_accession_excludes_restatements_quarters_and_prior_periods() -> None:
    """Future filings and comparative/quarter periods cannot replace revenue."""
    original = _fact()
    payload = _payload(
        [
            original,
            deepcopy(original),
            _fact(accn="0000001750-21-000001", filed="2021-02-01", val=900),
            _fact(form="10-K/A", val=800),
            _fact(start="2019-10-01", val=700),
            _fact(start="2018-01-01", end="2018-12-31", val=600),
        ]
    )
    actual = sec_annual_financials(payload, _filings(), _CIK, date(2020, 2, 1))
    expected = sec_annual_financials(
        _payload([original]), _filings(), _CIK, date(2020, 2, 1)
    )
    assert actual.equals(expected)
    revenue = actual.filter(pl.col("metric") == "revenue").row(0, named=True)
    assert revenue["value"] == 100
    assert revenue["status"] == "observed"
    assert revenue["period_start"] == date(2019, 1, 1)
    assert revenue["concepts"] == ["Revenues"]
    assert actual.filter(pl.col("status") == "missing").height == 8


@pytest.mark.parametrize("conflict", ["value", "period", "concept"])
def test_disagreeing_values_or_annual_periods_are_not_arbitrarily_selected(
    conflict: str,
) -> None:
    """Different values, durations and alternate tags remain explicit conflicts."""
    facts = [_fact()]
    if conflict == "value":
        facts.append(_fact(val=101))
    elif conflict == "period":
        facts.append(_fact(start="2018-12-31"))
    payload = _payload(facts)
    if conflict == "concept":
        payload = {
            "cik": 1750,
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": facts}},
                    "SalesRevenueNet": {"units": {"USD": [_fact(val=90)]}},
                }
            },
        }
    result = sec_annual_financials(payload, _filings(), _CIK, date(2020, 2, 1))
    row = result.filter(pl.col("metric") == "revenue").row(0, named=True)
    assert row["status"] == "conflicting"
    assert row["value"] is None


def test_cash_instant_zero_and_foreign_currency_remain_distinct() -> None:
    """Zero USD cash is observed, while non-USD revenue is unsupported and missing."""
    instant = _fact(val=0)
    instant.pop("start")
    payload = {
        "cik": 1750,
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [instant]}},
                "Revenues": {"units": {"CAD": [_fact()]}},
            }
        },
    }
    result = sec_annual_financials(payload, _filings(), _CIK, date(2020, 2, 1))
    cash = result.filter(pl.col("metric") == "cash_and_equivalents").row(0, named=True)
    revenue = result.filter(pl.col("metric") == "revenue").row(0, named=True)
    assert cash["value"] == 0
    assert cash["status"] == "observed"
    assert cash["period_start"] is None
    assert revenue["value"] is None
    assert revenue["status"] == "missing"


def test_cutoff_amendments_and_empty_history_preserve_schema() -> None:
    """Future origins and amendments supply no original annual observation rows."""
    for filings, cutoff in (
        (_filings(), date(2020, 1, 31)),
        (_filings().with_columns(pl.lit("10-K/A").alias("form")), date(2020, 2, 1)),
        (_filings().head(0), date(2020, 2, 1)),
    ):
        result = sec_annual_financials(_payload([_fact()]), filings, _CIK, cutoff)
        assert result.is_empty()
        assert result.schema["value"] == pl.Float64


@pytest.mark.parametrize("payload", [{}, {"cik": 1750}, {"cik": 1750, "facts": []}])
def test_malformed_root_json_cannot_be_reported_as_observed(
    payload: dict[str, object],
) -> None:
    """A damaged root response is different from a valid issuer with missing facts."""
    with pytest.raises((TypeError, ValueError)):
        sec_annual_financials(payload, _filings(), _CIK, date(2020, 2, 1))


@pytest.mark.parametrize(
    "failure", ["identity", "accession", "date", "duplicate", "value", "null", "schema"]
)
def test_invalid_identity_metadata_and_values_fail_explicitly(failure: str) -> None:
    """Invalid rows cannot quietly become plausible model inputs."""
    payload = _payload([_fact(val=True if failure == "value" else 100)])
    filings = _filings()
    issuer = _CIK
    if failure == "identity":
        issuer = "0000001751"
    elif failure == "accession":
        filings = filings.with_columns(pl.lit("bad").alias("accession_number"))
    elif failure == "date":
        filings = filings.with_columns(pl.lit(date(2021, 1, 1)).alias("period_end"))
    elif failure == "duplicate":
        filings = pl.concat(
            [
                filings,
                filings.with_columns(pl.lit(date(2018, 12, 31)).alias("period_end")),
            ]
        )
    elif failure == "null":
        filings = filings.with_columns(pl.lit(None, dtype=pl.Date).alias("filing_date"))
    elif failure == "schema":
        filings = filings.drop("form")
    with pytest.raises(ValueError):
        sec_annual_financials(payload, filings, issuer, date(2020, 2, 1))


def test_live_metadata_and_training_input_produce_identical_financials() -> None:
    """Live accession arrays reproduce the exact financial parser training schema."""
    payload = {
        "cik": 1750,
        "filings": {
            "recent": {
                "accessionNumber": [_ACCESSION],
                "filingDate": ["2020-02-01"],
                "reportDate": ["2019-12-31"],
                "form": ["10-K"],
            },
            "files": [],
        },
    }
    metadata = sec_annual_filing_metadata(payload, _CIK, date(2020, 2, 1))
    assert metadata.equals(_filings())
    assert sec_annual_financials(
        _payload([_fact()]), metadata, _CIK, date(2020, 2, 1)
    ).equals(
        sec_annual_financials(_payload([_fact()]), _filings(), _CIK, date(2020, 2, 1))
    )


def test_live_metadata_requires_complete_accession_arrays() -> None:
    """Dates without accession identity cannot select original financial facts."""
    payload = {
        "cik": 1750,
        "filings": {
            "recent": {
                "filingDate": ["2020-02-01"],
                "reportDate": ["2019-12-31"],
                "form": ["10-K"],
            },
            "files": [],
        },
    }
    with pytest.raises(ValueError, match="accession"):
        sec_annual_filing_metadata(payload, _CIK, date(2020, 2, 1))


def test_live_metadata_includes_declared_historical_accessions() -> None:
    """An empty recent page still yields financial history from the required page."""
    name = "CIK0000001750-submissions-001.json"
    recent = dict.fromkeys(("accessionNumber", "filingDate", "reportDate", "form"), [])
    payload = {"cik": 1750, "filings": {"recent": recent, "files": [{"name": name}]}}
    historical = {
        name: {
            "accessionNumber": [_ACCESSION],
            "filingDate": ["2020-02-01"],
            "reportDate": ["2019-12-31"],
            "form": ["10-K"],
        }
    }
    assert sec_annual_filing_metadata(
        payload, _CIK, date(2020, 2, 1), historical
    ).equals(_filings())
    with pytest.raises(ValueError, match="incomplete"):
        sec_annual_filing_metadata(payload, _CIK, date(2020, 2, 1))
