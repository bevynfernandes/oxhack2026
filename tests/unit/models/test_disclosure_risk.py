"""Business-event labels, causal metadata and research-only model fitting."""

import io
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from oxhack2026.models.disclosure_risk import (
    disclosure_bankruptcy_panel,
    train_disclosure_risk,
)


def test_panel_uses_filing_date_and_retains_earlier_unqualified_history() -> None:
    """A prior report is usable history even when not an eligible training origin."""
    source = pl.DataFrame(
        {
            "cik": ["1750.0"] * 3,
            "filing_date": ["2001-02-01", "2002-02-01", "2004-02-01"],
            "period_of_report": ["2000-12-31", "2001-12-31", "2003-12-31"],
            "qualified": ["No", "Yes", "Yes"],
            "can_label": ["True"] * 3,
            "label": ["False", "True", "False"],
            "bankruptcy_date_1": ["2003-01-01"] * 3,
            "bankruptcy_date_2": [None] * 3,
            "bankruptcy_date_3": [None] * 3,
        },
        schema_overrides={
            "bankruptcy_date_2": pl.String,
            "bankruptcy_date_3": pl.String,
        },
    )
    panel = disclosure_bankruptcy_panel(source)
    assert panel.height == 1
    row = panel.row(0, named=True)
    assert row["issuer_id"] == "0000001750"
    assert row["target"] == 1
    assert row["label_end"] == date(2003, 2, 1)
    assert row["days_since_previous_annual_filing"] == 365
    assert row["missing_previous_report"] == 0


def _synthetic_panel() -> pl.DataFrame:
    rows = []
    for partition, year in (("train", 2005), ("validation", 2010), ("test", 2016)):
        for number in range(40):
            target = int(number < 20)
            lag = 250 + number if target else 20 + number
            rows.append(
                {
                    "issuer_id": f"{partition}-{number}",
                    "partition": partition,
                    "filing_date": date(year, 3, 1),
                    "label_end": date(year + 1, 3, 1),
                    "target": target,
                    "report_lag_days": lag,
                    "previous_report_lag_days": lag - 5,
                    "days_since_previous_annual_filing": 370,
                    "report_lag_change_days": 5,
                    "missing_previous_report": 0,
                }
            )
    return pl.DataFrame(rows)


def test_candidates_fit_without_converting_research_into_serving_authority() -> None:
    """Real estimators learn a synthetic signal while filesystem writes are mocked."""
    panel = _synthetic_panel()
    output = MagicMock(spec=Path)
    output.__truediv__.return_value.open.side_effect = lambda *_args: io.BytesIO(
        b"model"
    )
    with (
        patch.object(pl.DataFrame, "write_parquet"),
        patch("oxhack2026.models.disclosure_risk.joblib.dump") as save,
    ):
        result = train_disclosure_risk(panel, output, "0" * 64)
    assert result["eligible_for_serving"] is False
    assert result["status"] == "research_models_trained"
    assert result["selected_model"] != "training_prevalence"
    assert save.call_count == 4


def test_good_test_metrics_cannot_override_worse_validation_calibration() -> None:
    """The prespecified gate requires improvement on validation and test losses."""
    output = MagicMock(spec=Path)
    output.__truediv__.return_value.open.side_effect = lambda *_args: io.BytesIO(
        b"model"
    )
    baseline = {
        "roc_auc": 0.5,
        "average_precision": 0.5,
        "brier": 0.25,
        "log_loss": 0.7,
    }
    candidate = {**baseline, "brier": 0.26, "log_loss": 0.6}
    good_test = {**baseline, "brier": 0.1, "log_loss": 0.2}
    with (
        patch.object(pl.DataFrame, "write_parquet"),
        patch("oxhack2026.models.disclosure_risk.joblib.dump"),
        patch(
            "oxhack2026.models.disclosure_risk._metrics",
            side_effect=[baseline, *[candidate] * 4, baseline, good_test],
        ),
        patch(
            "oxhack2026.models.disclosure_risk._precision_interval",
            return_value=(0.01, 0.2),
        ),
    ):
        result = train_disclosure_risk(_synthetic_panel(), output, "0" * 64)
    assert result["statistical_gate_passed"] is False


@pytest.mark.parametrize("failure", ["overlap", "immature", "few_events"])
def test_invalid_evaluation_cannot_fit_models(failure: str) -> None:
    """Issuer overlap, immature outcomes and too few events fail before fitting."""
    panel = _synthetic_panel()
    if failure == "overlap":
        panel = panel.with_columns(
            pl.col("issuer_id").str.replace("validation", "train")
        )
    elif failure == "immature":
        panel = panel.with_columns(
            pl.when(pl.col("partition") == "train")
            .then(pl.lit(date(2015, 1, 1)))
            .otherwise(pl.col("label_end"))
            .alias("label_end")
        )
    else:
        panel = panel.with_columns(pl.lit(0).alias("target"))
    with (
        patch("oxhack2026.models.disclosure_risk.Pipeline.fit") as fit,
        pytest.raises(ValueError),
    ):
        train_disclosure_risk(panel, Path("mock-unused"), "0" * 64)
    fit.assert_not_called()
