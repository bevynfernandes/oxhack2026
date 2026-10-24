"""Saved synthetic tests of training isolation; never real model validation."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.features.company_outcomes import company_horizon_end
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.company_training import (
    CompanyExperimentPlan,
    CompanyLogisticModel,
    predict_company_logistic,
    run_company_experiment,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"


def _source(index: int, year: int) -> CompanySourceSnapshot:
    # Exercise the real-source code branch using explicitly synthetic test content.
    content = FIXTURE.read_text().replace("2025-", f"{year}-")
    content = content.replace("alpha", f"alpha-{index}")
    content = content.replace("beta", f"beta-{index}")
    snapshot = CompanySourceSnapshot.model_validate_json(content)
    return CompanySourceSnapshot.model_validate(
        snapshot.model_dump()
        | {"snapshot_id": f"test-source-{index}", "synthetic": False}
    )


def _plan() -> CompanyExperimentPlan:
    return CompanyExperimentPlan(
        experiment_id="synthetic-test-only",
        group_id="adoption_retention",
        outcome_id="commercial_viability_12m_v1",
        metric_ids=("sdk_downloads_30d_v1",),
        train_snapshot_ids=("test-source-0", "test-source-1"),
        test_snapshot_ids=("test-source-2", "test-source-3"),
        fit_at=datetime(2024, 1, 1, tzinfo=UTC),
        evaluated_at=datetime(2026, 10, 24, tzinfo=UTC),
        minimum_train_per_class=2,
        minimum_test_per_class=2,
    )


def _sources() -> tuple[CompanySourceSnapshot, ...]:
    return (_source(0, 2021), _source(1, 2021), _source(2, 2024), _source(3, 2024))


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
            evidence_ids=("synthetic-label-evidence",),
            reason_codes=("synthetic-test-truth",),
        )
        for source in sources
        for company in source.companies
    )


def test_real_fit_roundtrip_and_identical_baseline_holdout() -> None:
    """Actual sklearn fitting survives JSON and improves on an obvious toy baseline."""
    sources = _sources()

    result = run_company_experiment(_plan(), sources, _labels(sources))

    assert result.status == "experimental"
    assert result.model is not None
    restored = CompanyLogisticModel.model_validate_json(result.model.model_dump_json())
    assert predict_company_logistic(restored, sources[2]) == predict_company_logistic(
        result.model, sources[2]
    )
    assert result.logistic_metrics is not None
    assert result.prevalence_metrics is not None
    assert (
        result.logistic_metrics.matched_count == result.prevalence_metrics.matched_count
    )
    assert result.logistic_metrics.matched_count == 4
    assert result.beats_prevalence is True
    assert "public_release_not_validated" in result.reasons


def test_holdout_values_and_truth_cannot_change_training_parameters() -> None:
    """A different future distribution cannot change medians, scaling or weights."""
    sources = _sources()
    labels = _labels(sources)
    first = run_company_experiment(_plan(), sources, labels)
    changed = []
    for source in sources[2:]:
        payload = source.model_dump()
        for metric in payload["metrics"]:
            if metric["value"] is not None:
                metric["value"]["value"] = 1000000
        changed.append(CompanySourceSnapshot.model_validate(payload))
    changed_labels = tuple(
        CompanyOutcomeLabel.model_validate(
            label.model_dump() | {"value": not label.value}
        )
        if label.decision_at >= _plan().fit_at
        else label
        for label in labels
    )

    second = run_company_experiment(_plan(), (*sources[:2], *changed), changed_labels)

    assert first.model == second.model


def test_synthetic_source_never_reaches_fitting() -> None:
    """Fixture protection is enforced before any sklearn fit."""
    sources = _sources()
    synthetic = CompanySourceSnapshot.model_validate(
        sources[0].model_dump() | {"synthetic": True}
    )

    with patch("oxhack2026.models.company_training._fit") as fit:
        result = run_company_experiment(_plan(), (synthetic, *sources[1:]), ())

    fit.assert_not_called()
    assert result.reasons == ("synthetic_sources_forbidden",)


def test_missing_and_future_labels_prevent_training() -> None:
    """Absent truth and late-arriving training truth never become negatives."""
    sources = _sources()
    labels = tuple(
        CompanyOutcomeLabel.model_validate(
            label.model_dump() | {"available_at": _plan().evaluated_at}
        )
        for label in _labels(sources)
    )

    result = run_company_experiment(_plan(), sources, labels)
    empty = run_company_experiment(_plan(), sources, ())

    assert result.status == empty.status == "blocked"
    assert result.model is empty.model is None
    assert result.counts["training_label_label_not_available_at_fit"] == 4
    assert empty.counts["training_labels"] == 0


def test_heldout_family_is_excluded_even_without_test_features() -> None:
    """A missing-data test company still reserves its family from training."""
    sources = _sources()
    payload = sources[2].model_dump()
    payload["relationships"][0]["subject_id"] = "alpha-0"
    for metric in payload["metrics"]:
        if metric["company_id"] == "alpha-2":
            metric.update(state="missing", value=None, reason="Synthetic missingness")
    changed = (*sources[:2], CompanySourceSnapshot.model_validate(payload), sources[3])
    labels = tuple(label for label in _labels(sources) if label.company_id != "alpha-2")

    result = run_company_experiment(_plan(), changed, labels)

    assert result.status == "blocked"
    assert result.counts["training_label_held_out_family"] == 1
    assert result.counts["test_no_usable_features"] == 1


def test_unobserved_metric_and_definition_drift_are_rejected() -> None:
    """All-missing columns cannot fit and a changed unit cannot silently transfer."""
    sources = _sources()
    plan = CompanyExperimentPlan.model_validate(
        _plan().model_dump() | {"metric_ids": ("operating_cashflow_12m_usd_v1",)}
    )

    result = run_company_experiment(plan, sources, _labels(sources))

    assert result.status == "blocked"
    assert "training_metric_unobserved:operating_cashflow_12m_usd_v1" in result.reasons
    payload = sources[2].model_dump()
    payload["definitions"][0]["definition"] = "Changed test definition"
    drift = CompanySourceSnapshot.model_validate(payload)
    with pytest.raises(ValueError, match="definition changed"):
        run_company_experiment(_plan(), (*sources[:2], drift, sources[3]), ())


def test_wrong_dates_duplicates_and_label_families_fail() -> None:
    """Inconsistent temporal partitions and identity joins fail before fitting."""
    sources = _sources()
    with pytest.raises(ValueError, match="exactly the unique"):
        run_company_experiment(_plan(), (*sources, sources[0]), ())
    with pytest.raises(ValueError, match="chronological"):
        run_company_experiment(
            CompanyExperimentPlan.model_validate(
                _plan().model_dump() | {"fit_at": sources[0].as_of}
            ),
            sources,
            (),
        )
    labels = _labels(sources)
    wrong = CompanyOutcomeLabel.model_validate(
        labels[0].model_dump() | {"family_id": "unrelated-family"}
    )
    with pytest.raises(ValueError, match="Label family conflicts"):
        run_company_experiment(_plan(), sources, (wrong, *labels[1:]))


@pytest.mark.parametrize(
    "changes",
    [
        {"metric_ids": ()},
        {"metric_ids": ("x", "x")},
        {"test_snapshot_ids": ("test-source-0",)},
        {"minimum_train_per_class": 1},
        {"evaluated_at": datetime(2020, 1, 1, tzinfo=UTC)},
    ],
)
def test_invalid_plan_is_rejected(changes: dict[str, object]) -> None:
    """A reproducible plan requires nonoverlapping identities and meaningful gates."""
    with pytest.raises(ValueError):
        CompanyExperimentPlan.model_validate(_plan().model_dump() | changes)


def test_prediction_rejects_old_synthetic_and_incompatible_sources() -> None:
    """The inference path enforces the same source definitions and fit cutoff."""
    sources = _sources()
    result = run_company_experiment(_plan(), sources, _labels(sources))
    assert result.model is not None
    with pytest.raises(ValueError, match="at or after"):
        predict_company_logistic(result.model, sources[0])
    synthetic = CompanySourceSnapshot.model_validate(
        sources[2].model_dump() | {"synthetic": True}
    )
    with pytest.raises(ValueError, match="real source"):
        predict_company_logistic(result.model, synthetic)
    with pytest.raises(ValueError, match="ordered production features"):
        CompanyLogisticModel.model_validate(
            result.model.model_dump() | {"scales": (-1, 1)}
        )
