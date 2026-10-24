"""Deterministic public company assessments from exact, validated C1 snapshots."""

from collections import defaultdict
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta
from hashlib import sha256

import orjson

from oxhack2026.catalog.company import (
    CompanyEvent,
    CompanyMetricObservation,
    CompanyRelationship,
    CompanySourceSnapshot,
    MetricDefinition,
    MetricFamily,
    SourceEvidence,
)
from oxhack2026.features.company_outcomes import (
    COMPANY_OUTCOME_IDS,
    CompanyOutcomeId,
    company_horizon_end,
)
from oxhack2026.features.definitions import require_utc
from oxhack2026.models.company_assessments import (
    AssessmentStatement,
    CompanyAssessment,
    CompanyOutcomeAssessment,
)
from oxhack2026.storage.company import resolve_family

POLICY_VERSION = "company-public-evidence-v1"
_FAMILIES: dict[CompanyOutcomeId, frozenset[MetricFamily]] = {
    "operating_growth_24m_v1": frozenset({"traction", "execution", "commercial"}),
    "commercial_viability_12m_v1": frozenset({"commercial"}),
    "financing_or_acquisition_24m_v1": frozenset({"market_financing"}),
}
_EVENT_OUTCOMES: dict[str, frozenset[CompanyOutcomeId]] = {
    "release": frozenset({"operating_growth_24m_v1"}),
    "product_retirement": frozenset({"operating_growth_24m_v1"}),
    "company_shutdown": frozenset(
        {
            "operating_growth_24m_v1",
            "commercial_viability_12m_v1",
        }
    ),
    "funding": frozenset({"financing_or_acquisition_24m_v1"}),
    "acquisition": frozenset({"financing_or_acquisition_24m_v1"}),
    "ownership_change": frozenset({"financing_or_acquisition_24m_v1"}),
}
_SUMMARIES: dict[CompanyOutcomeId, str] = {
    "operating_growth_24m_v1": (
        "Current observations are available; future operation and growth "
        "have no validated prediction."
    ),
    "commercial_viability_12m_v1": (
        "Commercial observations are available; no validated cash-flow "
        "forecast is available."
    ),
    "financing_or_acquisition_24m_v1": (
        "Market or financing observations are available; future financing "
        "and acquisition have no validated prediction."
    ),
}


def build_company_assessments(
    snapshot: CompanySourceSnapshot, first_recorded_at: datetime
) -> tuple[CompanyAssessment, ...]:
    """Assess every company using verified public facts, without predicting success.

    Args:
        snapshot: Exact fully validated C1 publication with verified raw bytes.
            This function performs no vendor/storage reads and does not verify raw
            hashes itself. Definitions, identities and source timing stay C1-owned.
        first_recorded_at: Actual UTC recording time, pinned for repeatable retries;
            cannot precede the source publication.
    Returns:
        Deterministically ordered evidence-only/unavailable profiles at the frozen
        source cutoff. Each preserves all three outcomes, exact source/policy and
        synthetic identity, dated public facts and explicit metric gaps. Restricted,
        unverified, disputed and stale values never appear in narrative statements.
        No future labels or probabilities are computed. All output is recorded
        after its cutoff and therefore labelled reconstructed.
    Raises:
        ValueError: Recording time is invalid or a company identity lacks verified
            public evidence. Source validation failures propagate from C1.
    """
    require_utc(first_recorded_at)
    if first_recorded_at < snapshot.recorded_at:
        message = "Assessment recording cannot precede its source publication"
        raise ValueError(message)
    definitions = {row.metric_id: row for row in snapshot.definitions}
    return tuple(
        _assess_company(view, definitions, first_recorded_at)
        for view in _company_views(snapshot)
    )


def _company_views(snapshot: CompanySourceSnapshot) -> Iterator[CompanySourceSnapshot]:
    relationships: dict[str, list[CompanyRelationship]] = defaultdict(list)
    evidence: dict[str, list[SourceEvidence]] = defaultdict(list)
    metrics: dict[str, list[CompanyMetricObservation]] = defaultdict(list)
    events: dict[str, list[CompanyEvent]] = defaultdict(list)
    for relationship in snapshot.relationships:
        relationships[relationship.company_id].append(relationship)
    for source in snapshot.evidence:
        evidence[source.company_id].append(source)
    for metric in snapshot.metrics:
        metrics[metric.company_id].append(metric)
    for event in snapshot.events:
        events[event.company_id].append(event)
    for company in sorted(snapshot.companies, key=lambda row: row.company_id):
        # Ephemeral views share validated facts; they are never source publications.
        yield snapshot.model_copy(
            update={
                "companies": (company,),
                "relationships": tuple(relationships[company.company_id]),
                "evidence": tuple(evidence[company.company_id]),
                "metrics": tuple(metrics[company.company_id]),
                "events": tuple(events[company.company_id]),
            }
        )


def _source_reason(
    evidence_ids: tuple[str, ...], evidence: Mapping[str, SourceEvidence]
) -> str | None:
    if any(evidence[key].access != "public" for key in evidence_ids):
        return "restricted evidence"
    if any(evidence[key].review_state != "verified" for key in evidence_ids):
        return "unverified or disputed evidence"
    return None


def _metric_statement(
    row: CompanyMetricObservation,
    definition: MetricDefinition,
    evidence: Mapping[str, SourceEvidence],
    as_of: datetime,
) -> AssessmentStatement | None:
    if row.state == "not_applicable":
        return None
    reason = (
        row.state
        if row.state != "observed"
        else _source_reason(row.evidence_ids, evidence)
    )
    if reason is None and as_of - row.measurement_end > timedelta(
        days=definition.maximum_age_days
    ):
        reason = "stale measurement"
    if reason is not None:
        return AssessmentStatement(
            statement_id=f"metric-{row.observation_id}",
            role="evidence_gap",
            text=f"{definition.label}: no usable public measurement ({reason}).",
            metric_observation_ids=(row.observation_id,),
            missing_metric_ids=(row.metric_id,),
        )
    if row.value is None:
        message = "An observed source metric requires a value"
        raise ValueError(message)
    if row.value.kind == "boolean":
        value = "yes" if row.value.value else "no"
    else:
        value = format(row.value.value, ",f" if row.value.kind == "decimal" else ",d")
    unit = definition.unit
    if definition.currency is not None and definition.currency != unit:
        unit = f"{unit} ({definition.currency})"
    scope = (
        ""
        if definition.scope == "company"
        else f" {definition.scope.capitalize()} measure."
    )
    return AssessmentStatement(
        statement_id=f"metric-{row.observation_id}",
        role="observation",
        text=f"{definition.label}: {value} {unit}.{scope}",
        evidence_ids=tuple(sorted(set(row.evidence_ids))),
        metric_observation_ids=(row.observation_id,),
    )


def _event_statement(
    row: CompanyEvent, evidence: Mapping[str, SourceEvidence], as_of: datetime
) -> AssessmentStatement | None:
    if _source_reason(row.evidence_ids, evidence) is not None:
        return None
    when = "; event date unknown"
    if row.occurred_on is not None:
        date_label = "event date"
        if row.stage == "announced" and row.occurred_on > as_of.date():
            date_label = "expected event date"
        when = f"; {date_label} {row.occurred_on.isoformat()}"
    return AssessmentStatement(
        statement_id=f"event-{row.event_id}",
        role="risk"
        if row.kind == "company_shutdown" and row.stage != "announced"
        else "observation",
        text=f"{row.kind.replace('_', ' ').capitalize()} {row.stage}{when}.",
        evidence_ids=tuple(sorted(set(row.evidence_ids))),
        event_ids=(row.event_id,),
    )


def _assess_company(
    view: CompanySourceSnapshot,
    definitions: Mapping[str, MetricDefinition],
    first_recorded_at: datetime,
) -> CompanyAssessment:
    company = view.companies[0]
    evidence = {row.evidence_id: row for row in view.evidence}
    if _source_reason(company.evidence_ids, evidence) is not None:
        message = "Company identity requires verified public source evidence"
        raise ValueError(message)
    tagged: list[tuple[AssessmentStatement, frozenset[CompanyOutcomeId]]] = []
    for metric in view.metrics:
        definition = definitions[metric.metric_id]
        statement = _metric_statement(metric, definition, evidence, view.as_of)
        if statement is not None:
            tagged.append(
                (
                    statement,
                    frozenset(
                        key
                        for key, families in _FAMILIES.items()
                        if definition.family in families
                    ),
                )
            )
    superseded = {
        row.supersedes_id for row in view.events if row.supersedes_id is not None
    }
    for event in view.events:
        if event.event_id in superseded:
            continue
        statement = _event_statement(event, evidence, view.as_of)
        if statement is not None:
            tagged.append((statement, _EVENT_OUTCOMES[event.kind]))
    tagged.sort(key=lambda pair: pair[0].statement_id)
    public_relationships = tuple(
        row
        for row in view.relationships
        if _source_reason(row.evidence_ids, evidence) is None
    )
    family = resolve_family(
        view.model_copy(update={"relationships": public_relationships}),
        company.company_id,
        view.as_of,
    )
    digest = sha256(
        orjson.dumps(
            {
                "source_snapshot_id": view.snapshot_id,
                "company_id": company.company_id,
                "policy_version": POLICY_VERSION,
                "first_recorded_at": first_recorded_at,
            },
            option=orjson.OPT_SORT_KEYS,
        )
    ).hexdigest()
    return CompanyAssessment(
        assessment_id=f"assessment-{digest}",
        company_id=company.company_id,
        family_id=family.family_id,
        family_reason_codes=family.reason_codes,
        source_snapshot_id=view.snapshot_id,
        policy_version=POLICY_VERSION,
        as_of=view.as_of,
        first_recorded_at=first_recorded_at,
        mode="reconstructed",
        outcomes=_outcome_sections(tagged, view.as_of),
        statements=tuple(pair[0] for pair in tagged),
        synthetic=view.synthetic,
        limitations=(
            *view.limitations,
            "Evidence assessment only; no validated outcome probabilities.",
        ),
    )


def _outcome_sections(
    tagged: list[tuple[AssessmentStatement, frozenset[CompanyOutcomeId]]],
    as_of: datetime,
) -> tuple[CompanyOutcomeAssessment, ...]:
    results = []
    for outcome_id in COMPANY_OUTCOME_IDS:
        statements = [row for row, targets in tagged if outcome_id in targets]
        has_facts = any(row.role != "evidence_gap" for row in statements)
        results.append(
            CompanyOutcomeAssessment(
                outcome_id=outcome_id,
                horizon_end=company_horizon_end(as_of, outcome_id),
                assessment_status="evidence_only" if has_facts else "unavailable",
                summary=_SUMMARIES[outcome_id]
                if has_facts
                else "Relevant verified public evidence is unavailable.",
                statement_ids=tuple(row.statement_id for row in statements),
                reason_codes=("no_validated_outcome_model",)
                if has_facts
                else ("no_usable_public_evidence",),
            )
        )
    return tuple(results)
