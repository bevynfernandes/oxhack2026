"""Linear-time relational integrity for immutable company source tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oxhack2026.catalog.company import (
        CompanyEvent,
        CompanyMetricObservation,
        CompanyProfile,
        CompanyRelationship,
        CompanySourceSnapshot,
    )


def validate_company_snapshot(snapshot: CompanySourceSnapshot) -> None:
    """Check identities, source attribution, knowledge cutoffs and metric matrix.

    Args:
        snapshot: Parsed normalized source tables.
    Returns:
        None when all invariants hold.
    Raises:
        ValueError: For duplicate, foreign, future or incompatible source facts.
    """
    tables = (
        (snapshot.companies, "company_id"),
        (snapshot.relationships, "relationship_id"),
        (snapshot.definitions, "metric_id"),
        (snapshot.evidence, "evidence_id"),
        (snapshot.metrics, "observation_id"),
        (snapshot.events, "event_id"),
    )
    for rows, key in tables:
        if len({getattr(row, key) for row in rows}) != len(rows):
            message = f"Duplicate {key} in company snapshot"
            raise ValueError(message)
    companies = {row.company_id for row in snapshot.companies}
    definitions = {row.metric_id: row for row in snapshot.definitions}
    if not companies or not definitions:
        message = "Company source snapshot requires companies and metric definitions"
        raise ValueError(message)
    _validate_sources(snapshot)
    _validate_links(snapshot)
    _validate_facts(snapshot)
    _validate_metrics(snapshot)


def _validate_sources(snapshot: CompanySourceSnapshot) -> None:
    companies = {row.company_id for row in snapshot.companies}
    for source in snapshot.evidence:
        if (
            source.company_id not in companies
            or source.collected_at > snapshot.recorded_at
            or source.available_at > snapshot.as_of
        ):
            message = (
                "Source evidence has unknown company or future availability/collection"
            )
            raise ValueError(message)
        if (
            snapshot.mode != "historical_reconstruction"
            and source.collected_at > snapshot.as_of
        ):
            message = (
                "Only reconstructed snapshots can use later-collected source bytes"
            )
            raise ValueError(message)


def _validate_links(snapshot: CompanySourceSnapshot) -> None:
    companies = {row.company_id for row in snapshot.companies}
    evidence = {row.evidence_id: row for row in snapshot.evidence}
    linked: tuple[
        CompanyProfile | CompanyRelationship | CompanyMetricObservation | CompanyEvent,
        ...,
    ] = (
        *snapshot.companies,
        *snapshot.relationships,
        *snapshot.metrics,
        *snapshot.events,
    )
    for row in linked:
        if row.company_id not in companies:
            message = "Record refers to an unknown company"
            raise ValueError(message)
        for key in row.evidence_ids:
            source = evidence.get(key)
            if source is None or source.company_id != row.company_id:
                message = "Evidence is missing or belongs to a different company"
                raise ValueError(message)
    for company in snapshot.companies:
        if company.context_as_of > snapshot.as_of:
            message = "Company context follows the snapshot cutoff"
            raise ValueError(message)


def _validate_facts(snapshot: CompanySourceSnapshot) -> None:
    evidence = {row.evidence_id: row for row in snapshot.evidence}
    facts: tuple[CompanyMetricObservation | CompanyEvent, ...] = (
        *snapshot.metrics,
        *snapshot.events,
    )
    for fact in facts:
        if (
            fact.available_at > snapshot.as_of
            or fact.collected_at > snapshot.recorded_at
        ):
            message = "Fact timing exceeds snapshot bounds"
            raise ValueError(message)
        if (
            snapshot.mode != "historical_reconstruction"
            and fact.collected_at > snapshot.as_of
        ):
            message = "Later-collected facts require reconstruction mode"
            raise ValueError(message)
        if any(
            evidence[key].available_at > fact.available_at
            or evidence[key].collected_at > fact.collected_at
            for key in fact.evidence_ids
        ):
            message = "Fact precedes its supporting evidence"
            raise ValueError(message)


def _validate_metrics(snapshot: CompanySourceSnapshot) -> None:
    companies = {row.company_id for row in snapshot.companies}
    definitions = {row.metric_id: row for row in snapshot.definitions}
    selected: set[tuple[str, str]] = set()
    for row in snapshot.metrics:
        definition = definitions.get(row.metric_id)
        if definition is None or (
            row.value is not None and row.value.kind != definition.value_kind
        ):
            message = "Metric definition is missing or its value type disagrees"
            raise ValueError(message)
        if row.measurement_end > snapshot.as_of:
            message = "Metric measurement follows snapshot cutoff"
            raise ValueError(message)
        pair = (row.company_id, row.metric_id)
        if pair in selected:
            message = "Snapshot selects more than one vintage for a company metric"
            raise ValueError(message)
        selected.add(pair)
    if len(selected) != len(companies) * len(definitions):
        message = (
            "Every company/definition requires an observation or explicit missingness"
        )
        raise ValueError(message)
