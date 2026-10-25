"""Financial model selection respects issuer independence and label maturity."""

import io
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from oxhack2026.features.sec_financial_panel import FINANCIAL_FEATURES
from oxhack2026.models.financial_components import train_financial_component


def _panel() -> pl.DataFrame:
    rows = []
    for partition, year in (("train", 2012), ("validation", 2018), ("test", 2023)):
        for number in range(40):
            target = int(number < 20)
            rows.append(
                {
                    "issuer_id": f"{partition}-{number}",
                    "partition": partition,
                    "filing_date": date(year, 3, 1),
                    "label_available_at": date(year + 2, 3, 1),
                    "component": "revenue_growth_2fy",
                    "target": target,
                    **{feature: float(target) for feature in FINANCIAL_FEATURES},
                }
            )
    return pl.DataFrame(rows)


def test_real_candidate_fits_preserve_research_only_status() -> None:
    """Four actual estimators learn a strong toy signal without real filesystem IO."""
    output = MagicMock(spec=Path)
    output.__truediv__.return_value.open.side_effect = lambda *_args: io.BytesIO(
        b"model"
    )
    with (
        patch.object(pl.DataFrame, "write_parquet"),
        patch("oxhack2026.models.financial_components.joblib.dump") as save,
    ):
        result = train_financial_component(_panel(), output, {"plan_sha256": "0" * 64})
    assert save.call_count == 4
    assert result["selected_model"] != "training_prevalence"
    assert result["statistical_gate_passed"] is True
    assert result["eligible_for_serving"] is False


@pytest.mark.parametrize(
    "invalid", ["overlap", "maturity", "one_class", "few", "target"]
)
def test_invalid_experiments_fail_before_writing_or_fitting(invalid: str) -> None:
    """Leaking identities, immature labels and inadequate targets fail explicitly."""
    panel = _panel()
    if invalid == "overlap":
        panel = panel.with_columns(
            pl.col("issuer_id").str.replace("validation-", "train-")
        )
    elif invalid == "maturity":
        panel = panel.with_columns(
            pl.when(pl.col("partition") == "train")
            .then(pl.lit(date(2020, 1, 1)))
            .otherwise(pl.col("label_available_at"))
            .alias("label_available_at")
        )
    elif invalid == "one_class":
        panel = panel.with_columns(pl.lit(1).alias("target"))
    elif invalid == "few":
        panel = panel.filter(pl.col("issuer_id").str.ends_with("0"))
    else:
        panel = panel.with_columns(
            pl.when(pl.col("partition") == "test")
            .then(pl.lit("other"))
            .otherwise(pl.col("component"))
            .alias("component")
        )
    output = MagicMock(spec=Path)
    with pytest.raises(ValueError):
        train_financial_component(panel, output, {})
    output.mkdir.assert_not_called()
