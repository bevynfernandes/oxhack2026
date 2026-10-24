"""C3 consumes the merged C2 examples without changing their numerical values."""

from datetime import UTC, datetime
from pathlib import Path

import orjson
import pytest

from oxhack2026.api.model_mapping import (
    BatchPresentation,
    map_evidence,
    map_forecast_batch,
)
from oxhack2026.api.schemas import Freshness
from oxhack2026.evaluation.contracts import EvidenceItem
from oxhack2026.models.contracts import ForecastManifest, ForecastResult


@pytest.fixture
def manifest() -> ForecastManifest:
    """Return Dev 2's saved synthetic manifest, including private artifact paths."""
    return ForecastManifest.model_validate(
        orjson.loads(Path("tests/fixtures/models/forecast-manifest.json").read_bytes())
    )


@pytest.fixture
def row() -> ForecastResult:
    """Return Dev 2's ready prediction with its authoritative saved growth."""
    return ForecastResult.model_validate(
        orjson.loads(Path("tests/fixtures/models/ready.json").read_bytes())
    )


@pytest.fixture
def evidence() -> EvidenceItem:
    """Return Dev 2's bounded synthetic measured evidence."""
    return EvidenceItem.model_validate(
        orjson.loads(Path("tests/fixtures/models/evidence.json").read_bytes())
    )


@pytest.fixture
def presentation() -> BatchPresentation:
    """Return explicit synthetic source quality; do not infer it from model status."""
    return BatchPresentation(
        catalog_version="synthetic-catalog-v1",
        evidence_version="synthetic-evidence-v1",
        freshness={
            "synthetic-tool": Freshness(
                as_of=datetime(2025, 1, 4, tzinfo=UTC),
                stale=False,
                completeness="complete",
            )
        },
        evaluation_id="synthetic-evaluation-v1",
    )


def test_c2_to_c3_mapping(
    manifest: ForecastManifest,
    row: ForecastResult,
    evidence: EvidenceItem,
    presentation: BatchPresentation,
) -> None:
    """Preserve saved values and evidence while excluding private paths and truth."""
    batch = map_forecast_batch(manifest, (row,), (evidence,), presentation)
    public = batch.results[0]
    assert public.predicted_downloads == row.predicted_downloads
    assert public.predicted_growth_pct == row.predicted_growth_pct
    assert public.feature_row_id == row.feature_row_id
    assert public.data_age_hours == row.data_age_hours
    assert public.baseline is not None
    assert public.baseline.predicted_downloads == row.baseline_predicted_downloads
    assert [record.kind for record in public.evidence] == [
        "measurement",
        "interpretation",
        "limitation",
    ]
    assert "actual_downloads" not in batch.model_dump_json()
    assert "fixture.json" not in batch.model_dump_json()
    assert batch.provenance.synthetic is True


@pytest.mark.parametrize(
    "change",
    [
        {"batch_id": "different"},
        {"model_id": "different"},
        {"mode": "prospective"},
        {"feature_schema_version": "different"},
    ],
)
def test_mismatched_forecast(
    manifest: ForecastManifest,
    row: ForecastResult,
    evidence: EvidenceItem,
    presentation: BatchPresentation,
    change: dict[str, str],
) -> None:
    """Never bind a different forecast to the requested immutable manifest."""
    with pytest.raises(ValueError, match="frozen manifest"):
        map_forecast_batch(
            manifest, (row.model_copy(update=change),), (evidence,), presentation
        )


def test_missing_and_wrong_evidence(
    manifest: ForecastManifest,
    row: ForecastResult,
    evidence: EvidenceItem,
    presentation: BatchPresentation,
) -> None:
    """Absent, duplicate and wrong-tool evidence fail the publication boundary."""
    for records in (
        (),
        (evidence, evidence),
        (evidence.model_copy(update={"tool_id": "other"}),),
    ):
        with pytest.raises(ValueError):
            map_forecast_batch(manifest, (row,), records, presentation)


def test_future_evidence(
    manifest: ForecastManifest,
    row: ForecastResult,
    evidence: EvidenceItem,
    presentation: BatchPresentation,
) -> None:
    """A later-collected observation cannot leak into the original evidence payload."""
    future = evidence.model_copy(
        update={"available_at": datetime(2025, 1, 7, tzinfo=UTC)}
    )
    with pytest.raises(ValueError, match="forecast boundary"):
        map_forecast_batch(manifest, (row,), (future,), presentation)


def test_validated_status_is_not_a_superiority_claim(
    manifest: ForecastManifest,
    row: ForecastResult,
    evidence: EvidenceItem,
    presentation: BatchPresentation,
) -> None:
    """C2 validated status is preserved rather than escalated to statistical claims."""
    result = map_forecast_batch(
        manifest,
        (row.model_copy(update={"evidence_status": "validated"}),),
        (evidence,),
        presentation,
    )
    assert result.results[0].evidence_status == "validated"
    assert "superiority" not in result.model_dump_json()


def test_unsafe_evidence_url(evidence: EvidenceItem) -> None:
    """Do not publish credentials embedded in an upstream source link."""
    with pytest.raises(ValueError):
        map_evidence(
            evidence.model_copy(update={"source_url": "https://example.com?key=secret"})
        )


def test_source_quality_required(
    manifest: ForecastManifest, row: ForecastResult, evidence: EvidenceItem
) -> None:
    """Missing source quality must not become an assumed complete history."""
    presentation = BatchPresentation(
        "synthetic-catalog", "synthetic-evidence", {}, None
    )
    with pytest.raises(ValueError, match="freshness"):
        map_forecast_batch(manifest, (row,), (evidence,), presentation)
