"""C1 public presentation preserves real verification and collection timestamps."""

from datetime import UTC, datetime
from pathlib import Path

import orjson
import pytest

from oxhack2026.api import schemas as s
from oxhack2026.api.data_mapping import (
    SourcePresentation,
    map_catalog,
    map_history,
    map_source_health,
)
from oxhack2026.api.model_mapping import BatchPresentation, map_forecast_batch
from oxhack2026.catalog.schemas import CatalogSnapshot
from oxhack2026.evaluation.contracts import EvidenceItem
from oxhack2026.models.contracts import ForecastManifest, ForecastResult
from oxhack2026.storage.contracts import (
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)


@pytest.fixture
def batch() -> s.ForecastBatch:
    """Return C3 from the same C2 fixture identities used by the C1 examples."""
    manifest = ForecastManifest.model_validate_json(
        Path("tests/fixtures/models/forecast-manifest.json").read_bytes()
    )
    row = ForecastResult.model_validate_json(
        Path("tests/fixtures/models/ready.json").read_bytes()
    )
    evidence = EvidenceItem.model_validate_json(
        Path("tests/fixtures/models/evidence.json").read_bytes()
    )
    presentation = BatchPresentation(
        "synthetic-catalog-v1",
        "synthetic-evidence-v1",
        {
            row.identity.tool_id: s.Freshness(
                as_of=manifest.windows.observation_window_end,
                stale=False,
                completeness="complete",
            )
        },
        None,
    )
    return map_forecast_batch(manifest, (row,), (evidence,), presentation)


@pytest.fixture
def catalog() -> CatalogSnapshot:
    """Return C1's contemporary catalogue with actual retrospective inspection."""
    return CatalogSnapshot.model_validate_json(
        Path("tests/fixtures/data/catalog.json").read_bytes()
    )


@pytest.fixture
def series() -> ObservationSeries:
    """Return C1's exact npm package series identity."""
    return ObservationSeries.model_validate(
        orjson.loads(Path("tests/fixtures/data/series.json").read_bytes())["series"][0]
    )


@pytest.fixture
def states() -> dict[str, ObservationRevision]:
    """Return the saved zero/missing/late/revised observation states."""
    payload = orjson.loads(
        Path("tests/fixtures/data/observation-states.json").read_bytes()
    )
    return {
        name: ObservationRevision.model_validate(row)
        for name, row in payload["states"].items()
    }


def test_retrospective_mapping_is_explicit(
    catalog: CatalogSnapshot, batch: s.ForecastBatch
) -> None:
    """Preserve actual verification dates in a labelled reconstruction."""
    result = map_catalog(catalog, batch)
    assert result.tools[0].mapping_verification == "retrospective"
    assert (
        result.tools[0].mapping_evidence[0].observed_at
        == catalog.evidence[0].checked_at
    )
    assert result.recorded_at == catalog.recorded_at
    assert result.cohort_kind == "contemporary_catalogue"
    assert result.limitations == catalog.limitations
    with pytest.raises(ValueError, match="Prospective"):
        map_catalog(catalog, batch.model_copy(update={"mode": "prospective"}))


def test_changed_mapping_is_not_substituted(
    catalog: CatalogSnapshot, batch: s.ForecastBatch
) -> None:
    """New catalogue/mapping versions cannot rewrite the saved batch's identities."""
    with pytest.raises(ValueError, match="frozen identity"):
        map_catalog(
            catalog.model_copy(update={"mapping_version": "new-mapping"}), batch
        )
    ended = catalog.mappings[0].model_copy(update={"valid_to": batch.decision_at})
    assert (
        map_catalog(catalog.model_copy(update={"mappings": (ended,)}), batch).tools
        == ()
    )


@pytest.mark.parametrize("state", ["complete", "zero", "missing", "partial", "vendor"])
def test_history_preserves_source_state(
    batch: s.ForecastBatch,
    series: ObservationSeries,
    states: dict[str, ObservationRevision],
    state: str,
) -> None:
    """Preserve missing and partial counts separately from complete zero."""
    row = states[state]
    history = map_history((row,), series, batch, "synthetic-tool")
    assert history.points[0].downloads == row.value
    assert history.points[0].completeness == row.completeness
    assert history.points[0].revision_id == row.revision_id


def test_history_rejects_ambiguity_and_late_collection(
    batch: s.ForecastBatch,
    series: ObservationSeries,
    states: dict[str, ObservationRevision],
) -> None:
    """Reject duplicate vintages and late prospective observations."""
    for records in ((states["complete"], states["revised"]), (states["late"],)):
        with pytest.raises(ValueError, match="ambiguous revisions"):
            map_history(records, series, batch, "synthetic-tool")
    with pytest.raises(ValueError, match="ambiguous revisions"):
        map_history(
            (states["complete"],),
            series,
            batch.model_copy(update={"mode": "prospective"}),
            "synthetic-tool",
        )
    with pytest.raises(ValueError, match="frozen package"):
        map_history(
            (),
            series.model_copy(update={"entity_id": "other-package"}),
            batch,
            "synthetic-tool",
        )


def test_missing_health_time_is_not_invented(series: ObservationSeries) -> None:
    """Absent last-success time remains null; source facts are supplied explicitly."""
    coverage = SourceCoverage.model_validate(
        orjson.loads(Path("tests/fixtures/data/coverage.json").read_bytes())[
            "coverage"
        ][0]
    ).model_copy(update={"last_success_at": None})
    facts = SourcePresentation(True, 2, "verified", "degraded")
    result = map_source_health(series, coverage, facts)
    assert result.freshness.as_of is None
    assert result.missing_partitions == coverage.missing_days
    assert result.revisions == 2
    with pytest.raises(ValueError, match="selected source"):
        map_source_health(
            series.model_copy(update={"series_id": "other"}), coverage, facts
        )


def test_pre_cutoff_verification_can_be_presented(
    catalog: CatalogSnapshot, batch: s.ForecastBatch
) -> None:
    """Distinguish pre-cutoff verification from retrospective inspection."""
    evidence = catalog.evidence[0].model_copy(
        update={
            "checked_at": datetime(2024, 1, 1, tzinfo=UTC),
            "available_at": datetime(2024, 1, 1, tzinfo=UTC),
        }
    )
    result = map_catalog(catalog.model_copy(update={"evidence": (evidence,)}), batch)
    assert result.tools[0].mapping_verification == "before_cutoff"
