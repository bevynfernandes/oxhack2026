"""C2-to-C3 presentation mapping without storage access or numerical formulas."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from oxhack2026.api import schemas as s
from oxhack2026.evaluation.contracts import EvidenceItem
from oxhack2026.models.contracts import ForecastManifest, ForecastResult


@dataclass(frozen=True)
class BatchPresentation:
    """Version and source-quality metadata supplied by the publication adapter.

    Attributes:
        catalog_version: Catalogue snapshot used by the frozen batch.
        evidence_version: Version of the published evidence bundle.
        freshness: Explicit source assessments keyed by tool ID, not inferred quality.
        evaluation_id: Published evaluation reference, or None when unavailable.
    """

    catalog_version: str
    evidence_version: str
    freshness: Mapping[str, s.Freshness]
    evaluation_id: str | None


def map_evidence(item: EvidenceItem) -> tuple[s.Evidence, ...]:
    """Split C2 measured text, interpretation and limitations into public records.

    Args:
        item: Validated model-owner evidence with dated source observations.
    Returns:
        Escapable text records retaining original source and availability metadata.
    Raises:
        ValueError: Public identifiers or source URLs are invalid or unsafe.
    """
    measured = s.Evidence(
        evidence_id=item.evidence_id,
        source=item.source,
        observed_at=item.window.end,
        available_at=item.available_at,
        kind="measurement",
        text=item.measured_change,
        url=item.source_url,
    )
    records = [measured]
    if item.predictive_interpretation is not None:
        records.append(
            s.Evidence(
                **{
                    **measured.model_dump(),
                    "evidence_id": f"{item.evidence_id}-interpretation",
                    "kind": "interpretation",
                    "text": item.predictive_interpretation,
                }
            )
        )
    for index, limitation in enumerate(item.limitations):
        records.append(
            s.Evidence(
                **{
                    **measured.model_dump(),
                    "evidence_id": f"{item.evidence_id}-limitation-{index}",
                    "kind": "limitation",
                    "text": limitation,
                }
            )
        )
    return tuple(records)


def _require_scope(row: ForecastResult, manifest: ForecastManifest) -> None:
    if (
        row.batch_id != manifest.batch_id
        or row.windows != manifest.windows
        or row.identity.ecosystem != manifest.ecosystem
        or row.identity.dataset_version != manifest.dataset_version
        or row.identity.mapping_version != manifest.mapping_version
        or row.feature_schema_version != manifest.feature_schema_version
        or row.model_id != manifest.model.model_id
        or row.experiment_id != manifest.model.experiment_id
        or row.mode != manifest.mode
    ):
        message = "Forecast row does not match its frozen manifest"
        raise ValueError(message)


def _map_row(
    row: ForecastResult,
    evidence: Mapping[str, EvidenceItem],
    freshness: s.Freshness,
) -> s.Forecast:
    records: list[s.Evidence] = []
    for evidence_id in row.evidence_ids:
        item = evidence.get(evidence_id)
        if item is None or item.tool_id != row.identity.tool_id:
            message = "Forecast evidence is absent or belongs to another tool"
            raise ValueError(message)
        records.extend(map_evidence(item))
    if freshness.stale != row.stale:
        message = "Published freshness disagrees with the forecast"
        raise ValueError(message)
    interval = row.interval
    return s.Forecast(
        forecast_id=row.forecast_id,
        feature_row_id=row.feature_row_id,
        tool_id=row.identity.tool_id,
        organization_id=row.identity.organization_id,
        package_id=row.identity.package_id,
        model_id=row.model_id,
        availability="available" if row.forecast_status == "ready" else "unavailable",
        reference_downloads=row.reference_downloads,
        predicted_downloads=row.predicted_downloads,
        predicted_growth_pct=row.predicted_growth_pct,
        estimate_kind=row.estimate_kind,
        ranking_eligible=row.ranking_eligible,
        reasons=row.reason_codes,
        interval=s.Interval(
            lower=interval.interval_lower,
            upper=interval.interval_upper,
            nominal_coverage=interval.nominal_coverage,
            method=interval.interval_method,
            calibration_id=interval.calibration_id,
            status="validated",
        )
        if interval is not None
        else None,
        baseline=s.Baseline(
            model_id=row.baseline_model_id,
            predicted_downloads=row.baseline_predicted_downloads,
        )
        if row.baseline_predicted_downloads is not None
        else None,
        evidence_status=row.evidence_status,
        evidence=tuple(records),
        freshness=freshness,
        data_age_hours=row.data_age_hours,
    )


def map_forecast_batch(
    manifest: ForecastManifest,
    rows: Sequence[ForecastResult],
    evidence: Sequence[EvidenceItem],
    presentation: BatchPresentation,
) -> s.ForecastBatch:
    """Map validated C2 artifacts into a pre-reveal C3 batch without inference.

    Args:
        manifest: Frozen forecast manifest, whose paths stay private.
        rows: Validated forecasts matching every manifest scope/version field.
        evidence: The evidence bundle referenced by those rows.
        presentation: Explicit catalogue, evidence and quality publication metadata.
    Returns:
        A public batch containing only saved predictions and permitted evidence.
    Raises:
        ValueError: Artifacts disagree, evidence/freshness is absent, or public
            fields are unsafe. Storage adapters translate this to HTTP 503.
    """
    evidence_by_id = {item.evidence_id: item for item in evidence}
    if len(evidence_by_id) != len(evidence):
        message = "Evidence identifiers must be unique"
        raise ValueError(message)
    results: list[s.Forecast] = []
    for row in rows:
        _require_scope(row, manifest)
        freshness = presentation.freshness.get(row.identity.tool_id)
        if freshness is None:
            message = "Explicit source freshness is required for each tool"
            raise ValueError(message)
        results.append(_map_row(row, evidence_by_id, freshness))
    windows = manifest.windows
    return s.ForecastBatch(
        batch_id=manifest.batch_id,
        ecosystem=manifest.ecosystem,
        target_id=windows.target_id,
        target_definition_version=windows.definition_version,
        decision_at=windows.decision_at,
        observation_window_end=windows.observation_window_end,
        reference_window=s.Window(
            start=windows.reference.start, end=windows.reference.end
        ),
        target_window=s.Window(start=windows.target.start, end=windows.target.end),
        mode=manifest.mode,
        provenance=s.Provenance(
            dataset_version=manifest.dataset_version,
            catalog_version=presentation.catalog_version,
            mapping_version=manifest.mapping_version,
            feature_schema_version=manifest.feature_schema_version,
            evidence_version=presentation.evidence_version,
            experiment_id=manifest.model.experiment_id,
            synthetic=manifest.synthetic,
            limitations=manifest.limitations,
        ),
        results=tuple(results),
        evaluation_id=presentation.evaluation_id,
    )
