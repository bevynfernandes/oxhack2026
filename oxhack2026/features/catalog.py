"""Resolve verified C1 mappings before constructing numerical feature requests."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

import orjson

from oxhack2026.catalog.schemas import CatalogSnapshot
from oxhack2026.features.builders import FEATURE_SCHEMA_VERSION, FeatureRequest
from oxhack2026.features.definitions import target_windows
from oxhack2026.models.contracts import (
    Ecosystem,
    ForecastMode,
    RowIdentity,
    TargetId,
    TargetWindows,
    TimeWindow,
)
from oxhack2026.storage.contracts import ObservationSeries


@dataclass(frozen=True)
class RequestScope:
    """One immutable dataset/ecosystem/target/origin and availability mode."""

    dataset_version: str
    ecosystem: Ecosystem
    target_id: TargetId
    decision_at: datetime
    mode: ForecastMode


@dataclass(frozen=True)
class CatalogRequests:
    """Resolved requests, frozen organization representatives and cohort caveats."""

    requests: tuple[FeatureRequest, ...]
    representatives: tuple[tuple[str, str], ...]
    limitations: tuple[str, ...]


def _series_index(
    series: Sequence[ObservationSeries], ecosystem: Ecosystem
) -> dict[str, ObservationSeries]:
    indexed: dict[str, ObservationSeries] = {}
    for item in series:
        if (
            item.ecosystem != ecosystem
            or item.source != ecosystem
            or item.entity_kind != "package"
            or item.unit != "downloads"
        ):
            continue
        if item.entity_id in indexed:
            message = "Package has ambiguous download series in the frozen index"
            raise ValueError(message)
        indexed[item.entity_id] = item
    return indexed


def _mapping_time(
    catalog: CatalogSnapshot, scope: RequestScope, contemporary: bool
) -> datetime:
    if not scope.dataset_version or scope.mode not in {"reconstructed", "prospective"}:
        message = "Request scope requires a dataset version and supported mode"
        raise ValueError(message)
    if scope.mode == "prospective" and catalog.recorded_at > scope.decision_at:
        message = "Prospective catalogue must be recorded by the decision cutoff"
        raise ValueError(message)
    if contemporary and (
        scope.mode != "reconstructed" or catalog.cohort_kind != "contemporary_catalogue"
    ):
        message = (
            "Contemporary mapping selection requires reconstructed current cohorts"
        )
        raise ValueError(message)
    return catalog.recorded_at if contemporary else scope.decision_at


def catalog_requests(
    catalog: CatalogSnapshot,
    series: Sequence[ObservationSeries],
    scope: RequestScope,
    *,
    contemporary: bool = False,
) -> CatalogRequests:
    """Select effective, verified primary packages independently of future outcomes.

    Args:
        catalog: Frozen validated C1 catalogue with dated mapping evidence.
        series: Frozen C1 series index; exactly one download series per package.
        scope: Requested dataset, origin, ecosystem, target and collection mode.
        contemporary: Explicitly use mappings effective at catalogue recording
            for contemporary reconstructed cohorts. Never backdate their evidence.
    Returns:
        Deterministically ordered company-backed tool requests and the catalogue's
        preselected organization representatives. Contemporary reconstructed
        cohorts retain explicit survivorship/retrospective verification caveats.
        A missing series fails instead of silently dropping a mapped company.
    Raises:
        ValueError: Scope, series identity or prospective catalogue evidence is
            invalid, ambiguous or newer than the decision cutoff.
    """
    boundaries = target_windows(scope.decision_at, scope.target_id)
    mapping_at = _mapping_time(catalog, scope, contemporary)
    indexed = _series_index(series, scope.ecosystem)
    organizations = {row.organization_id: row for row in catalog.organizations}
    tools = {row.tool_id: row for row in catalog.tools}
    packages = {row.package_id: row for row in catalog.packages}
    evidence = {row.evidence_id: row for row in catalog.evidence}
    windows = TargetWindows(
        target_id=scope.target_id,
        decision_at=scope.decision_at,
        observation_window_end=boundaries.observation_end,
        reference=TimeWindow(
            start=boundaries.reference_start, end=boundaries.reference_end
        ),
        target=TimeWindow(start=boundaries.target_start, end=boundaries.target_end),
    )
    requests: list[FeatureRequest] = []
    representatives: list[tuple[str, str]] = []
    retrospective = False
    for mapping in sorted(catalog.mappings, key=lambda row: row.mapping_id):
        tool = tools[mapping.tool_id]
        package = packages[mapping.package_id]
        if not (
            mapping.verified
            and mapping.primary
            and package.ecosystem == scope.ecosystem
            and organizations[tool.organization_id].kind == "company_backed"
            and mapping.valid_from <= mapping_at
            and (mapping.valid_to is None or mapping_at < mapping.valid_to)
            and (
                tool.earliest_eligibility_at is None
                or tool.earliest_eligibility_at <= scope.decision_at
            )
        ):
            continue
        later_evidence = any(
            evidence[key].available_at > scope.decision_at
            or evidence[key].checked_at > scope.decision_at
            for key in mapping.evidence_ids
        )
        if later_evidence and scope.mode == "prospective":
            message = "Prospective mapping evidence was inspected after the cutoff"
            raise ValueError(message)
        retrospective |= later_evidence
        selected_series = indexed.get(package.package_id)
        if selected_series is None:
            message = "Verified primary package is absent from the frozen series index"
            raise ValueError(message)
        identity = RowIdentity(
            tool_id=tool.tool_id,
            organization_id=tool.organization_id,
            package_id=package.package_id,
            ecosystem=scope.ecosystem,
            dataset_version=scope.dataset_version,
            mapping_version=catalog.mapping_version,
        )
        row_hash = sha256(
            orjson.dumps(
                {
                    "identity": identity.model_dump(mode="json"),
                    "target": scope.target_id,
                    "decision_at": scope.decision_at,
                    "mode": scope.mode,
                    "feature_schema_version": FEATURE_SCHEMA_VERSION,
                },
                option=orjson.OPT_SORT_KEYS,
            )
        ).hexdigest()
        requests.append(
            FeatureRequest(
                feature_row_id=f"feature-{row_hash}",
                identity=identity,
                windows=windows,
                series=selected_series,
            )
        )
        if mapping.organization_representative:
            representatives.append((tool.organization_id, tool.tool_id))
    limitations = list(catalog.limitations)
    if catalog.cohort_kind == "contemporary_catalogue":
        limitations.append(
            "Contemporary catalogue: reconstructed cohorts may have survivorship bias."
        )
    if contemporary:
        limitations.append(
            "Mappings selected at catalogue recording; "
            "membership was not historically known."
        )
    if retrospective:
        limitations.append(
            "Mapping verification occurred after this reconstructed decision cutoff."
        )
    return CatalogRequests(tuple(requests), tuple(representatives), tuple(limitations))
