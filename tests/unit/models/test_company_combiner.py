"""Saved synthetic safety tests; their performance is not real-company validation."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.features.company_outcomes import company_horizon_end
from oxhack2026.models.company_combiner import (
    CompanyCombinerModel,
    CompanyCombinerPlan,
    predict_company_combiner,
    run_company_combiner,
)
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"


def _sources() -> tuple[CompanySourceSnapshot, ...]:
    sources = []
    for index, year in enumerate((2020, 2020, 2022, 2022, 2024, 2024)):
        content = FIXTURE.read_text().replace("2025-", f"{year}-")
        for name in ("alpha", "beta"):
            content = content.replace(name, f"{name}-{index}")
        source = CompanySourceSnapshot.model_validate_json(content)
        # Exercise real-source branches with explicitly synthetic test-only content.
        sources.append(
            CompanySourceSnapshot.model_validate(
                source.model_dump()
                | {"snapshot_id": f"test-source-{index}", "synthetic": False}
            )
        )
    return tuple(sources)


def _plan() -> CompanyCombinerPlan:
    return CompanyCombinerPlan(
        experiment_id="synthetic-blend-test-only",
        outcome_id="commercial_viability_12m_v1",
        # Toy features exercise plumbing, not five distinct real constructs.
        group_metrics={
            group: (
                "sdk_releases_30d_v1"
                if group == "team_execution"
                else "sdk_downloads_30d_v1",
            )
            for group in SPECIALIST_GROUP_IDS
        },
        base_snapshot_ids=("test-source-0", "test-source-1"),
        blend_snapshot_ids=("test-source-2", "test-source-3"),
        test_snapshot_ids=("test-source-4", "test-source-5"),
        base_fit_at=datetime(2022, 1, 1, tzinfo=UTC),
        fit_at=datetime(2024, 1, 1, tzinfo=UTC),
        evaluated_at=datetime(2026, 10, 24, tzinfo=UTC),
        minimum_base_per_class=2,
        minimum_blend_per_class=2,
        minimum_test_per_class=2,
    )


def _labels(
    sources: tuple[CompanySourceSnapshot, ...],
) -> tuple[CompanyOutcomeLabel, ...]:
    plan = _plan()
    return tuple(
        CompanyOutcomeLabel(
            company_id=company.company_id,
            family_id=company.company_id,
            source_snapshot_id="synthetic-truth-only",
            outcome_id=plan.outcome_id,
            decision_at=source.as_of,
            horizon_end=company_horizon_end(source.as_of, plan.outcome_id),
            evaluated_at=plan.evaluated_at,
            label_state="observed",
            value=company.company_id.startswith("beta"),
            available_at=company_horizon_end(source.as_of, plan.outcome_id),
            evidence_ids=("synthetic-test-evidence",),
            reason_codes=("synthetic-test-truth",),
        )
        for source in sources
        for company in source.companies
    )


def test_combiner_fits_roundtrips_and_compares_identical_rows() -> None:
    """Real sklearn fitting and portable JSON use the same untouched test rows."""
    sources = _sources()

    result = run_company_combiner(_plan(), sources, _labels(sources))

    assert result.status == "experimental"
    assert result.model is not None
    restored = CompanyCombinerModel.model_validate_json(result.model.model_dump_json())
    assert predict_company_combiner(restored, sources[4]) == predict_company_combiner(
        result.model, sources[4]
    )
    assert len(result.test_metrics) == 7
    assert {metric.matched_count for metric in result.test_metrics.values()} == {4}
    assert result.counts["blend_matched_labels"] == 4
    assert "public_release_not_validated" in result.reasons


def test_final_test_values_and_truth_cannot_change_fitted_parameters() -> None:
    """Changing the entire future distribution cannot alter either fitted stage."""
    sources = _sources()
    labels = _labels(sources)
    first = run_company_combiner(_plan(), sources, labels)
    changed = []
    for source in sources[4:]:
        payload = source.model_dump()
        for metric in payload["metrics"]:
            if metric["value"] is not None:
                metric["value"]["value"] = 1000000
        changed.append(CompanySourceSnapshot.model_validate(payload))
    changed_labels = tuple(
        CompanyOutcomeLabel.model_validate(row.model_dump() | {"value": not row.value})
        if row.decision_at >= _plan().fit_at
        else row
        for row in labels
    )

    second = run_company_combiner(_plan(), (*sources[:4], *changed), changed_labels)

    assert first.model is not None
    assert first.model == second.model


def test_blend_truth_changes_combiner_but_never_specialists() -> None:
    """The later blending labels influence only the second fitting stage."""
    sources = _sources()
    labels = _labels(sources)
    first = run_company_combiner(_plan(), sources, labels)
    changed = tuple(
        CompanyOutcomeLabel.model_validate(row.model_dump() | {"value": not row.value})
        if _plan().base_fit_at <= row.decision_at < _plan().fit_at
        else row
        for row in labels
    )

    second = run_company_combiner(_plan(), sources, changed)

    assert first.model is not None and second.model is not None
    assert first.model.specialists == second.model.specialists
    assert first.model.coefficients != second.model.coefficients


def test_one_missing_group_abstains_instead_of_renormalizing() -> None:
    """A company without one specialist gets no combined forecast."""
    sources = _sources()
    result = run_company_combiner(_plan(), sources, _labels(sources))
    assert result.model is not None
    payload = sources[4].model_dump()
    for metric in payload["metrics"]:
        if (
            metric["company_id"] == "alpha-4"
            and metric["metric_id"] == "sdk_releases_30d_v1"
        ):
            metric.update(
                value=None,
                state="missing",
                reason="Synthetic missing execution feature",
                evidence_ids=(),
            )
    missing = CompanySourceSnapshot.model_validate(payload)

    forecasts = predict_company_combiner(result.model, missing)

    assert [row.company_id for row in forecasts] == ["beta-4"]


@pytest.mark.parametrize("partition", (0, 2, 4))
def test_synthetic_sources_never_fit_any_stage(partition: int) -> None:
    """Every input partition is protected before any model fit."""
    sources = list(_sources())
    sources[partition] = CompanySourceSnapshot.model_validate(
        sources[partition].model_dump() | {"synthetic": True}
    )

    with patch("oxhack2026.models.company_combiner.run_company_experiment") as fit:
        result = run_company_combiner(_plan(), sources, ())

    fit.assert_not_called()
    assert result.reasons == ("synthetic_sources_forbidden",)


def test_missing_specialist_support_blocks_combiner_fitting() -> None:
    """Empty truth produces retained base failures and no fitted combined score."""
    with patch("oxhack2026.models.company_combiner._fit_combiner") as fit:
        result = run_company_combiner(_plan(), _sources(), ())

    fit.assert_not_called()
    assert result.reasons == ("specialist_training_gates_failed",)
    assert len(result.specialist_results) == 5


def test_future_blend_labels_are_not_training_truth() -> None:
    """Late available blending labels cannot enter either fitting stage."""
    sources = _sources()
    labels = tuple(
        CompanyOutcomeLabel.model_validate(
            row.model_dump() | {"available_at": _plan().evaluated_at}
        )
        if _plan().base_fit_at <= row.decision_at < _plan().fit_at
        else row
        for row in _labels(sources)
    )

    result = run_company_combiner(_plan(), sources, labels)

    assert result.status == "blocked"
    assert result.model is None


@pytest.mark.parametrize("reuse_company", (True, False))
def test_overlapping_company_or_family_periods_are_rejected(
    reuse_company: bool,
) -> None:
    """A final-test company cannot leak into specialist or blending fitting."""
    sources = _sources()
    if reuse_company:
        reused = CompanySourceSnapshot.model_validate_json(
            sources[4].model_dump_json().replace("alpha-4", "alpha-0")
        )
    else:
        payload = sources[4].model_dump()
        payload["relationships"][0]["subject_id"] = "alpha-0"
        reused = CompanySourceSnapshot.model_validate(payload)

    with pytest.raises(ValueError, match="company/family disjoint"):
        run_company_combiner(_plan(), (*sources[:4], reused, sources[5]), ())


def test_duplicate_final_origins_and_reversed_source_times_are_rejected() -> None:
    """Final-period dict projection cannot overwrite duplicate company/origin rows."""
    sources = _sources()
    duplicated = CompanySourceSnapshot.model_validate(
        sources[4].model_dump() | {"snapshot_id": "test-source-5"}
    )
    with pytest.raises(ValueError, match="company/family disjoint"):
        run_company_combiner(_plan(), (*sources[:5], duplicated), ())
    wrong_time = CompanySourceSnapshot.model_validate_json(
        sources[4].model_dump_json().replace("2024-", "2022-")
    )
    with pytest.raises(ValueError, match="chronological"):
        run_company_combiner(_plan(), (*sources[:4], wrong_time, sources[5]), ())


def test_reversed_periods_missing_groups_and_wrong_model_order_are_rejected() -> None:
    """Plan and portable-model validation preserve exact five-group semantics."""
    plan = _plan()
    for changes in (
        {"fit_at": plan.base_fit_at},
        {"group_metrics": {"team_execution": ("sdk_downloads_30d_v1",)}},
        {"test_snapshot_ids": plan.blend_snapshot_ids},
    ):
        with pytest.raises(ValueError):
            CompanyCombinerPlan.model_validate(plan.model_dump() | changes)
    sources = _sources()
    result = run_company_combiner(plan, sources, _labels(sources))
    assert result.model is not None

    with pytest.raises(ValueError, match="model lineage"):
        CompanyCombinerModel.model_validate(
            result.model.model_dump()
            | {"specialists": tuple(reversed(result.model.specialists))}
        )
    with pytest.raises(ValueError, match="precede"):
        predict_company_combiner(result.model, sources[2])


def test_insufficient_final_test_support_never_fits_combiner() -> None:
    """A one-class final test does not produce misleading accuracy or a model."""
    sources = _sources()
    labels = tuple(
        CompanyOutcomeLabel.model_validate(row.model_dump() | {"value": True})
        if row.decision_at >= _plan().fit_at
        else row
        for row in _labels(sources)
    )

    with patch("oxhack2026.models.company_combiner._fit_combiner") as fit:
        result = run_company_combiner(_plan(), sources, labels)

    fit.assert_not_called()
    assert "test_insufficient_negative_families" in result.reasons
