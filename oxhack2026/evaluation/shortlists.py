"""Pure ranking and replay policy; API consumers never need training imports."""

from collections.abc import Mapping, Sequence
from heapq import nlargest
from math import fsum, log1p

from oxhack2026.evaluation.contracts import RankedCandidate, ShortlistScore
from oxhack2026.features.definitions import (
    MIN_HEADLINE_ORGANIZATIONS,
    SHORTLIST_SIZE,
)
from oxhack2026.models.contracts import ForecastResult, MatureOutcome


def _eligible_rows(
    rows: Sequence[ForecastResult], representatives: Mapping[str, str]
) -> dict[str, ForecastResult]:
    if not rows:
        return {}
    first = rows[0]
    seen_tools: set[str] = set()
    seen_forecasts: set[str] = set()
    eligible: dict[str, ForecastResult] = {}
    for row in rows:
        if (
            row.batch_id != first.batch_id
            or row.windows != first.windows
            or row.identity.ecosystem != first.identity.ecosystem
            or row.identity.dataset_version != first.identity.dataset_version
            or row.identity.mapping_version != first.identity.mapping_version
        ):
            message = "Rankings require one batch, target, ecosystem and frozen dataset"
            raise ValueError(message)
        if row.identity.tool_id in seen_tools or row.forecast_id in seen_forecasts:
            message = "Duplicate tool or forecast ID in the candidate universe"
            raise ValueError(message)
        seen_tools.add(row.identity.tool_id)
        seen_forecasts.add(row.forecast_id)
        organization = row.identity.organization_id
        if row.ranking_eligible and organization not in representatives:
            message = (
                "Missing frozen representative mapping for an eligible organization"
            )
            raise ValueError(message)
        if (
            row.ranking_eligible
            and representatives[organization] == row.identity.tool_id
        ):
            eligible[organization] = row
    return eligible


def rank_forecasts(
    rows: Sequence[ForecastResult], representatives: Mapping[str, str]
) -> tuple[RankedCandidate, ...]:
    """Order frozen organization representatives by growth, then tool ID for display.

    Args:
        rows: One immutable batch, including unavailable/excluded rows if desired.
        representatives: Frozen mapping of organization ID to representative tool ID.
    Returns:
        Eligible display ranks. Equal scores remain equal predictions; scientific
        comparisons must average tied selections rather than score tool-ID order.
    Raises:
        ValueError: On duplicate identities, mixed scopes, or missing mappings.
    """
    ordered = sorted(
        _eligible_rows(rows, representatives).values(),
        key=lambda row: (-(row.predicted_growth_pct or 0.0), row.identity.tool_id),
    )
    result: list[RankedCandidate] = []
    for index, row in enumerate(ordered, start=1):
        growth = row.predicted_growth_pct
        if growth is None:
            message = "Eligible forecasts require percentage growth"
            raise ValueError(message)
        result.append(
            RankedCandidate(
                forecast_id=row.forecast_id,
                tool_id=row.identity.tool_id,
                organization_id=row.identity.organization_id,
                rank=index,
                predicted_growth_pct=growth,
            )
        )
    return tuple(result)


def _outcome_growth(
    eligible: Mapping[str, ForecastResult], outcomes: Sequence[MatureOutcome]
) -> tuple[dict[str, float], set[str]]:
    indexed: dict[str, MatureOutcome] = {}
    for outcome in outcomes:
        if outcome.forecast_id in indexed:
            message = "Select exactly one outcome vintage per forecast"
            raise ValueError(message)
        indexed[outcome.forecast_id] = outcome
    growth: dict[str, float] = {}
    positives: set[str] = set()
    for organization, forecast in eligible.items():
        record = indexed.get(forecast.forecast_id)
        if record is None:
            continue
        if (
            record.label.windows != forecast.windows
            or record.label.feature_row_id != forecast.feature_row_id
        ):
            message = (
                "Outcome does not match its frozen forecast windows and feature row"
            )
            raise ValueError(message)
        actual, reference = record.label.actual_downloads, forecast.reference_downloads
        if actual is None or reference is None:
            message = "Eligible mature records require actual and reference counts"
            raise ValueError(message)
        growth[organization] = log1p(actual) - log1p(reference)
        if 2 * actual >= 3 * reference:
            positives.add(organization)
    return growth, positives


def score_shortlist(
    rows: Sequence[ForecastResult],
    outcomes: Sequence[MatureOutcome],
    organization_ids: Sequence[str],
    representatives: Mapping[str, str],
    candidate_universe_id: str,
) -> ShortlistScore:
    """Score up to five selected organizations on one common candidate universe.

    Args:
        rows: All candidates in the frozen forecast batch.
        outcomes: One available mature vintage per forecast; omissions stay missing.
        organization_ids: Distinct eligible organizations chosen by the user.
        representatives: Frozen organization-to-tool mapping from the batch catalogue.
        candidate_universe_id: Persisted identifier for the exact compared universe.
    Returns:
        Scores, or null metrics if any candidate outcome is unavailable. Partial
        selections get descriptive mean growth but no headline/top-5 metrics.
    Raises:
        ValueError: For invalid selections, mixed scopes, or mismatched outcomes.
    """
    selected = tuple(organization_ids)
    if len(selected) > SHORTLIST_SIZE or len(set(selected)) != len(selected):
        message = "Select at most five distinct organizations"
        raise ValueError(message)
    if not candidate_universe_id:
        message = "A persisted candidate-universe identifier is required"
        raise ValueError(message)
    eligible = _eligible_rows(rows, representatives)
    if any(organization not in eligible for organization in selected):
        message = "Selection contains an unknown or ineligible organization"
        raise ValueError(message)
    growth, positives = _outcome_growth(eligible, outcomes)
    complete = len(growth) == len(eligible)
    full = len(selected) == SHORTLIST_SIZE
    average = (
        fsum(growth[org] for org in selected) / len(selected)
        if selected and complete
        else None
    )
    hits = len(set(selected) & positives)
    oracle = (
        fsum(nlargest(SHORTLIST_SIZE, growth.values())) / SHORTLIST_SIZE
        if full and complete
        else None
    )
    reasons: list[str] = []
    if not complete:
        reasons.append("immature_outcome")
    if not full:
        reasons.append("shortlist_under_five")
    if len(eligible) < MIN_HEADLINE_ORGANIZATIONS:
        reasons.append("fewer_than_ten_organizations")
    return ShortlistScore(
        forecast_ids=tuple(eligible[org].forecast_id for org in selected),
        candidate_universe_id=candidate_universe_id,
        selection_count=len(selected),
        eligible_organization_count=len(eligible),
        headline_eligible=full
        and complete
        and len(eligible) >= MIN_HEADLINE_ORGANIZATIONS,
        complete_outcomes=complete,
        mean_realized_log_growth=average,
        precision_at_5=hits / SHORTLIST_SIZE if full and complete else None,
        recall_at_5=hits / len(positives) if full and complete and positives else None,
        regret=max(0.0, oracle - average)
        if oracle is not None and average is not None
        else None,
        reason_codes=tuple(reasons),
    )
