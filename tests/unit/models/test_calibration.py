"""Exact CQR order statistics, frozen pairing, quantile inversion, and gates."""

from dataclasses import replace
from math import expm1
from pathlib import Path

import numpy as np
import orjson
import pytest

from oxhack2026.models.calibrate import (
    IntervalEvidence,
    SubgroupCoverage,
    apply_cqr,
    fit_cqr,
    interval_serving_reasons,
)
from oxhack2026.models.contracts import ModelReference

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/models"


def _model() -> ModelReference:
    payload = orjson.loads((FIXTURES / "forecast-manifest.json").read_bytes())["model"]
    return ModelReference.model_validate(payload)


def _evidence() -> IntervalEvidence:
    return IntervalEvidence(
        calibration_count=500,
        calibration_origins=26,
        calibration_organizations=30,
        test_coverage=0.8,
        interval_score=1.0,
        baseline_interval_score=1.0,
    )


def test_exact_finite_sample_correction_and_crossing_rate() -> None:
    """Four calibration rows use the fourth sorted score, not interpolated quantiles."""
    quantiles = np.array(
        [[2.0, 3.0, 4.0], [4.0, 3.0, 2.0], [2.0, 3.0, 4.0], [2.0, 3.0, 4.0]]
    )
    truth = np.array([1.0, 4.0, 3.0, 10.0])

    correction = fit_cqr(_model(), quantiles, truth, "synthetic-calibration")

    assert correction.log_correction == 6
    assert correction.crossing_rate == 0.25
    assert correction.prediction_count == 4
    np.testing.assert_array_equal(quantiles[1], [4, 3, 2])


def test_interval_widening_and_count_inversion() -> None:
    """Conformal widening happens before inverse transform and zero clipping."""
    model = _model()
    quantiles = np.full((4, 3), [1.0, 2.0, 3.0])
    correction = fit_cqr(model, quantiles, np.array([6.0] * 4), "synthetic")

    band = apply_cqr(correction, model, np.array([[3.0, 2.0, 1.0]]))

    assert correction.log_correction == 3
    assert band.lower[0] == 0
    assert band.upper[0] == pytest.approx(expm1(6))
    assert band.crossing_rate == 1
    assert np.all(band.lower <= band.upper)


def test_zero_correction_when_calibration_actuals_are_inside() -> None:
    """Nonnegative conformity scores never shrink a raw quantile interval."""
    predictions = np.full((4, 3), [1.0, 2.0, 3.0])

    correction = fit_cqr(_model(), predictions, np.array([2.0] * 4), "synthetic")

    assert correction.log_correction == 0


def test_refitted_model_cannot_reuse_correction() -> None:
    """Changing model bytes while retaining its ID still invalidates calibration."""
    model = _model()
    predictions = np.full((4, 3), [1.0, 2.0, 3.0])
    correction = fit_cqr(model, predictions, np.array([2.0] * 4), "synthetic")
    changed = ModelReference.model_validate(
        model.model_dump()
        | {
            "model_artifact": {"path": model.model_artifact.path, "sha256": "b" * 64},
        }
    )

    with pytest.raises(ValueError, match="unchanged model"):
        apply_cqr(correction, changed, predictions)


@pytest.mark.parametrize("shape", [(0, 3), (4, 2), (4,), (2, 3, 1)])
def test_invalid_quantile_shapes(shape: tuple[int, ...]) -> None:
    """Only a nonempty row-aligned triplet of quantiles is supported."""
    with pytest.raises(ValueError, match="array"):
        fit_cqr(_model(), np.zeros(shape), np.zeros(4), "synthetic")


def test_insufficient_finite_sample_support() -> None:
    """Do not clamp the required order statistic to fabricate a valid correction."""
    with pytest.raises(ValueError, match="Insufficient rows"):
        fit_cqr(_model(), np.zeros((3, 3)), np.zeros(3), "synthetic")


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_quantiles_rejected(value: float) -> None:
    """Nonfinite inputs fail before quantile sorting or interval publication."""
    predictions = np.zeros((4, 3))
    predictions[0, 0] = value

    with pytest.raises(ValueError, match="finite"):
        fit_cqr(_model(), predictions, np.zeros(4), "synthetic")


def test_invalid_log_targets_rejected() -> None:
    """Labels must be aligned, finite, and nonnegative on log1p count scale."""
    predictions = np.zeros((4, 3))
    for truth in (np.zeros(3), np.array([-1.0] * 4), np.array([float("nan")] * 4)):
        with pytest.raises(ValueError, match="log targets"):
            fit_cqr(_model(), predictions, truth, "synthetic")


def test_inverse_overflow_rejected() -> None:
    """Unrepresentable endpoints fail instead of publishing infinity or clipping."""
    model = _model()
    correction = fit_cqr(model, np.zeros((4, 3)), np.zeros(4), "synthetic")

    with pytest.raises(ValueError, match="finite count"):
        apply_cqr(correction, model, np.array([[1000.0, 1000.0, 1000.0]]))


def test_exact_interval_gate_boundaries() -> None:
    """All minimum support and inclusive coverage boundaries are tested."""
    evidence = _evidence()

    assert interval_serving_reasons(evidence) == ()
    assert interval_serving_reasons(replace(evidence, test_coverage=0.75)) == ()
    assert interval_serving_reasons(replace(evidence, test_coverage=0.90)) == ()
    assert interval_serving_reasons(replace(evidence, calibration_count=499)) == (
        "insufficient_calibration_predictions",
    )
    assert interval_serving_reasons(replace(evidence, calibration_origins=25)) == (
        "insufficient_calibration_origins",
    )
    assert interval_serving_reasons(
        replace(evidence, calibration_organizations=29)
    ) == ("insufficient_calibration_organizations",)


@pytest.mark.parametrize("coverage", [0.74999, 0.90001])
def test_coverage_outside_serving_gate(coverage: float) -> None:
    """An overly wide or undercovered band both fail the empirical release gate."""
    assert interval_serving_reasons(replace(_evidence(), test_coverage=coverage)) == (
        "overall_coverage_outside_gate",
    )


def test_supported_subgroup_undercoverage() -> None:
    """Subgroup support requires at least 100 rows spanning at least 13 origins."""
    evidence = _evidence()

    assert interval_serving_reasons(
        replace(evidence, subgroups=(SubgroupCoverage(100, 13, 0.69999),))
    ) == ("supported_subgroup_undercoverage",)
    for group in (
        SubgroupCoverage(99, 13, 0.5),
        SubgroupCoverage(100, 12, 0.5),
        SubgroupCoverage(100, 13, 0.7),
    ):
        assert interval_serving_reasons(replace(evidence, subgroups=(group,))) == ()


def test_worse_interval_score_is_experimental() -> None:
    """A calibrated model must meet the preregistered baseline score guardrail."""
    assert interval_serving_reasons(replace(_evidence(), interval_score=1.001)) == (
        "interval_score_worse_than_baseline",
    )


def test_invalid_evidence_rejected() -> None:
    """Nonfinite or impossible coverage/score values cannot pass serving gates."""
    for evidence in (
        replace(_evidence(), test_coverage=float("nan")),
        replace(_evidence(), calibration_count=-1),
        replace(_evidence(), interval_score=-1),
        replace(_evidence(), subgroups=(SubgroupCoverage(1, 1, 1.1),)),
    ):
        with pytest.raises(ValueError, match="valid support"):
            interval_serving_reasons(evidence)
