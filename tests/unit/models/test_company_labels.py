"""Company labels preserve full follow-up, calendar horizons and unknown truth."""

from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest

from oxhack2026.features.company_outcomes import CompanyOutcomeId, company_horizon_end
from oxhack2026.models.company_contracts import CompanyOutcomeLabel

DECISION = datetime(2024, 2, 29, 15, 30, tzinfo=UTC)


def _label(
    outcome_id: CompanyOutcomeId = "commercial_viability_12m_v1",
) -> dict[str, object]:
    end = company_horizon_end(DECISION, outcome_id)
    return {
        "company_id": "synthetic-company",
        "family_id": "synthetic-family",
        "source_snapshot_id": "synthetic-label-source-v1",
        "outcome_id": outcome_id,
        "decision_at": DECISION,
        "horizon_end": end,
        "evaluated_at": end + timedelta(days=2),
        "label_state": "observed",
        "value": True,
        "available_at": end + timedelta(days=1),
        "evidence_ids": ["synthetic-confirmed-financial-report"],
    }


@pytest.mark.parametrize(
    "outcome_id,year",
    [
        ("operating_growth_24m_v1", 2026),
        ("commercial_viability_12m_v1", 2025),
        ("financing_or_acquisition_24m_v1", 2026),
    ],
)
def test_calendar_horizon_clamps_leap_day_and_preserves_time(
    outcome_id: CompanyOutcomeId, year: int
) -> None:
    """A Thursday afternoon company assessment does not inherit Monday origins."""
    result = company_horizon_end(DECISION, outcome_id)

    assert result == datetime(year, 2, 28, 15, 30, tzinfo=UTC)


def test_calendar_anniversary_counts_intervening_leap_day() -> None:
    """A year crossing February 2024 is not an unconditional 365-day duration."""
    decision = datetime(2023, 3, 1, tzinfo=UTC)

    short = company_horizon_end(decision, "commercial_viability_12m_v1")
    long = company_horizon_end(decision, "operating_growth_24m_v1")

    assert short == datetime(2024, 3, 1, tzinfo=UTC)
    assert long == datetime(2025, 3, 1, tzinfo=UTC)
    assert short - decision == timedelta(days=366)
    assert long - decision == timedelta(days=731)


@pytest.mark.parametrize(
    "outcome_id",
    [
        "operating_growth_24m_v1",
        "commercial_viability_12m_v1",
        "financing_or_acquisition_24m_v1",
    ],
)
def test_mature_company_labels_round_trip_separately_from_assessments(
    outcome_id: CompanyOutcomeId,
) -> None:
    """Each endpoint has separate source-backed truth, never a pooled success bit."""
    label = CompanyOutcomeLabel.model_validate(_label(outcome_id))

    restored = CompanyOutcomeLabel.model_validate_json(label.model_dump_json())

    assert restored == label
    assert label.outcome_id == outcome_id
    assert label.value is True
    assert "probability" not in label.model_dump()


@pytest.mark.parametrize("state", ["unobserved", "conflicting"])
def test_unknown_or_conflicting_facts_never_become_negative_labels(state: str) -> None:
    """Incomplete financials and contradictory announcements stay outside training."""
    label = CompanyOutcomeLabel.model_validate(
        _label()
        | {
            "label_state": state,
            "value": None,
            "available_at": None,
            "reason_codes": ["financial_follow_up_unavailable"],
        }
    )

    assert label.value is None
    assert label.available_at is None
    with pytest.raises(ValueError, match="Undefined company outcomes"):
        CompanyOutcomeLabel.model_validate(label.model_dump() | {"value": False})


def test_explicit_negative_requires_observed_complete_follow_up() -> None:
    """False is valid source-backed truth; it is never inferred from a null."""
    label = CompanyOutcomeLabel.model_validate(
        _label() | {"value": False, "reason_codes": ["verified_shutdown"]}
    )

    assert label.value is False
    with pytest.raises(ValueError, match="supporting source evidence"):
        CompanyOutcomeLabel.model_validate(label.model_dump() | {"evidence_ids": []})
    with pytest.raises(ValueError, match="precise observed reason"):
        CompanyOutcomeLabel.model_validate(label.model_dump() | {"reason_codes": []})


def test_horizon_maturity_is_inclusive_but_one_microsecond_early_is_immature() -> None:
    """Early positives cannot bypass complete horizon follow-up."""
    end = company_horizon_end(DECISION, "commercial_viability_12m_v1")
    base = _label() | {"available_at": end, "evaluated_at": end}

    assert CompanyOutcomeLabel.model_validate(base).value is True
    with pytest.raises(ValueError, match="complete calendar-horizon"):
        CompanyOutcomeLabel.model_validate(
            base | {"evaluated_at": end - timedelta(microseconds=1)}
        )
    immature = CompanyOutcomeLabel.model_validate(
        base
        | {
            "label_state": "immature",
            "evaluated_at": end - timedelta(microseconds=1),
            "value": None,
            "available_at": None,
            "reason_codes": ["horizon_not_elapsed"],
        }
    )
    assert immature.value is None


@pytest.mark.parametrize(
    "change",
    [
        {"available_at": datetime(2025, 2, 28, 15, 29, tzinfo=UTC)},
        {"available_at": datetime(2025, 3, 5, tzinfo=UTC)},
        {"horizon_end": datetime(2025, 3, 1, 15, 30, tzinfo=UTC)},
        {"evaluated_at": DECISION - timedelta(seconds=1)},
        {
            "label_state": "immature",
            "value": None,
            "available_at": None,
            "reason_codes": ["not_yet"],
        },
        {"label_state": "unobserved", "value": None, "available_at": None},
        {"value": None},
        {"available_at": None},
    ],
)
def test_temporally_invalid_or_undefined_labels_fail(change: dict[str, object]) -> None:
    """Future support, shifted horizons and inconsistent missingness are rejected."""
    with pytest.raises(ValueError):
        CompanyOutcomeLabel.model_validate(_label() | change)


@pytest.mark.parametrize("value", [0, 1, "false", "true"])
def test_truth_does_not_coerce_numbers_or_strings_to_booleans(value: object) -> None:
    """External missing-value conventions cannot silently become company outcomes."""
    with pytest.raises(ValueError):
        CompanyOutcomeLabel.model_validate(_label() | {"value": value})


@pytest.mark.parametrize(
    "value",
    [datetime(2024, 2, 29), datetime(2024, 2, 29, tzinfo=timezone(timedelta(hours=1)))],
)
def test_company_cutoffs_require_utc(value: datetime) -> None:
    """Timezone ambiguity is rejected before either features or labels are built."""
    with pytest.raises(ValueError, match="UTC"):
        company_horizon_end(value, "commercial_viability_12m_v1")
    with pytest.raises(ValueError, match="UTC"):
        CompanyOutcomeLabel.model_validate(_label() | {"decision_at": value})


def test_unknown_outcome_and_calendar_overflow_fail_explicitly() -> None:
    """Version typos and unrepresentable anniversaries cannot select a fallback."""
    with pytest.raises(ValueError, match="Unsupported"):
        company_horizon_end(DECISION, cast(CompanyOutcomeId, "downloads_next_30d_v1"))
    with pytest.raises(ValueError):
        company_horizon_end(
            datetime(9999, 1, 1, tzinfo=UTC), "commercial_viability_12m_v1"
        )
