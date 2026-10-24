"""Pure C1 presentation mapping; storage and revision selection remain upstream."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from oxhack2026.api import schemas as s
from oxhack2026.catalog.schemas import CatalogSnapshot
from oxhack2026.storage.contracts import (
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)


def _check_catalog(snapshot: CatalogSnapshot, batch: s.ForecastBatch) -> None:
    if (
        snapshot.catalog_version != batch.provenance.catalog_version
        or snapshot.mapping_version != batch.provenance.mapping_version
        or snapshot.synthetic != batch.provenance.synthetic
    ):
        message = "Catalogue does not match the batch's frozen identity versions"
        raise ValueError(message)
    if batch.mode == "prospective" and snapshot.recorded_at > batch.decision_at:
        message = "Prospective batches require a catalogue recorded before the cutoff"
        raise ValueError(message)


def map_catalog(snapshot: CatalogSnapshot, batch: s.ForecastBatch) -> s.Catalog:
    """Present verified, effective C1 package mappings for a frozen batch.

    Args:
        snapshot: Validated frozen catalogue, including actual verification dates.
        batch: Exact forecast scope and identity versions selected by the scout.
    Returns:
        Public identities with retrospective verification explicitly labelled.
        Contemporary cohort limitations remain visible rather than becoming a
        claim that today's catalogue was known at the historical decision.
    Raises:
        ValueError: Versions disagree or a prospective mapping uses later evidence.
    """
    _check_catalog(snapshot, batch)
    organizations = {item.organization_id: item for item in snapshot.organizations}
    tools = {item.tool_id: item for item in snapshot.tools}
    packages = {item.package_id: item for item in snapshot.packages}
    evidence = {item.evidence_id: item for item in snapshot.evidence}
    results: list[s.Tool] = []
    for mapping in snapshot.mappings:
        package = packages[mapping.package_id]
        if not (
            mapping.verified
            and mapping.primary
            and package.ecosystem == batch.ecosystem
            and mapping.valid_from <= batch.decision_at
            and (mapping.valid_to is None or batch.decision_at < mapping.valid_to)
        ):
            continue
        tool = tools[mapping.tool_id]
        organization = organizations[tool.organization_id]
        records = tuple(evidence[key] for key in mapping.evidence_ids)
        retrospective = any(
            record.checked_at > batch.decision_at
            or record.available_at > batch.decision_at
            for record in records
        )
        if retrospective and batch.mode == "prospective":
            message = "Prospective mapping evidence was inspected after the cutoff"
            raise ValueError(message)
        results.append(
            s.Tool(
                tool_id=tool.tool_id,
                tool_name=tool.name,
                organization_id=organization.organization_id,
                organization_name=organization.name,
                package_id=package.package_id,
                package_name=package.canonical_name,
                ecosystem=package.ecosystem,
                category=tool.category,
                representative=mapping.organization_representative,
                mapping_verification="retrospective"
                if retrospective
                else "before_cutoff",
                mapping_evidence=tuple(
                    s.Evidence(
                        evidence_id=record.evidence_id,
                        source=record.kind,
                        observed_at=record.checked_at,
                        available_at=record.available_at,
                        kind="mapping",
                        text=record.assertion,
                        url=record.url,
                    )
                    for record in records
                ),
            )
        )
    return s.Catalog(
        catalog_version=snapshot.catalog_version,
        mapping_version=snapshot.mapping_version,
        synthetic=snapshot.synthetic,
        tools=tuple(results),
        recorded_at=snapshot.recorded_at,
        cohort_kind=snapshot.cohort_kind,
        limitations=snapshot.limitations,
    )


def map_history(
    observations: Sequence[ObservationRevision],
    series: ObservationSeries,
    batch: s.ForecastBatch,
    tool_id: str,
) -> s.History:
    """Present a selected C1 history vintage without choosing newer revisions.

    Args:
        observations: Exact dataset revisions selected by the published read layer.
        series: Download series for the forecast's selected package and ecosystem.
        batch: Frozen dataset and temporal scope used by the original forecast.
        tool_id: Tool whose published forecast identifies the package.
    Returns:
        Chronological history retaining explicit zero, missing and partial counts.
    Raises:
        ValueError: Series identity, temporal bounds or prospective collection
            disagree; or multiple revisions make any daily value ambiguous.
    """
    forecast = next((row for row in batch.results if row.tool_id == tool_id), None)
    if (
        forecast is None
        or series.entity_id != forecast.package_id
        or series.ecosystem != batch.ecosystem
        or series.unit != "downloads"
        or series.source != batch.ecosystem
    ):
        message = "History series does not match the forecast's frozen package"
        raise ValueError(message)
    seen: set[datetime] = set()
    points: list[s.HistoryPoint] = []
    for row in observations:
        if (
            row.series_id != series.series_id
            or row.window.end > batch.observation_window_end
            or row.available_at > batch.decision_at
            or (
                batch.mode == "prospective"
                and row.first_collected_at > batch.decision_at
            )
            or row.window.start in seen
        ):
            message = "History contains future, mismatched or ambiguous revisions"
            raise ValueError(message)
        seen.add(row.window.start)
        points.append(
            s.HistoryPoint(
                window=s.Window(start=row.window.start, end=row.window.end),
                downloads=row.value,
                available_at=row.available_at,
                completeness=row.completeness,
                revision_id=row.revision_id,
            )
        )
    points.sort(key=lambda item: item.window.start)
    return s.History(
        batch_id=batch.batch_id,
        tool_id=tool_id,
        dataset_version=batch.provenance.dataset_version,
        observation_window_end=batch.observation_window_end,
        points=tuple(points),
    )


@dataclass(frozen=True)
class SourcePresentation:
    """Operational facts supplied by the data owner, not inferred from coverage.

    Attributes:
        stale: Source freshness assessment under its configured policy.
        revisions: Published revision count for this report's scope.
        mapping_status: Public catalogue-verification status.
        connector_status: Safe public connector state, without private exceptions.
    """

    stale: bool
    revisions: int
    mapping_status: str
    connector_status: Literal["ready", "degraded", "unavailable"]


def map_source_health(
    series: ObservationSeries,
    coverage: SourceCoverage,
    presentation: SourcePresentation,
) -> s.SourceHealth:
    """Present C1 daily coverage with explicit operational facts and unknown dates.

    Args:
        series: Source identity for the coverage record.
        coverage: Published complete/partial/missing daily counts.
        presentation: Model-independent health facts supplied by the data owner.
    Returns:
        Public health preserving unknown last-success time rather than inventing it.
    Raises:
        ValueError: Coverage belongs to another series or public fields are invalid.
    """
    if coverage.series_id != series.series_id:
        message = "Coverage does not belong to the selected source series"
        raise ValueError(message)
    return s.SourceHealth(
        source=series.source,
        ecosystem=series.ecosystem,
        freshness=s.Freshness(
            as_of=coverage.last_success_at,
            stale=presentation.stale,
            completeness="unavailable"
            if coverage.status == "missing"
            else coverage.status,
            reasons=coverage.reasons,
        ),
        missing_partitions=coverage.missing_days,
        revisions=presentation.revisions,
        mapping_status=presentation.mapping_status,
        connector_status=presentation.connector_status,
    )
