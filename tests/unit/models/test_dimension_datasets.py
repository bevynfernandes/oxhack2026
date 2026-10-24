"""Raw-source adapters use mocked captures and preserve unknown observations."""

from datetime import date
from math import asinh
from pathlib import Path
from unittest.mock import patch

import orjson
import polars as pl
import pytest

from oxhack2026.models.dimension_datasets import (
    _release_dates,
    build_financial_dataset,
    build_sdk_datasets,
)


def test_sdk_targets_use_future_counts_without_changing_origin_features() -> None:
    """A changed future observation affects labels, never predictor windows."""
    cohort = orjson.dumps(
        {
            "subjects": [
                {"subject_id": name, "package": name, "segment": "data"}
                for name in ("alpha", "beta", "gamma")
            ]
        }
    )
    histories: dict[str, tuple[int, ...]] = dict.fromkeys(
        ("alpha", "beta", "gamma"), (100,) * 1461
    )
    with (
        patch.object(Path, "read_bytes", return_value=cohort),
        patch(
            "oxhack2026.models.dimension_datasets._download_history",
            side_effect=lambda directory, package: histories[package],
        ),
        patch(
            "oxhack2026.models.dimension_datasets._release_dates",
            return_value=(date(2022, 3, 1), date(2022, 4, 1)),
        ),
    ):
        first, audit = build_sdk_datasets(Path("mock"), Path("cohort.json"))
        changed = list(histories["alpha"])
        changed[(date(2022, 4, 1) - date(2022, 1, 1)).days] += 10000
        histories["alpha"] = tuple(changed)
        second, _ = build_sdk_datasets(Path("mock"), Path("cohort.json"))

    assert audit["declared_subjects"] == 3
    for dimension in ("adoption_retention", "industry_competition"):
        before = next(
            row
            for row in first[dimension]
            if row.subject_id == "alpha" and row.origin == date(2022, 3, 31)
        )
        after = next(
            row
            for row in second[dimension]
            if row.subject_id == "alpha" and row.origin == date(2022, 3, 31)
        )
        assert before.values == after.values
        assert before.target != after.target
    assert first["team_execution"]


def test_stable_release_filter_requires_complete_pagination() -> None:
    """Drafts, prereleases, duplicates and metadata files cannot inflate cadence."""
    release = {
        "id": 1,
        "draft": False,
        "prerelease": False,
        "published_at": "2023-01-01T00:00:00Z",
    }
    files = [Path("releases-1.json"), Path("releases-1.json.capture.json")]
    with (
        patch.object(Path, "glob", return_value=iter(files)),
        patch.object(
            Path,
            "read_bytes",
            return_value=orjson.dumps(
                [
                    release,
                    release,
                    release | {"id": 2, "prerelease": True},
                    release | {"id": 3, "draft": True},
                ]
            ),
        ),
    ):
        dates = _release_dates(Path("mock"))
    assert dates == (date(2023, 1, 1),)

    with (
        patch.object(Path, "glob", return_value=iter(files)),
        patch.object(Path, "read_bytes", return_value=orjson.dumps([release] * 100)),
    ):
        assert _release_dates(Path("mock")) is None


def test_financial_rows_match_same_issuer_next_annual_period() -> None:
    """Financial predictors and target use separate years of reported USD values."""
    issuer = pl.DataFrame({"cik": ["0001"], "sic": ["7372"]}).lazy()
    data = pl.DataFrame(
        [
            {
                "cik": "0001",
                "fiscal_period": "FY",
                "unit": "USD",
                "quality": "reported",
                "metric": metric,
                "value": str(value),
                "start_date": f"{year}-01-01",
                "end_date": f"{year}-12-31",
            }
            for year, cashflow in ((2020, 100000), (2021, 200000))
            for metric, value in (("revenue", 1000000), ("ocf", cashflow))
        ]
    ).lazy()

    with patch(
        "oxhack2026.models.dimension_datasets.pl.scan_csv", side_effect=[issuer, data]
    ):
        rows, audit = build_financial_dataset(Path("mock"))

    assert len(rows) == 1
    assert rows[0].origin == date(2020, 12, 31)
    assert rows[0].target_end == date(2021, 12, 31)
    assert rows[0].values[1] == pytest.approx(asinh(0.1))
    assert rows[0].target == pytest.approx(asinh(0.2))
    assert "unknown" in str(audit["availability"])
