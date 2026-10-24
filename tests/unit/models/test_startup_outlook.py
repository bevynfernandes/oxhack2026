"""Research model placeholders preserve source coverage without inventing scores."""

from pathlib import Path

import orjson
import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.startup_outlook import (
    SPECIALIST_GROUP_IDS,
    SpecialistGroupId,
    SpecialistOutlook,
    StartupOutlook,
    build_untrained_outlook,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"
GROUPS: dict[str, SpecialistGroupId] = {
    "sdk_downloads_30d_v1": "adoption_retention",
    "sdk_releases_30d_v1": "team_execution",
    "operating_cashflow_12m_usd_v1": "financial_health",
}


def _source() -> CompanySourceSnapshot:
    return CompanySourceSnapshot.model_validate_json(FIXTURE.read_bytes())


def _outlook() -> StartupOutlook:
    return build_untrained_outlook(_source(), "alpha", GROUPS, "synthetic-map-v1")


def _section(outlook: StartupOutlook, group: SpecialistGroupId) -> SpecialistOutlook:
    return next(section for section in outlook.specialists if section.group_id == group)


def test_committed_schema_matches_the_backend_contract() -> None:
    """The schema supplied to backend/UI consumers stays synchronized."""
    path = (
        Path(__file__).resolve().parents[3]
        / "contracts/datasets/models/StartupOutlook.schema.json"
    )

    schema = orjson.loads(path.read_bytes())

    assert schema == StartupOutlook.model_json_schema()


def test_source_identity_zero_and_five_groups_round_trip() -> None:
    """An observed zero is usable evidence but does not create a forecast."""
    source = _source()

    outlook = _outlook()

    assert StartupOutlook.model_validate_json(outlook.model_dump_json()) == outlook
    assert tuple(row.group_id for row in outlook.specialists) == SPECIALIST_GROUP_IDS
    assert outlook.source_snapshot_id == source.snapshot_id
    assert outlook.company_id == "alpha"
    assert outlook.as_of == source.as_of
    assert outlook.synthetic is True
    assert outlook.inference_runtime == "local_cpu"
    assert outlook.overall_outlook is None
    assert outlook.overall_reason_codes == ("model_not_trained",)
    adoption = _section(outlook, "adoption_retention")
    assert adoption.data_status == "available"
    assert adoption.usable_metric_observation_ids == adoption.metric_observation_ids
    assert adoption.evidence_ids == ("alpha-source",)
    assert adoption.model_status == "model_not_trained"
    assert all(row.prediction is None for row in outlook.specialists)
    assert all(
        "beta" not in key for row in outlook.specialists for key in row.evidence_ids
    )


def test_unavailable_groups_and_financial_gaps_remain_distinct() -> None:
    """No assigned observations and missing private metrics retain different reasons."""
    outlook = _outlook()

    attention = _section(outlook, "attention_sentiment")
    financials = _section(outlook, "financial_health")

    assert attention.data_status == financials.data_status == "insufficient_data"
    assert attention.metric_observation_ids == ()
    assert "no_assigned_metrics" in attention.reason_codes
    assert financials.metric_observation_ids
    assert "missing" in financials.reason_codes
    assert financials.evidence_ids == ()


@pytest.mark.parametrize(
    "change,expected",
    [
        ("restricted", "restricted"),
        ("unreviewed", "unverified"),
        ("disputed", "unverified"),
        ("stale", "stale"),
        ("conflicting", "conflicting"),
        ("not_applicable", "not_applicable"),
    ],
)
def test_unusable_values_do_not_count_as_available(change: str, expected: str) -> None:
    """Source/access/freshness policy is shared with model features."""
    payload = _source().model_dump(mode="json")
    if change == "restricted":
        payload["evidence"][0].update(access="restricted", url=None)
    elif change in {"unreviewed", "disputed"}:
        payload["evidence"][0]["review_state"] = change
    elif change == "stale":
        payload["metrics"][0]["window"]["end"] = "2025-01-29T00:00:00Z"
        payload["definitions"][0]["maximum_age_days"] = 1
    else:
        payload["metrics"][0].update(state=change, value=None, reason="Source review")
    source = CompanySourceSnapshot.model_validate(payload)

    outlook = build_untrained_outlook(source, "alpha", GROUPS, "synthetic-map-v1")
    section = _section(outlook, "adoption_retention")

    assert section.data_status == (
        "not_applicable" if change == "not_applicable" else "insufficient_data"
    )
    assert expected in section.reason_codes
    assert section.usable_metric_observation_ids == section.evidence_ids == ()
    assert section.metric_observation_ids


def test_unmapped_metrics_are_preserved_and_order_is_deterministic() -> None:
    """An incomplete policy preserves observations without guessing groups."""
    source = _source()
    payload = source.model_dump()
    payload["metrics"] = tuple(reversed(source.metrics))

    outlook = build_untrained_outlook(source, "alpha", {}, "empty-map-v1")
    reordered = build_untrained_outlook(
        CompanySourceSnapshot.model_validate(payload), "alpha", {}, "empty-map-v1"
    )

    assert outlook == reordered
    assert set(outlook.unassigned_metric_observation_ids) == {
        row.observation_id for row in source.metrics if row.company_id == "alpha"
    }
    assert all(row.data_status == "insufficient_data" for row in outlook.specialists)


def test_unknown_company_mapping_and_empty_policy_fail() -> None:
    """The builder rejects invalid configuration rather than hiding metric mistakes."""
    source = _source()

    with pytest.raises(ValueError, match="Company is absent"):
        build_untrained_outlook(source, "absent", GROUPS, "v1")
    with pytest.raises(ValueError, match="known definitions"):
        build_untrained_outlook(source, "alpha", {"unknown": "financial_health"}, "v1")
    with pytest.raises(ValueError):
        build_untrained_outlook(source, "alpha", GROUPS, "")


@pytest.mark.parametrize("field", ["overall_outlook", "success_score"])
def test_no_numerical_overall_prediction_can_be_injected(field: str) -> None:
    """Neither a plausible score nor an unknown score field bypasses the gate."""
    payload = _outlook().model_dump()

    with pytest.raises(ValueError):
        StartupOutlook.model_validate(payload | {field: 0.8})


@pytest.mark.parametrize(
    "patch",
    [
        {"prediction": 0.8},
        {"model_status": "validated"},
        {"data_status": "insufficient_data"},
        {"usable_metric_observation_ids": ("absent",)},
        {"evidence_ids": ()},
        {"evidence_ids": ("alpha-source", "alpha-source")},
        {"reason_codes": ()},
        {"reason_codes": ("missing",)},
    ],
)
def test_specialist_predictions_and_contradictory_coverage_fail(
    patch: dict[str, object],
) -> None:
    """Available metrics cannot be confused with a trained/validated model."""
    section = _section(_outlook(), "adoption_retention")

    with pytest.raises(ValueError):
        SpecialistOutlook.model_validate(section.model_dump() | patch)


def test_group_inventory_and_assignment_are_unambiguous() -> None:
    """Five unique groups and one assignment per source observation are required."""
    outlook = _outlook()
    payload = outlook.model_dump()

    with pytest.raises(ValueError, match="five groups exactly once"):
        StartupOutlook.model_validate(
            payload | {"specialists": outlook.specialists[:4]}
        )
    with pytest.raises(ValueError, match="five groups exactly once"):
        StartupOutlook.model_validate(
            payload | {"specialists": outlook.specialists[:1] * 5}
        )
    with pytest.raises(ValueError, match="assigned only once"):
        StartupOutlook.model_validate(
            payload
            | {
                "unassigned_metric_observation_ids": outlook.specialists[
                    0
                ].metric_observation_ids
            }
        )
    with pytest.raises(ValueError, match="requires a reason"):
        StartupOutlook.model_validate(payload | {"overall_reason_codes": ()})
