"""Presentation adapters calling Dev 2's authoritative lightweight policy."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from oxhack2026.api import schemas as s
from oxhack2026.api.repository import ImmatureOutcome
from oxhack2026.evaluation.metrics import outcome_diagnostics
from oxhack2026.evaluation.shortlists import rank_forecasts, score_shortlist
from oxhack2026.features.definitions import SHORTLIST_SIZE
from oxhack2026.models.contracts import ForecastResult, MatureOutcome, TimeWindow


@dataclass(frozen=True)
class RankingPresentation:
    """Published comparators, policy version and current outcome availability.

    Attributes:
        baselines: Model-owner comparator orderings; no local baseline sorting.
        policy_version: Version bound to the published ranking configuration.
        reveal_allowed: True only after complete outcome publication checks pass.
    """

    baselines: tuple[s.Ranking, ...]
    policy_version: str
    reveal_allowed: bool


@dataclass(frozen=True)
class ScoringContext:
    """Frozen candidate scope and request-time availability bound.

    Attributes:
        representatives: Frozen organization-to-tool mapping from the catalogue.
        candidate_universe_id: Published ID of the exact comparison universe.
        as_of: Timezone-aware UTC request time; do not supply a future time.
    """

    representatives: Mapping[str, str]
    candidate_universe_id: str
    as_of: datetime


def map_rankings(
    batch_id: str,
    rows: Sequence[ForecastResult],
    representatives: Mapping[str, str],
    presentation: RankingPresentation,
) -> s.Rankings:
    """Present the shared policy's ordering and exclusions for one batch.

    Args:
        batch_id: Exact immutable batch being served.
        rows: C2 forecast results, including unavailable/nonrepresentative rows.
        representatives: Catalogue mapping frozen with this batch.
        presentation: Published comparator and reveal metadata.
    Returns:
        C3 rankings using Dev 2's order and shortlist-size constant.
    Raises:
        ValueError: Rows mix batches, scopes, duplicate IDs or invalid mappings.
    """
    if any(row.batch_id != batch_id for row in rows):
        message = "Ranking rows do not match the requested batch"
        raise ValueError(message)
    ordered = rank_forecasts(rows, representatives)
    ranked_ids = tuple(candidate.tool_id for candidate in ordered)
    ranked_set = set(ranked_ids)
    return s.Rankings(
        batch_id=batch_id,
        policy_version=presentation.policy_version,
        primary=s.Ranking(name="Predicted percentage growth", tool_ids=ranked_ids),
        recommended_tool_ids=ranked_ids[:SHORTLIST_SIZE],
        baselines=presentation.baselines,
        exclusions=tuple(
            s.Exclusion(
                tool_id=row.identity.tool_id,
                reasons=row.reason_codes or ("not_organization_representative",),
            )
            for row in rows
            if row.identity.tool_id not in ranked_set
        ),
        shortfall_reason=(
            "Fewer eligible organization representatives than shortlist slots."
            if len(ranked_ids) < SHORTLIST_SIZE
            else None
        ),
        reveal_allowed=presentation.reveal_allowed,
    )


def score_selection(
    rows: Sequence[ForecastResult],
    outcomes: Sequence[MatureOutcome],
    selection: s.RevealRequest,
    context: ScoringContext,
) -> tuple[s.Score, ...]:
    """Delegate shortlist metrics after enforcing request-time outcome availability.

    Args:
        rows: The complete frozen C2 candidate batch.
        outcomes: One selected published outcome vintage per forecast.
        selection: Distinct organization IDs submitted by the scout.
        context: Frozen representatives, universe ID and actual request time.
    Returns:
        Mean log growth, precision, recall and regret from Dev 2, in that order.
        Undefined metrics stay null; undersized/unvalidated claims retain reasons.
    Raises:
        ImmatureOutcome: Any outcome is future-available or the shared policy
            reports an incomplete candidate universe.
        ValueError: Invalid UTC context, mismatched artifacts or invalid selection.
    """
    TimeWindow.validate_utc(context.as_of)
    if any(
        outcome.label.available_at is None or outcome.label.available_at > context.as_of
        for outcome in outcomes
    ):
        raise ImmatureOutcome
    score = score_shortlist(
        rows,
        outcomes,
        selection.organization_ids,
        context.representatives,
        context.candidate_universe_id,
    )
    if not score.complete_outcomes:
        raise ImmatureOutcome
    return tuple(
        s.Score(
            name="Your selection",
            metric=metric,
            value=value,
            organization_ids=selection.organization_ids,
            reason="; ".join(score.reason_codes) or None,
            candidate_universe_id=score.candidate_universe_id,
            headline_eligible=score.headline_eligible,
            complete_outcomes=score.complete_outcomes,
        )
        for metric, value in (
            ("Mean realized log growth", score.mean_realized_log_growth),
            ("Precision at five", score.precision_at_5),
            ("Recall at five", score.recall_at_5),
            ("Regret", score.regret),
        )
    )


def map_outcomes(
    rows: Sequence[ForecastResult],
    outcomes: Sequence[MatureOutcome],
    as_of: datetime,
) -> tuple[s.Outcome, ...]:
    """Present Dev 2's per-tool diagnostics without copying numerical formulas.

    Args:
        rows: Frozen forecast results for the exact replay batch.
        outcomes: One published outcome vintage per forecast, when available.
        as_of: Actual timezone-aware UTC reveal request time.
    Returns:
        Saved truth and shared-policy diagnostics; absent truth stays null.
    Raises:
        ImmatureOutcome: An outcome is not available at the request time.
        ValueError: Outcome IDs/vintages are ambiguous or do not match forecasts.
    """
    TimeWindow.validate_utc(as_of)
    indexed = {outcome.forecast_id: outcome for outcome in outcomes}
    if len(indexed) != len(outcomes) or not indexed.keys() <= {
        row.forecast_id for row in rows
    }:
        message = "Outcomes require one vintage per known forecast"
        raise ValueError(message)
    results: list[s.Outcome] = []
    for row in rows:
        outcome = indexed.get(row.forecast_id)
        if outcome is None:
            results.append(
                s.Outcome(
                    tool_id=row.identity.tool_id,
                    actual_downloads=None,
                    realized_growth_pct=None,
                    model_absolute_error=None,
                    baseline_absolute_error=None,
                    reasons=("incomplete_outcome",),
                )
            )
            continue
        if outcome.label.available_at is None or outcome.label.available_at > as_of:
            raise ImmatureOutcome
        diagnostics = outcome_diagnostics(row, outcome, as_of)
        results.append(
            s.Outcome(
                tool_id=row.identity.tool_id,
                actual_downloads=diagnostics.actual_downloads,
                realized_growth_pct=diagnostics.realized_growth_pct,
                model_absolute_error=diagnostics.model_absolute_error,
                baseline_absolute_error=diagnostics.baseline_absolute_error,
                reasons=diagnostics.reason_codes,
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class ReplayPresentation:
    """Published outcome vintage and comparator metadata for one replay.

    Attributes:
        scoring: Frozen candidate universe and actual request time.
        outcome_vintage: Exact selected publication version, shared by its outcomes.
        comparators: Saved model-owner comparator scores on the same universe.
        limitations: Published research/coverage limitations, without added claims.
    """

    scoring: ScoringContext
    outcome_vintage: str
    comparators: tuple[s.Score, ...]
    limitations: tuple[str, ...]


def map_reveal(
    rows: Sequence[ForecastResult],
    outcomes: Sequence[MatureOutcome],
    selection: s.RevealRequest,
    presentation: ReplayPresentation,
) -> s.Reveal:
    """Assemble separate reveal truth and delegated scores for one frozen batch.

    Args:
        rows: Complete original forecast batch, never mutated by reveal.
        outcomes: One selected complete publication vintage per available tool.
        selection: Exact organization IDs captured at submission time.
        presentation: Request-time scoring scope, comparator scores and limitations.
    Returns:
        C3 truth, per-tool diagnostics and all shared shortlist metrics.
    Raises:
        ImmatureOutcome: No batch/outcomes or an incomplete/late candidate universe.
        ValueError: Mixed scope/vintage, invalid selections or mismatched comparators.
    """
    if not rows or not outcomes:
        raise ImmatureOutcome
    if any(
        outcome.outcome_vintage != presentation.outcome_vintage for outcome in outcomes
    ):
        message = "Reveal outcomes must use the selected published vintage"
        raise ValueError(message)
    if any(
        score.candidate_universe_id != presentation.scoring.candidate_universe_id
        for score in presentation.comparators
    ):
        message = "Replay comparators must use the exact shared candidate universe"
        raise ValueError(message)
    scores = score_selection(rows, outcomes, selection, presentation.scoring)
    diagnostics = map_outcomes(rows, outcomes, presentation.scoring.as_of)
    available = tuple(
        outcome.label.available_at
        for outcome in outcomes
        if outcome.label.available_at is not None
    )
    return s.Reveal(
        batch_id=rows[0].batch_id,
        outcome_vintage=presentation.outcome_vintage,
        available_at=max(available),
        selected_organization_ids=selection.organization_ids,
        outcomes=diagnostics,
        selection_score=scores[0],
        selection_metrics=scores[1:],
        comparators=presentation.comparators,
        limitations=presentation.limitations,
    )
