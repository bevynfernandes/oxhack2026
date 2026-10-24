"""The API delegates numerical rules to the merged Dev 2 implementation."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import orjson
import pytest

from oxhack2026.api.numerical_policy import (
    RankingPresentation,
    ScoringContext,
    map_rankings,
    score_selection,
)
from oxhack2026.api.repository import ImmatureOutcome
from oxhack2026.api.schemas import RevealRequest
from oxhack2026.evaluation.shortlists import score_shortlist
from oxhack2026.models.contracts import ForecastResult, MatureOutcome


@pytest.fixture
def row() -> ForecastResult:
    """Return the shared synthetic ready forecast."""
    return ForecastResult.model_validate(
        orjson.loads(Path("tests/fixtures/models/ready.json").read_bytes())
    )


@pytest.fixture
def outcome() -> MatureOutcome:
    """Return the separately stored shared synthetic mature outcome."""
    return MatureOutcome.model_validate(
        orjson.loads(Path("tests/fixtures/models/mature-outcome.json").read_bytes())
    )


@pytest.fixture
def context() -> ScoringContext:
    """Return a frozen universe and request time after outcome publication."""
    return ScoringContext(
        {"synthetic-org": "synthetic-tool"},
        "synthetic-universe",
        datetime(2025, 2, 10, tzinfo=UTC),
    )


def test_policy_delegation(
    row: ForecastResult, outcome: MatureOutcome, context: ScoringContext
) -> None:
    """Retain shared-policy outputs and limitations without copying their formulas."""
    selection = RevealRequest(organization_ids=("synthetic-org",))
    with patch(
        "oxhack2026.api.numerical_policy.score_shortlist", wraps=score_shortlist
    ) as delegate:
        scores = score_selection((row,), (outcome,), selection, context)
    delegate.assert_called_once_with(
        (row,),
        (outcome,),
        selection.organization_ids,
        context.representatives,
        context.candidate_universe_id,
    )
    assert scores[0].value is not None
    assert scores[0].headline_eligible is False
    assert scores[0].complete_outcomes is True
    assert scores[1].value is None
    assert scores[0].reason is not None
    assert "fewer_than_ten_organizations" in scores[0].reason
    assert all(score.organization_ids == selection.organization_ids for score in scores)


def test_future_availability_is_409_before_scoring(
    row: ForecastResult, outcome: MatureOutcome
) -> None:
    """An otherwise mature label is unavailable before its publication time."""
    context = ScoringContext(
        {"synthetic-org": "synthetic-tool"},
        "synthetic-universe",
        datetime(2025, 2, 6, tzinfo=UTC),
    )
    with (
        patch("oxhack2026.api.numerical_policy.score_shortlist") as delegate,
        pytest.raises(ImmatureOutcome),
    ):
        score_selection((row,), (outcome,), RevealRequest(organization_ids=()), context)
    delegate.assert_not_called()


def test_incomplete_universe_is_409(
    row: ForecastResult, context: ScoringContext
) -> None:
    """Missing outcomes cannot become partial-universe or zero-valued scores."""
    with pytest.raises(ImmatureOutcome):
        score_selection(
            (row,), (), RevealRequest(organization_ids=("synthetic-org",)), context
        )


def test_shared_ranking_and_nonrepresentatives(
    row: ForecastResult, context: ScoringContext
) -> None:
    """Only the frozen organization representative enters the published ordering."""
    presentation = RankingPresentation((), "synthetic-policy-v1", False)
    ranked = map_rankings(row.batch_id, (row,), context.representatives, presentation)
    assert ranked.primary.tool_ids == ("synthetic-tool",)
    assert ranked.shortfall_reason is not None
    excluded = map_rankings(
        row.batch_id, (row,), {"synthetic-org": "another-tool"}, presentation
    )
    assert excluded.primary.tool_ids == ()
    assert excluded.exclusions[0].reasons == ("not_organization_representative",)
    with pytest.raises(ValueError, match="requested batch"):
        map_rankings("another-batch", (row,), context.representatives, presentation)


def test_per_tool_diagnostics_use_shared_policy(
    row: ForecastResult, outcome: MatureOutcome, context: ScoringContext
) -> None:
    """Reveal diagnostics use Dev 2 values, including missing/immature safeguards."""
    from oxhack2026.api.numerical_policy import map_outcomes

    result = map_outcomes((row,), (outcome,), context.as_of)[0]
    assert result.actual_downloads == 3900
    assert result.realized_growth_pct == pytest.approx(30)
    assert result.model_absolute_error == 300
    assert result.baseline_absolute_error == 900
    assert map_outcomes((row,), (), context.as_of)[0].actual_downloads is None
    with pytest.raises(ImmatureOutcome):
        map_outcomes((row,), (outcome,), datetime(2025, 2, 6, tzinfo=UTC))
    with pytest.raises(ValueError, match="one vintage"):
        map_outcomes((row,), (outcome, outcome), context.as_of)


def test_reveal_composition_freezes_vintage_and_original_forecast(
    row: ForecastResult, outcome: MatureOutcome, context: ScoringContext
) -> None:
    """Assemble full truth/metrics without altering the original saved prediction."""
    from oxhack2026.api.numerical_policy import ReplayPresentation, map_reveal

    before = row.model_dump_json()
    selection = RevealRequest(organization_ids=("synthetic-org",))
    presentation = ReplayPresentation(
        context, outcome.outcome_vintage, (), ("Synthetic fixture.",)
    )
    result = map_reveal((row,), (outcome,), selection, presentation)
    assert result.selected_organization_ids == selection.organization_ids
    assert result.outcomes[0].model_absolute_error == 300
    assert len(result.selection_metrics) == 3
    assert row.model_dump_json() == before
    with pytest.raises(ValueError, match="published vintage"):
        map_reveal(
            (row,),
            (outcome,),
            selection,
            ReplayPresentation(context, "another-vintage", (), ()),
        )
    with pytest.raises(ImmatureOutcome):
        map_reveal((), (), selection, presentation)
