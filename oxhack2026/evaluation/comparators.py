"""Exact tie-averaged shortlist comparators on identical candidate universes."""

from collections.abc import Mapping
from heapq import nlargest
from math import fsum, isfinite


def selection_weights(scores: Mapping[str, float], limit: int = 5) -> dict[str, float]:
    """Compute exact inclusion probabilities with uniform ties at the boundary.

    Args:
        scores: One score per eligible organization; larger scores rank first.
        limit: Research shortlist size from zero to five, bounded by availability.
    Returns:
        Nonzero inclusion weights summing to min(limit, candidate count). All-tied
        persistence and uniform random selection give each candidate k/n weight.
    Raises:
        ValueError: If the limit is invalid or any comparator score is nonfinite.
    """
    if not 0 <= limit <= 5 or any(not isfinite(value) for value in scores.values()):
        message = "Comparators require finite scores and a shortlist size from 0 to 5"
        raise ValueError(message)
    size = min(limit, len(scores))
    if size == 0:
        return {}
    threshold = nlargest(size, scores.values())[-1]
    above = sum(value > threshold for value in scores.values())
    tied = sum(value == threshold for value in scores.values())
    tie_weight = (size - above) / tied
    return {
        organization: 1.0 if value > threshold else tie_weight
        for organization, value in scores.items()
        if value >= threshold
    }


def expected_shortlist_growth(
    scores: Mapping[str, float],
    realized_log_growth: Mapping[str, float],
    limit: int = 5,
) -> float | None:
    """Evaluate a comparator's expected mean growth without random sampling noise.

    Args:
        scores: Comparator scores on the frozen eligible organization universe.
        realized_log_growth: Mature realized log growth on exactly the same keys.
        limit: Desired shortlist size from zero through five.
    Returns:
        Exact tie-averaged mean growth, or None for an empty selection.
    Raises:
        ValueError: If universes differ, values are nonfinite, or limit is invalid.
    """
    if scores.keys() != realized_log_growth.keys() or any(
        not isfinite(value) for value in realized_log_growth.values()
    ):
        message = (
            "Every comparator must use identical candidates and finite mature truth"
        )
        raise ValueError(message)
    weights = selection_weights(scores, limit)
    if not weights:
        return None
    return fsum(
        weight * realized_log_growth[organization]
        for organization, weight in weights.items()
    ) / min(limit, len(scores))
