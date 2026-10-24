"""Shared temporal and shortlist policy against C2's saved synthetic fixtures."""

from datetime import UTC, datetime, timedelta
from math import log1p
from pathlib import Path

import orjson
import pytest
from pydantic import ValidationError

from oxhack2026.evaluation.shortlists import rank_forecasts, score_shortlist
from oxhack2026.features.definitions import require_decision, target_windows
from oxhack2026.models.contracts import ForecastManifest, ForecastResult, MatureOutcome

FIXTURES = Path(__file__).parents[2] / "fixtures" / "models"


def _universe(
    count: int = 10,
) -> tuple[list[ForecastResult], list[MatureOutcome], dict[str, str]]:
    base = orjson.loads((FIXTURES / "ready.json").read_bytes())
    truth = orjson.loads((FIXTURES / "mature-outcome.json").read_bytes())
    forecasts, outcomes, representatives = [], [], {}
    for index in range(count):
        tool_id, organization = (
            f"synthetic-tool-{index:02d}",
            f"synthetic-org-{index:02d}",
        )
        identifier, feature_id = f"forecast-{index:02d}", f"feature-{index:02d}"
        identity = base["identity"] | {
            "tool_id": tool_id,
            "organization_id": organization,
        }
        forecasts.append(
            ForecastResult.model_validate(
                base
                | {
                    "identity": identity,
                    "forecast_id": identifier,
                    "feature_row_id": feature_id,
                    "reference_downloads": 2000,
                    "predicted_downloads": 3000,
                    "predicted_growth_pct": 50,
                }
            )
        )
        outcomes.append(
            MatureOutcome.model_validate(
                truth
                | {
                    "forecast_id": identifier,
                    "label": truth["label"]
                    | {
                        "feature_row_id": feature_id,
                        "actual_downloads": 2000 + 200 * index,
                    },
                }
            )
        )
        representatives[organization] = tool_id
    return forecasts, outcomes, representatives


def test_worked_windows_and_fixed_lookback() -> None:
    """Check independently specified plan dates for both targets and 84-day history."""
    origin = datetime(2025, 1, 6, tzinfo=UTC)
    short = target_windows(origin, "downloads_next_30d_v1")
    long = target_windows(origin, "downloads_trailing_28d_at_91d_v1")
    assert short.reference_start == datetime(2024, 12, 5, tzinfo=UTC)
    assert short.observation_end == datetime(2025, 1, 4, tzinfo=UTC)
    assert short.target_start == origin
    assert short.target_end == datetime(2025, 2, 5, tzinfo=UTC)
    assert long.reference_start == datetime(2024, 12, 7, tzinfo=UTC)
    assert long.target_start == datetime(2025, 3, 10, tzinfo=UTC)
    assert long.target_end == datetime(2025, 4, 7, tzinfo=UTC)
    assert (short.observation_end - short.history_start).days == 84


@pytest.mark.parametrize(
    "value",
    [
        datetime(2025, 1, 6),
        datetime(2025, 1, 7, tzinfo=UTC),
        datetime(2025, 1, 6, 0, 0, 0, 1, tzinfo=UTC),
    ],
)
def test_invalid_decision(value: datetime) -> None:
    """Reject naive timestamps, wrong weekdays, and subsecond cutoff drift."""
    with pytest.raises(ValueError):
        require_decision(value)


def test_recorded_at_cutoff_is_not_prospective() -> None:
    """Recording at the target start is too late for pre-target publication."""
    payload = orjson.loads((FIXTURES / "forecast-manifest.json").read_bytes())
    payload.update(
        mode="prospective", first_recorded_at=payload["windows"]["decision_at"]
    )
    with pytest.raises(ValidationError, match="Late"):
        ForecastManifest.model_validate(payload)
    payload["first_recorded_at"] = datetime(2025, 1, 6, tzinfo=UTC) - timedelta(
        microseconds=1
    )
    assert ForecastManifest.model_validate(payload).mode == "prospective"


def test_tied_display_and_frozen_representatives() -> None:
    """Display ties sort by ID; a better forecast cannot replace the frozen tool."""
    forecasts, _, representatives = _universe()
    alternative = ForecastResult.model_validate(
        forecasts[0].model_dump()
        | {
            "identity": forecasts[0].identity.model_dump() | {"tool_id": "other-tool"},
            "forecast_id": "other-forecast",
            "predicted_downloads": 20000,
            "predicted_growth_pct": 900,
        }
    )
    ranked = rank_forecasts([alternative, *reversed(forecasts)], representatives)
    assert len(ranked) == 10
    assert [row.tool_id for row in ranked] == sorted(representatives.values())
    assert {row.predicted_growth_pct for row in ranked} == {50}


def test_manual_score_and_small_universe() -> None:
    """Verify hand-calculated metrics, exact breakout boundary, and ten-org gate."""
    forecasts, outcomes, representatives = _universe()
    selected = list(representatives)[5:]
    score = score_shortlist(
        forecasts, outcomes, selected, representatives, "universe-v1"
    )
    assert score.headline_eligible
    assert score.precision_at_5 == score.recall_at_5 == 1
    assert score.regret == 0
    assert score.mean_realized_log_growth == pytest.approx(
        sum(log1p(value) - log1p(2000) for value in [3000, 3200, 3400, 3600, 3800]) / 5
    )
    small = score_shortlist(
        forecasts[:5],
        outcomes[:5],
        list(representatives)[:5],
        representatives,
        "small-v1",
    )
    assert not small.headline_eligible
    assert small.precision_at_5 == 0
    assert small.recall_at_5 is None
    assert "fewer_than_ten_organizations" in small.reason_codes


def test_partial_empty_and_immature_scores() -> None:
    """Undefined and unavailable metrics stay null; never zero-filled actuals."""
    forecasts, outcomes, representatives = _universe()
    partial = score_shortlist(
        forecasts, outcomes, list(representatives)[:1], representatives, "v1"
    )
    assert partial.mean_realized_log_growth == 0
    assert partial.precision_at_5 is None
    assert not partial.headline_eligible
    empty = score_shortlist(forecasts, outcomes, [], representatives, "v1")
    assert empty.mean_realized_log_growth is None
    incomplete = score_shortlist(
        forecasts, outcomes[:-1], list(representatives)[:5], representatives, "v1"
    )
    assert not incomplete.complete_outcomes
    assert incomplete.mean_realized_log_growth is None
    assert incomplete.precision_at_5 is None
    assert not incomplete.headline_eligible
    assert "immature_outcome" in incomplete.reason_codes
    assert rank_forecasts([], {}) == ()


def test_invalid_selections_and_outcomes() -> None:
    """Reject duplicate/unknown/six-way selections and mixed truth vintages."""
    forecasts, outcomes, representatives = _universe()
    organization = next(iter(representatives))
    for selected in (
        [organization, organization],
        ["unknown"],
        list(representatives)[:6],
    ):
        with pytest.raises(ValueError):
            score_shortlist(forecasts, outcomes, selected, representatives, "v1")
    with pytest.raises(ValueError, match="one outcome vintage"):
        score_shortlist(forecasts, [*outcomes, outcomes[0]], [], representatives, "v1")
    mismatched = MatureOutcome.model_validate(
        outcomes[0].model_dump()
        | {
            "label": outcomes[0].label.model_dump()
            | {"feature_row_id": "other-feature"},
        }
    )
    with pytest.raises(ValueError, match="does not match"):
        score_shortlist(
            forecasts, [mismatched, *outcomes[1:]], [], representatives, "v1"
        )


def test_scope_and_identity_validation() -> None:
    """Reject mixed snapshots, duplicate identities, and incomplete frozen mappings."""
    forecasts, _, representatives = _universe()
    with pytest.raises(ValueError, match="Duplicate"):
        rank_forecasts([forecasts[0], forecasts[0]], representatives)
    with pytest.raises(ValueError, match="Missing frozen"):
        rank_forecasts(forecasts, {})
    other = ForecastResult.model_validate(
        forecasts[1].model_dump() | {"batch_id": "other"}
    )
    with pytest.raises(ValueError, match="one batch"):
        rank_forecasts([forecasts[0], other], representatives)
    revised = ForecastResult.model_validate(
        forecasts[1].model_dump()
        | {
            "identity": forecasts[1].identity.model_dump()
            | {"dataset_version": "revised"},
        }
    )
    with pytest.raises(ValueError, match="frozen dataset"):
        rank_forecasts([forecasts[0], revised], representatives)


def test_low_reference_exclusion_and_threshold() -> None:
    """Exactly 1,000 may rank; the saved 999-download fixture cannot."""
    low = ForecastResult.model_validate_json(
        (FIXTURES / "low-reference-count.json").read_bytes()
    )
    representatives = {low.identity.organization_id: low.identity.tool_id}
    assert rank_forecasts([low], representatives) == ()
    at_threshold = ForecastResult.model_validate(
        low.model_dump()
        | {
            "reference_downloads": 1000,
            "predicted_downloads": 1100,
            "predicted_growth_pct": 10,
            "ranking_eligible": True,
            "reason_codes": [],
        }
    )
    assert len(rank_forecasts([at_threshold], representatives)) == 1
