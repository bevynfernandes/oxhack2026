"""Training-cohort selection rejects future truth and held-out company families."""

from datetime import UTC, datetime, timedelta

import pytest

from oxhack2026.evaluation.company_labels import select_company_labels
from oxhack2026.features.company_outcomes import CompanyOutcomeId, company_horizon_end
from oxhack2026.models.company_contracts import CompanyOutcomeLabel

OUTCOME: CompanyOutcomeId = "commercial_viability_12m_v1"
DECISION = datetime(2024, 1, 1, tzinfo=UTC)
FIT_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _label(company_id: str = "synthetic-company") -> CompanyOutcomeLabel:
    end = company_horizon_end(DECISION, OUTCOME)
    return CompanyOutcomeLabel(
        company_id=company_id,
        family_id="synthetic-family",
        source_snapshot_id="synthetic-label-source-v1",
        outcome_id=OUTCOME,
        decision_at=DECISION,
        horizon_end=end,
        evaluated_at=FIT_AT,
        label_state="observed",
        value=True,
        available_at=end,
        evidence_ids=("synthetic-source-evidence",),
    )


def test_observed_positive_and_negative_labels_remain_distinct() -> None:
    """Complete observed negatives are usable; they are not manufactured from nulls."""
    positive = _label("synthetic-positive")
    negative = CompanyOutcomeLabel.model_validate(
        _label("synthetic-negative").model_dump()
        | {
            "value": False,
            "reason_codes": ["verified_shutdown"],
        }
    )

    selection = select_company_labels([positive, negative], OUTCOME, FIT_AT)

    assert [row.value for row in selection.labels] == [False, True]
    assert selection.excluded_counts == ()
    assert selection.fit_at == FIT_AT


def test_historical_fit_cannot_see_later_mature_or_later_available_truth() -> None:
    """A current source vintage never makes future evidence available to an old fit."""
    label = _label()

    immature = select_company_labels(
        [label], OUTCOME, label.horizon_end - timedelta(microseconds=1)
    )
    delayed = CompanyOutcomeLabel.model_validate(
        label.model_dump() | {"available_at": label.horizon_end + timedelta(days=1)}
    )
    unknown_at_fit = select_company_labels([delayed], OUTCOME, label.horizon_end)
    at_boundary = select_company_labels([label], OUTCOME, label.horizon_end)

    assert immature.labels == unknown_at_fit.labels == ()
    assert dict(immature.excluded_counts) == {"horizon_not_elapsed_at_fit": 1}
    assert dict(unknown_at_fit.excluded_counts) == {"label_not_available_at_fit": 1}
    assert at_boundary.labels == (label,)


@pytest.mark.parametrize(
    "state,expected_reason",
    [
        ("immature", "immature_source_vintage"),
        ("unobserved", "unobserved"),
        ("conflicting", "conflicting"),
    ],
)
def test_calendar_advancement_never_repairs_incomplete_source_vintage(
    state: str, expected_reason: str
) -> None:
    """Only new explicit source adjudication can replace an unknown old label."""
    base = _label()
    label = CompanyOutcomeLabel.model_validate(
        base.model_dump()
        | {
            "label_state": state,
            "value": None,
            "available_at": None,
            "evaluated_at": base.horizon_end - timedelta(days=1)
            if state == "immature"
            else FIT_AT,
            "reason_codes": ["follow_up_incomplete"],
        }
    )

    selection = select_company_labels([label], OUTCOME, FIT_AT)

    assert selection.labels == ()
    assert dict(selection.excluded_counts) == {expected_reason: 1}


def test_held_out_parent_family_excludes_all_related_companies() -> None:
    """A subsidiary cannot leak into training through a different company ID."""
    labels = [_label("synthetic-parent-product"), _label("synthetic-subsidiary")]

    selection = select_company_labels(
        labels, OUTCOME, FIT_AT, frozenset({"synthetic-family"})
    )

    assert selection.labels == ()
    assert dict(selection.excluded_counts) == {"held_out_family": 2}


def test_each_company_outcome_is_selected_independently() -> None:
    """A financing event cannot become a commercial viability training label."""
    base = _label()
    other: CompanyOutcomeId = "financing_or_acquisition_24m_v1"
    funding = CompanyOutcomeLabel.model_validate(
        base.model_dump()
        | {
            "outcome_id": other,
            "horizon_end": company_horizon_end(DECISION, other),
            "available_at": FIT_AT,
        }
    )

    selection = select_company_labels([funding, base], OUTCOME, FIT_AT)

    assert selection.labels == (base,)
    assert selection.excluded_counts == ()
    assert selection.outcome_id == OUTCOME


def test_ambiguous_vintages_are_not_resolved_by_truth_or_input_order() -> None:
    """A competing vintage requires explicit selection before training eligibility."""
    label = _label()
    conflicting = CompanyOutcomeLabel.model_validate(
        label.model_dump()
        | {
            "value": False,
            "reason_codes": ["negative_operating_cash_flow"],
            "source_snapshot_id": "synthetic-revised-source-v2",
        }
    )

    with pytest.raises(ValueError, match="one explicit label vintage"):
        select_company_labels([label, conflicting], OUTCOME, FIT_AT)
    with pytest.raises(ValueError, match="one explicit label vintage"):
        select_company_labels([conflicting, label], OUTCOME, FIT_AT)


def test_selection_is_order_independent_and_empty_cohorts_stay_empty() -> None:
    """Repeated frozen inputs reproduce row order; an empty cohort invents nothing."""
    labels = [_label("synthetic-z"), _label("synthetic-a")]

    first = select_company_labels(labels, OUTCOME, FIT_AT)
    repeated = select_company_labels(list(reversed(labels)), OUTCOME, FIT_AT)

    assert first == repeated
    assert select_company_labels([], OUTCOME, FIT_AT).labels == ()
    with pytest.raises(ValueError, match="UTC"):
        select_company_labels(labels, OUTCOME, datetime(2026, 1, 1))


def test_exclusion_accounting_counts_each_scoped_row_once() -> None:
    """A held-out family with missing truth has one exclusion, not two."""
    eligible = _label("synthetic-eligible")
    unknown = CompanyOutcomeLabel.model_validate(
        _label("synthetic-unknown").model_dump()
        | {
            "label_state": "unobserved",
            "value": None,
            "available_at": None,
            "reason_codes": ["financial_follow_up_missing"],
        }
    )
    held_out = CompanyOutcomeLabel.model_validate(
        unknown.model_dump()
        | {"company_id": "synthetic-held-out", "family_id": "reserved-family"}
    )

    selection = select_company_labels(
        [eligible, unknown, held_out], OUTCOME, FIT_AT, frozenset({"reserved-family"})
    )

    assert selection.labels == (eligible,)
    assert dict(selection.excluded_counts) == {"held_out_family": 1, "unobserved": 1}
    assert len(selection.labels) + sum(dict(selection.excluded_counts).values()) == 3
