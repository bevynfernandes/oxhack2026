"""Evidence assessment integrity and separation from future outcome labels."""

from datetime import timedelta
from pathlib import Path

import pytest

from oxhack2026.models.company_assessments import (
    AssessmentStatement,
    CompanyAssessment,
    CompanyOutcomeAssessment,
)

FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures/models/company-assessment.json"
)


def _assessment() -> CompanyAssessment:
    return CompanyAssessment.model_validate_json(FIXTURE.read_bytes())


def test_three_company_outcomes_round_trip_with_explicit_unknowns() -> None:
    """Profiles retain unknown sections and null probabilities."""
    assessment = _assessment()

    restored = CompanyAssessment.model_validate_json(assessment.model_dump_json())

    assert restored == assessment
    assert assessment.synthetic is True
    assert len(assessment.outcomes) == 3
    assert assessment.outcomes[1].assessment_status == "unavailable"
    assert all(row.probability is None for row in assessment.outcomes)
    assert all("value" not in row.model_dump() for row in assessment.outcomes)


def test_unresolved_family_stays_explicit_without_removing_company() -> None:
    """Missing ownership does not silently drop a company from the evidence product."""
    payload = _assessment().model_dump() | {
        "family_id": None,
        "family_reason_codes": ["historical_parent_unknown"],
    }

    unresolved = CompanyAssessment.model_validate(payload)

    assert unresolved.family_id is None
    assert len(unresolved.outcomes) == 3
    with pytest.raises(ValueError, match="explicit ownership reasons"):
        CompanyAssessment.model_validate(payload | {"family_reason_codes": []})


@pytest.mark.parametrize("probability", [0, 0.5, 1])
def test_evidence_cannot_become_a_success_probability(probability: float) -> None:
    """Plausible numbers cannot bypass the later prediction gate."""
    outcome = _assessment().outcomes[0]

    with pytest.raises(ValueError):
        CompanyOutcomeAssessment.model_validate(
            outcome.model_dump() | {"probability": probability}
        )
    with pytest.raises(ValueError):
        CompanyOutcomeAssessment.model_validate(
            outcome.model_dump() | {"assessment_status": "validated_probability"}
        )


def test_future_truth_and_composite_scores_are_not_assessment_fields() -> None:
    """The company list/profile schema cannot absorb outcome reveal payloads."""
    assessment = _assessment()

    with pytest.raises(ValueError):
        CompanyAssessment.model_validate(
            assessment.model_dump() | {"success_score": 85}
        )
    with pytest.raises(ValueError):
        CompanyOutcomeAssessment.model_validate(
            assessment.outcomes[0].model_dump() | {"value": True}
        )


def test_missing_or_duplicate_outcome_sections_fail() -> None:
    """Missing or repeated outcomes cannot alter coverage."""
    assessment = _assessment()

    with pytest.raises(ValueError, match="three outcomes once"):
        CompanyAssessment.model_validate(
            assessment.model_dump() | {"outcomes": assessment.outcomes[:2]}
        )
    with pytest.raises(ValueError, match="three outcomes once"):
        CompanyAssessment.model_validate(
            assessment.model_dump() | {"outcomes": (assessment.outcomes[0],) * 3}
        )


def test_statement_references_and_ids_must_resolve_unambiguously() -> None:
    """An explanation cannot silently cite the wrong or missing internal statement."""
    assessment = _assessment()
    bad_outcome = assessment.outcomes[0].model_dump() | {"statement_ids": ["unknown"]}

    with pytest.raises(ValueError, match="unknown assessment statement"):
        CompanyAssessment.model_validate(
            assessment.model_dump()
            | {"outcomes": [bad_outcome, *assessment.outcomes[1:]]}
        )
    with pytest.raises(ValueError, match="statement IDs must be unique"):
        CompanyAssessment.model_validate(
            assessment.model_dump()
            | {"statements": (*assessment.statements, assessment.statements[0])}
        )


def test_evidence_gaps_alone_cannot_create_a_supported_outlook() -> None:
    """Unknown financials stay unavailable instead of becoming reassuring evidence."""
    assessment = _assessment()
    commercial = assessment.outcomes[1].model_dump() | {
        "assessment_status": "evidence_only"
    }

    with pytest.raises(ValueError, match="Evidence gaps alone"):
        CompanyAssessment.model_validate(
            assessment.model_dump()
            | {"outcomes": [assessment.outcomes[0], commercial, assessment.outcomes[2]]}
        )


def test_observed_facts_cannot_be_hidden_under_unavailable_status() -> None:
    """Observed facts and unavailable states cannot disagree."""
    assessment = _assessment()
    operating = assessment.outcomes[0].model_dump() | {
        "assessment_status": "unavailable"
    }

    with pytest.raises(ValueError, match="Evidence gaps alone"):
        CompanyAssessment.model_validate(
            assessment.model_dump()
            | {"outcomes": [operating, *assessment.outcomes[1:]]}
        )


def test_facts_risks_and_gaps_require_their_support_or_missing_definition() -> None:
    """A warning needs evidence; a gap needs a named missing definition."""
    observation = _assessment().statements[0]
    gap = _assessment().statements[1]

    with pytest.raises(ValueError, match="requires source evidence"):
        AssessmentStatement.model_validate(
            observation.model_dump() | {"role": "risk", "evidence_ids": []}
        )
    with pytest.raises(ValueError, match="missing metric definitions"):
        AssessmentStatement.model_validate(
            gap.model_dump() | {"missing_metric_ids": []}
        )


def test_prospective_recording_must_precede_cutoff_and_horizons_match() -> None:
    """A later-written reconstruction never becomes a prospective assessment."""
    assessment = _assessment()

    with pytest.raises(ValueError, match="recorded before cutoff"):
        CompanyAssessment.model_validate(
            assessment.model_dump()
            | {"mode": "prospective", "first_recorded_at": assessment.as_of}
        )
    recorded = CompanyAssessment.model_validate(
        assessment.model_dump()
        | {
            "mode": "prospective",
            "first_recorded_at": assessment.as_of - timedelta(microseconds=1),
        }
    )
    assert recorded.mode == "prospective"
    with pytest.raises(ValueError, match="horizon does not match"):
        CompanyAssessment.model_validate(
            assessment.model_dump() | {"as_of": assessment.as_of + timedelta(days=1)}
        )
