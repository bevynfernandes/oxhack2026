"""Referential and effective-interval checks for C1 catalogues."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oxhack2026.catalog.schemas import CatalogSnapshot, ToolMapping


def _unique(values: Iterable[object], kind: str) -> None:
    seen: set[object] = set()
    for value in values:
        if value in seen:
            message = f"Duplicate {kind}: {value}"
            raise ValueError(message)
        seen.add(value)


def _nonoverlapping(groups: dict[tuple[str, str], list["ToolMapping"]]) -> None:
    for mappings in groups.values():
        previous_end: datetime | None = datetime.min.replace(tzinfo=UTC)
        for mapping in sorted(mappings, key=lambda item: item.valid_from):
            if previous_end is None or mapping.valid_from < previous_end:
                message = "Overlapping primary or organization representative mappings"
                raise ValueError(message)
            previous_end = mapping.valid_to


def validate_catalog(catalog: "CatalogSnapshot") -> None:
    """Validate foreign keys and nonoverlapping primary/representative mappings.

    Args:
        catalog: Parsed catalogue snapshot.
    Returns:
        None; validation succeeds without changing the snapshot.
    Raises:
        ValueError: For duplicates, unknown references, or conflicting intervals.
    """
    for records, field in (
        (catalog.organizations, "organization_id"),
        (catalog.tools, "tool_id"),
        (catalog.packages, "package_id"),
        (catalog.repositories, "repository_id"),
        (catalog.evidence, "evidence_id"),
        (catalog.mappings, "mapping_id"),
    ):
        _unique((getattr(record, field) for record in records), field)
    _unique(
        ((item.ecosystem, item.canonical_name) for item in catalog.packages), "package"
    )
    organizations = {item.organization_id for item in catalog.organizations}
    tools = {item.tool_id: item for item in catalog.tools}
    packages = {item.package_id: item for item in catalog.packages}
    repositories = {item.repository_id for item in catalog.repositories}
    evidence = {item.evidence_id for item in catalog.evidence}
    evidence_by_id = {item.evidence_id: item for item in catalog.evidence}
    if any(item.checked_at > catalog.recorded_at for item in catalog.evidence):
        message = "Catalogue cannot contain evidence collected after its recording"
        raise ValueError(message)
    if any(tool.organization_id not in organizations for tool in catalog.tools):
        message = "Tool references an unknown organization"
        raise ValueError(message)
    primary: dict[tuple[str, str], list[ToolMapping]] = defaultdict(list)
    representatives: dict[tuple[str, str], list[ToolMapping]] = defaultdict(list)
    for mapping in catalog.mappings:
        if (
            mapping.tool_id not in tools
            or mapping.package_id not in packages
            or not set(mapping.evidence_ids) <= evidence
            or (
                mapping.repository_id is not None
                and mapping.repository_id not in repositories
            )
        ):
            message = "Mapping contains an unknown foreign key or evidence reference"
            raise ValueError(message)
        ecosystem = packages[mapping.package_id].ecosystem
        if catalog.cohort_kind == "historical_eligibility":
            earliest = tools[mapping.tool_id].earliest_eligibility_at
            if (
                earliest is None
                or mapping.valid_from < earliest
                or any(
                    evidence_by_id[identifier].available_at > mapping.valid_from
                    for identifier in mapping.evidence_ids
                )
            ):
                message = (
                    "Historical membership requires evidence available at eligibility"
                )
                raise ValueError(message)
        if mapping.primary:
            primary[(mapping.tool_id, ecosystem)].append(mapping)
        if mapping.organization_representative:
            organization = tools[mapping.tool_id].organization_id
            representatives[(organization, ecosystem)].append(mapping)
    _nonoverlapping(primary)
    _nonoverlapping(representatives)
