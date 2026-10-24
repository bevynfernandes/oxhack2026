"""Saved C2 schema, fixture, temporal-boundary, and reveal-isolation checks."""

import builtins
import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import orjson
import pytest
from pydantic import ValidationError

from oxhack2026.evaluation.contracts import (
    CohortCounts,
    EvaluationReport,
    EvidenceItem,
    OutcomeDiagnostics,
    RankedCandidate,
    ShortlistScore,
)
from oxhack2026.models.contracts import (
    ArtifactReference,
    Contract,
    FeatureManifest,
    FeatureRow,
    ForecastManifest,
    ForecastResult,
    LabelRow,
    MatureOutcome,
    ModelReference,
    PredictionInterval,
    TargetWindows,
    TimeWindow,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/models"
SCHEMAS = Path(__file__).resolve().parents[3] / "contracts/datasets/models"


def _forecast(name: str = "ready") -> ForecastResult:
    return ForecastResult.model_validate(
        orjson.loads((FIXTURES / f"{name}.json").read_bytes())
    )


@pytest.mark.parametrize(
    "name",
    [
        "ready",
        "insufficient-history",
        "low-reference-count",
        "missing-source",
        "unvalidated-interval",
        "baseline",
    ],
)
def test_forecast_fixtures(name: str) -> None:
    """Validate each synthetic rendering state and preserve JSON round trips."""
    forecast = _forecast(name)

    restored = ForecastResult.model_validate_json(forecast.model_dump_json())

    assert restored == forecast
    assert forecast.identity.dataset_version.startswith("synthetic-")
    assert "actual_downloads" not in forecast.model_dump_json()


@pytest.mark.parametrize(
    "contract",
    [
        FeatureRow,
        LabelRow,
        FeatureManifest,
        ModelReference,
        ForecastManifest,
        ForecastResult,
        MatureOutcome,
        EvaluationReport,
        EvidenceItem,
        OutcomeDiagnostics,
        RankedCandidate,
        ShortlistScore,
    ],
)
def test_schema_exports_do_not_drift(contract: type[Contract]) -> None:
    """Compare committed JSON Schemas with the source Python types."""
    expected = orjson.loads((SCHEMAS / f"{contract.__name__}.schema.json").read_bytes())

    actual = contract.model_json_schema()

    assert actual == expected


@pytest.mark.parametrize(
    "path", ["../secret", "/absolute/data", "a/../../b", r"a\b", "."]
)
def test_artifact_paths_cannot_escape_bundle(path: str) -> None:
    """Reject unsafe artifact paths before any filesystem read is attempted."""
    with pytest.raises(ValidationError, match="relative path"):
        ArtifactReference(
            path=path,
            sha256="a" * 64,
            byte_size=0,
            media_type="application/octet-stream",
        )


def test_artifact_digest_and_safe_path() -> None:
    """Accept a relative hashed artifact and reject malformed hashes."""
    artifact = ArtifactReference(
        path="models/ridge.bin",
        sha256="a" * 64,
        byte_size=0,
        media_type="application/octet-stream",
    )

    assert artifact.path == "models/ridge.bin"
    with pytest.raises(ValidationError):
        ArtifactReference(
            path="models/ridge.bin",
            sha256="unknown",
            byte_size=0,
            media_type="application/octet-stream",
        )


@pytest.mark.parametrize("hour_offset", [None, 1, -1])
def test_windows_require_utc(hour_offset: int | None) -> None:
    """Reject naive boundaries and timezone offsets rather than guessing UTC."""
    from datetime import timezone

    zone = None if hour_offset is None else timezone(timedelta(hours=hour_offset))
    start = datetime(2025, 1, 1, tzinfo=zone)

    with pytest.raises(ValidationError, match="UTC"):
        TimeWindow(start=start, end=start + timedelta(days=1))


def test_empty_window_is_invalid() -> None:
    """Half-open measurement windows must have positive duration."""
    instant = datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(ValidationError, match="start < end"):
        TimeWindow(start=instant, end=instant)


def test_worked_target_boundaries() -> None:
    """The plan's saved January fixture uses the exact fixed 48-hour anchor."""
    windows = _forecast().windows

    assert windows.reference.start == datetime(2024, 12, 5, tzinfo=UTC)
    assert windows.reference.end == datetime(2025, 1, 4, tzinfo=UTC)
    assert windows.target.end == datetime(2025, 2, 5, tzinfo=UTC)
    medium = windows.model_dump()
    medium.update(
        target_id="downloads_trailing_28d_at_91d_v1",
        reference=TimeWindow(
            start=datetime(2024, 12, 7, tzinfo=UTC),
            end=datetime(2025, 1, 4, tzinfo=UTC),
        ),
        target=TimeWindow(
            start=datetime(2025, 3, 10, tzinfo=UTC),
            end=datetime(2025, 4, 7, tzinfo=UTC),
        ),
    )
    assert TargetWindows.model_validate(medium).target.end.day == 7


@pytest.mark.parametrize("offset", [timedelta(days=1), timedelta(hours=1)])
def test_invalid_origin_rejected(offset: timedelta) -> None:
    """Decision origins cannot drift to another weekday or time of day."""
    payload = _forecast().windows.model_dump()
    payload["decision_at"] = _forecast().windows.decision_at + offset

    with pytest.raises(ValidationError, match="Monday"):
        TargetWindows.model_validate(payload)


def test_moved_anchor_rejected() -> None:
    """Missing data cannot justify moving the fixed observation boundary."""
    payload = _forecast().windows.model_dump()
    payload["observation_window_end"] = _forecast().windows.decision_at

    with pytest.raises(ValidationError, match="48-hour"):
        TargetWindows.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"reference_downloads": 999},
        {"predicted_downloads": None},
        {"predicted_growth_pct": 100},
        {"predicted_growth_pct": None},
        {"predicted_downloads": float("nan")},
        {"actual_downloads": 4500},
    ],
)
def test_inconsistent_or_leaked_forecast_rejected(changes: dict[str, object]) -> None:
    """Reject invalid eligibility, nonfinite estimates, and future-outcome leakage."""
    payload = _forecast().model_dump()
    payload.update(changes)

    with pytest.raises(ValidationError):
        ForecastResult.model_validate(payload)


def test_unvalidated_interval_is_absent() -> None:
    """Experimental quantiles cannot silently become a validated serving band."""
    forecast = _forecast("unvalidated-interval")
    payload = forecast.model_dump()
    payload["interval"] = {
        "interval_lower": 2500,
        "interval_upper": 4500,
        "nominal_coverage": 0.8,
        "interval_method": "chronological-cqr-v1",
        "calibration_id": "synthetic-calibration",
    }

    assert forecast.interval is None
    with pytest.raises(ValidationError, match="validated"):
        ForecastResult.model_validate(payload)
    payload["evidence_status"] = "validated"
    assert ForecastResult.model_validate(payload).interval is not None


def test_interval_order() -> None:
    """Reject crossing interval endpoints even with a supplied calibrator ID."""
    with pytest.raises(ValidationError, match="ordered"):
        PredictionInterval(
            interval_lower=2,
            interval_upper=1,
            nominal_coverage=0.8,
            interval_method="cqr",
            calibration_id="synthetic",
        )


def test_immature_label_cannot_be_revealed() -> None:
    """Preserve missing labels as null and reject them in the mature-outcome DTO."""
    label = LabelRow.model_validate_json(
        (FIXTURES / "immature-outcome.json").read_bytes()
    )

    assert label.actual_downloads is None
    with pytest.raises(ValidationError, match="complete"):
        MatureOutcome(
            forecast_id="synthetic",
            label=label,
            outcome_vintage="synthetic",
            first_complete_vintage=True,
        )


def test_outcome_availability_and_zero() -> None:
    """A genuine mature zero is valid; a premature availability timestamp is not."""
    outcome = MatureOutcome.model_validate_json(
        (FIXTURES / "mature-outcome.json").read_bytes()
    )
    payload = outcome.label.model_dump()
    payload["actual_downloads"] = 0

    assert LabelRow.model_validate(payload).actual_downloads == 0
    payload["available_at"] = outcome.label.windows.target.start
    with pytest.raises(ValidationError, match="completion"):
        LabelRow.model_validate(payload)
    payload["available_at"] = None
    with pytest.raises(ValidationError, match="timestamp"):
        LabelRow.model_validate(payload)


def test_contract_imports_do_not_load_services() -> None:
    """Public imports leave training, network, and database implementations unloaded."""
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        assert name.split(".")[0] not in {
            "catboost",
            "sklearn",
            "psycopg",
            "httpx",
            "sqlalchemy",
            "polars",
        }
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    with patch("builtins.__import__", side_effect=guarded_import):
        namespace = runpy.run_path(
            str(SCHEMAS.parents[2] / "oxhack2026/models/contracts.py")
        )

    assert "ForecastResult" in namespace


def test_contradictory_counts_rejected() -> None:
    """Coverage reports cannot claim more eligible candidates than were observed."""
    with pytest.raises(ValidationError, match="consistent"):
        CohortCounts(
            candidate_count=1,
            eligible_count=2,
            organization_count=1,
            origin_count=1,
            headline_origin_count=1,
        )


@pytest.mark.parametrize(
    ("name", "contract"),
    [
        ("feature-row", FeatureRow),
        ("feature-manifest", FeatureManifest),
        ("forecast-manifest", ForecastManifest),
        ("evidence", EvidenceItem),
        ("evaluation", EvaluationReport),
    ],
)
def test_handoff_fixtures(name: str, contract: type[Contract]) -> None:
    """Every non-forecast handoff fixture validates with its published type."""
    payload = (FIXTURES / f"{name}.json").read_bytes()

    artifact = contract.model_validate_json(payload)

    assert artifact.model_dump()


def test_feature_history_eligibility() -> None:
    """Inadequate history cannot be marked eligible for a learned forecast."""
    payload = orjson.loads((FIXTURES / "feature-row.json").read_bytes())
    payload["complete_history_days"] = 83

    with pytest.raises(ValidationError, match="84 complete"):
        FeatureRow.model_validate(payload)


def test_model_calibrator_pair() -> None:
    """An ID without the paired frozen calibration artifact is invalid."""
    payload = orjson.loads((FIXTURES / "forecast-manifest.json").read_bytes())["model"]
    payload["calibration_id"] = "synthetic-calibrator"

    with pytest.raises(ValidationError, match="together"):
        ModelReference.model_validate(payload)


@pytest.mark.parametrize("change", ["late", "scope"])
def test_forecast_manifest_integrity(change: str) -> None:
    """Late prospective recordings and mismatched ecosystem/model pairs fail."""
    payload = orjson.loads((FIXTURES / "forecast-manifest.json").read_bytes())
    if change == "late":
        payload["mode"] = "prospective"
    else:
        payload["ecosystem"] = "pypi"

    with pytest.raises(ValidationError):
        ForecastManifest.model_validate(payload)


def test_evidence_must_be_available_after_measurement() -> None:
    """An evidence item cannot claim availability before its window ends."""
    payload = orjson.loads((FIXTURES / "evidence.json").read_bytes())
    payload["available_at"] = payload["window"]["start"]

    with pytest.raises(ValidationError, match="window ends"):
        EvidenceItem.model_validate(payload)


def test_short_holdout_cannot_claim_superiority() -> None:
    """Exploratory or undersupported evidence cannot assert statistical superiority."""
    payload = orjson.loads((FIXTURES / "evaluation.json").read_bytes())
    payload["statistical_superiority"] = True

    with pytest.raises(ValidationError, match="eight horizon blocks"):
        EvaluationReport.model_validate(payload)
