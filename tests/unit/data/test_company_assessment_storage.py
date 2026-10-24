"""C1/C2 composition guards, independent of model interpretation and filesystem."""

from datetime import timedelta

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company_assessments import validate_company_assessments
from oxhack2026.storage.contracts import ArtifactStore


def test_valid_company_composition(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
) -> None:
    """Saved C2 records bind exactly to source company, family and evidence IDs."""
    validate_company_assessments(company_source[0], company_assessments)


@pytest.mark.parametrize(
    "change",
    [
        "foreign_metric",
        "foreign_evidence",
        "unknown_definition",
        "omitted_support",
        "wrong_snapshot",
        "wrong_cutoff",
        "wrong_synthetic",
        "wrong_family",
        "too_early",
        "mixed_policy",
    ],
)
def test_rejects_incompatible_composition(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
    change: str,
) -> None:
    """Correctly shaped model records still need cross-artifact integrity checks."""
    source = company_source[0]
    payload = company_assessments[0].model_dump()
    updates: dict[str, dict[str, object]] = {
        "wrong_snapshot": {"source_snapshot_id": "different"},
        "wrong_synthetic": {"synthetic": False},
        "wrong_family": {"family_id": "different"},
        "too_early": {"first_recorded_at": source.recorded_at - timedelta(seconds=1)},
        "mixed_policy": {"policy_version": "another-policy"},
    }
    if change == "foreign_metric":
        payload["statements"][0]["metric_observation_ids"] = (
            "beta-sdk_downloads_30d_v1",
        )
    elif change == "foreign_evidence":
        payload["statements"][0]["evidence_ids"] = ("beta-source",)
    elif change == "unknown_definition":
        payload["statements"][2]["missing_metric_ids"] = ("unknown",)
    elif change == "omitted_support":
        payload["statements"][0]["role"] = "evidence_gap"
        payload["statements"][0]["missing_metric_ids"] = (
            "operating_cashflow_12m_usd_v1",
        )
        payload["statements"][0]["evidence_ids"] = ()
        payload["outcomes"][0].update(
            assessment_status="unavailable", reason_codes=("gap",)
        )
    elif change == "wrong_cutoff":
        from oxhack2026.features.company_outcomes import company_horizon_end

        cutoff = source.as_of - timedelta(days=1)
        payload["as_of"] = cutoff
        for outcome in payload["outcomes"]:
            outcome["horizon_end"] = company_horizon_end(cutoff, outcome["outcome_id"])
    else:
        payload.update(updates[change])
    changed = CompanyAssessment.model_validate(payload)
    with pytest.raises(ValueError):
        validate_company_assessments(source, (changed, company_assessments[1]))


def test_requires_complete_unique_company_set(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
) -> None:
    """Missing companies and duplicate assessment IDs cannot silently publish."""
    with pytest.raises(ValueError, match="one uniquely"):
        validate_company_assessments(company_source[0], company_assessments[:1])
    duplicate = CompanyAssessment.model_validate(
        company_assessments[1].model_dump()
        | {"assessment_id": company_assessments[0].assessment_id}
    )
    with pytest.raises(ValueError, match="one uniquely"):
        validate_company_assessments(
            company_source[0], (company_assessments[0], duplicate)
        )
