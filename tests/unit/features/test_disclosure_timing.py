"""Timing features remain causal, issuer-specific and explicit about missingness."""

from datetime import date

import polars as pl
import pytest

from oxhack2026.features.disclosure_timing import (
    disclosure_timing_frame,
    sec_disclosure_timing,
)


def test_timing_uses_only_strictly_earlier_issuer_reports() -> None:
    """Later reports and another issuer cannot change an earlier feature row."""
    filings = pl.DataFrame(
        {
            "issuer_id": ["a", "b", "a", "a"],
            "filing_date": [
                date(2020, 2, 1),
                date(2020, 2, 2),
                date(2021, 3, 1),
                date(2022, 4, 1),
            ],
            "period_end": [
                date(2019, 12, 31),
                date(2019, 12, 31),
                date(2020, 12, 31),
                date(2021, 12, 31),
            ],
        }
    )
    result = disclosure_timing_frame(filings)
    earlier = disclosure_timing_frame(filings.head(3))
    assert result.filter(pl.col("filing_date") <= date(2021, 3, 1)).equals(earlier)
    first = result.filter(pl.col("issuer_id") == "a").row(0, named=True)
    second = result.filter(pl.col("issuer_id") == "a").row(1, named=True)
    assert first["report_lag_days"] == 32
    assert first["previous_report_lag_days"] is None
    assert first["missing_previous_report"] == 1
    assert second["previous_report_lag_days"] == 32
    assert second["report_lag_days"] == 60
    assert second["report_lag_change_days"] == 28
    assert second["days_since_previous_annual_filing"] == 394


@pytest.mark.parametrize("invalid", ["schema", "reversed", "ambiguous", "null"])
def test_invalid_filing_history_fails_explicitly(invalid: str) -> None:
    """Invalid dates or ambiguous same-day reports cannot become model inputs."""
    frame = pl.DataFrame(
        {
            "issuer_id": ["a"],
            "filing_date": [date(2020, 2, 1)],
            "period_end": [date(2019, 12, 31)],
        }
    )
    if invalid == "schema":
        frame = frame.drop("issuer_id")
    elif invalid == "reversed":
        frame = frame.with_columns(pl.lit(date(2021, 1, 1)).alias("period_end"))
    elif invalid == "ambiguous":
        frame = pl.concat(
            [
                frame,
                frame.with_columns(pl.lit(date(2018, 12, 31)).alias("period_end")),
            ]
        )
    else:
        frame = frame.with_columns(pl.lit(None, dtype=pl.Date).alias("period_end"))
    with pytest.raises(ValueError):
        disclosure_timing_frame(frame)


def _submissions() -> dict[str, object]:
    return {
        "cik": 1750,
        "filings": {
            "recent": {
                "form": ["10-K", "10-K/A", "8-K", "10-K"],
                "filingDate": ["2002-02-01", "2002-03-01", "2002-04-01", "2003-03-01"],
                "reportDate": ["2001-12-31", "2001-12-31", "", "2002-12-31"],
            },
            "files": [{"name": "CIK0000001750-submissions-001.json"}],
        },
    }


def test_sec_metadata_reproduces_training_features_with_complete_pagination() -> None:
    """Annual forms, dated history and issuer identity match training conventions."""
    history = {
        "CIK0000001750-submissions-001.json": {
            "form": ["10-K405"],
            "filingDate": ["2001-02-01"],
            "reportDate": ["2000-12-31"],
        }
    }
    result = sec_disclosure_timing(
        _submissions(), "0000001750", date(2002, 12, 31), history
    )
    expected = disclosure_timing_frame(
        pl.DataFrame(
            {
                "issuer_id": ["0000001750"] * 2,
                "filing_date": [date(2001, 2, 1), date(2002, 2, 1)],
                "period_end": [date(2000, 12, 31), date(2001, 12, 31)],
            }
        )
    )
    assert result.equals(expected)


@pytest.mark.parametrize("failure", ["identity", "pagination", "arrays", "date"])
def test_sec_metadata_cannot_silently_become_a_zero_score(failure: str) -> None:
    """Mismatch, missing pages, damaged arrays and dates reject model inputs."""
    payload = _submissions()
    issuer = "0000001750"
    history: dict[str, object] = {
        "CIK0000001750-submissions-001.json": {
            "form": ["10-K"],
            "filingDate": ["2001-02-01"],
            "reportDate": ["2000-12-31"],
        }
    }
    if failure == "identity":
        issuer = "0000001751"
    elif failure == "pagination":
        history = {}
    elif failure == "arrays":
        history["CIK0000001750-submissions-001.json"] = {"form": []}
    else:
        history["CIK0000001750-submissions-001.json"] = {
            "form": ["10-K"],
            "filingDate": ["2001-02-01"],
            "reportDate": ["invalid"],
        }
    with pytest.raises((ValueError, pl.exceptions.PolarsError)):
        sec_disclosure_timing(payload, issuer, date(2002, 12, 31), history)


def test_empty_sec_annual_history_remains_empty() -> None:
    """A valid issuer without annual reports does not receive fabricated features."""
    payload = {
        "cik": 1750,
        "filings": {
            "recent": {"form": [], "filingDate": [], "reportDate": []},
            "files": [],
        },
    }
    assert sec_disclosure_timing(payload, "0000001750", date(2002, 1, 1)).is_empty()
