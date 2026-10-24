"""Explicit outcome-specific label eligibility and family exclusions at fit time."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from oxhack2026.features.company_outcomes import COMPANY_OUTCOME_IDS, CompanyOutcomeId
from oxhack2026.features.definitions import require_utc
from oxhack2026.models.company_contracts import CompanyOutcomeLabel

LabelExclusion = Literal[
    "held_out_family",
    "horizon_not_elapsed_at_fit",
    "immature_source_vintage",
    "unobserved",
    "conflicting",
    "label_not_available_at_fit",
]


@dataclass(frozen=True)
class CompanyLabelSelection:
    """Chronological training labels and exhaustive, nonoverlapping exclusion counts.

    Attributes:
        outcome_id: Exactly one endpoint; other input outcomes are outside this scope.
        fit_at: UTC knowledge cutoff for this training selection.
        labels: Observed mature labels available by fit_at, excluding held-out families.
        excluded_counts: Immutable reason/count pairs for all other scoped rows.
    """

    outcome_id: CompanyOutcomeId
    fit_at: datetime
    labels: tuple[CompanyOutcomeLabel, ...]
    excluded_counts: tuple[tuple[LabelExclusion, int], ...]


def select_company_labels(
    labels: Sequence[CompanyOutcomeLabel],
    outcome_id: CompanyOutcomeId,
    fit_at: datetime,
    held_out_families: frozenset[str] = frozenset(),
) -> CompanyLabelSelection:
    """Select one endpoint without turning missing follow-up into training negatives.

    Args:
        labels: Source-adjudicated records from explicitly selected immutable
            vintages. Upstream validates source evidence, identity and collection
            policy; this function cannot establish those historical facts.
        outcome_id: Endpoint to select independently from other company outcomes.
        fit_at: UTC training cutoff; future horizon completion/support is excluded.
        held_out_families: Families reserved for held-out-company evaluation.
    Returns:
        Deterministically ordered eligible labels and one exclusion per other row
        of this outcome. Family exclusions take precedence, then horizon maturity,
        selected-vintage state and availability. Old immature source vintages stay
        immature even after the calendar advances. No newer truth is substituted.
    Raises:
        ValueError: Cutoff/outcome is invalid or the same company/origin has multiple
            selected records. Callers must resolve vintages rather than pick one
            according to its outcome or whichever happened to arrive last.
    """
    require_utc(fit_at)
    if outcome_id not in COMPANY_OUTCOME_IDS:
        message = "Unsupported company outcome for label selection"
        raise ValueError(message)
    scoped = [label for label in labels if label.outcome_id == outcome_id]
    keys = {(label.company_id, label.decision_at) for label in scoped}
    if len(keys) != len(scoped):
        message = "Select one explicit label vintage per company/outcome/origin"
        raise ValueError(message)
    eligible: list[CompanyOutcomeLabel] = []
    exclusions: Counter[LabelExclusion] = Counter()
    for label in scoped:
        reason = _exclusion(label, fit_at, held_out_families)
        if reason is None:
            eligible.append(label)
        else:
            exclusions[reason] += 1
    return CompanyLabelSelection(
        outcome_id=outcome_id,
        fit_at=fit_at,
        labels=tuple(
            sorted(eligible, key=lambda row: (row.decision_at, row.company_id))
        ),
        excluded_counts=tuple(sorted(exclusions.items())),
    )


def _exclusion(
    label: CompanyOutcomeLabel, fit_at: datetime, held_out_families: frozenset[str]
) -> LabelExclusion | None:
    if label.family_id in held_out_families:
        return "held_out_family"
    if label.horizon_end > fit_at:
        return "horizon_not_elapsed_at_fit"
    if label.label_state == "immature":
        return "immature_source_vintage"
    if label.label_state in {"unobserved", "conflicting"}:
        return label.label_state
    if label.available_at is not None and label.available_at > fit_at:
        return "label_not_available_at_fit"
    return None
