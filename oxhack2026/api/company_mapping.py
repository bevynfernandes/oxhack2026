"""Public projection of source records, including derived private information."""

from oxhack2026.api import company_schemas as s
from oxhack2026.catalog.company import (
    CompanyEvent,
    CompanyRelationship,
    CompanySourceSnapshot,
)


def public_relationships(
    source: CompanySourceSnapshot,
) -> tuple[CompanyRelationship, ...]:
    """Keep mappings only when every supporting source is public.

    Args:
        source: Fully validated source publication.
    Returns:
        Publicly supported relationship identities and effective dates.
    """
    public = {row.evidence_id for row in source.evidence if row.access == "public"}
    return tuple(row for row in source.relationships if set(row.evidence_ids) <= public)


def public_events(
    source: CompanySourceSnapshot, company_id: str
) -> tuple[CompanyEvent, ...]:
    """Omit company events whose descriptions rely on restricted evidence.

    Args:
        source: Fully validated source publication.
        company_id: Exact company to project.
    Returns:
        Events with wholly public supporting evidence; no private descriptions.
    """
    public = {row.evidence_id for row in source.evidence if row.access == "public"}
    return tuple(
        row
        for row in source.events
        if row.company_id == company_id and set(row.evidence_ids) <= public
    )


def public_metrics(
    source: CompanySourceSnapshot, company_id: str
) -> tuple[s.CompanyMetric, ...]:
    """Withhold restricted values and reasons while retaining explicit missingness.

    Args:
        source: Fully validated source publication.
        company_id: Exact company to project.
    Returns:
        Public measurements or explicit restricted placeholders.
    Raises:
        ValueError: A projected record violates the public contract.
    """
    public = {row.evidence_id for row in source.evidence if row.access == "public"}
    rows = []
    for row in source.metrics:
        if row.company_id != company_id:
            continue
        payload = row.model_dump(exclude={"supersedes_id"})
        if not set(row.evidence_ids) <= public:
            payload.update(
                value=None,
                state="restricted",
                reason="Restricted source measurement; value and details withheld.",
                evidence_ids=(),
            )
        rows.append(s.CompanyMetric.model_validate(payload))
    return tuple(rows)


def public_coverage(
    source: CompanySourceSnapshot, company_id: str
) -> tuple[s.PublicCompanyCoverage, ...]:
    """Exclude private states from public coverage; report withheld metrics separately.

    Args:
        source: Fully validated source publication.
        company_id: Exact company to project.
    Returns:
        C1 frozen coverage with private measurement states withheld.
    Raises:
        KeyError: The company is unknown.
    """
    public = {row.evidence_id for row in source.evidence if row.access == "public"}
    restricted = {
        row.metric_id
        for row in source.metrics
        if row.company_id == company_id and not set(row.evidence_ids) <= public
    }
    definitions = {row.metric_id: row for row in source.definitions}
    result = []
    for coverage in source.coverage(company_id):
        fields = coverage.model_dump()
        for key in fields.keys() - {"company_id", "family"}:
            fields[key] = tuple(item for item in fields[key] if item not in restricted)
        fields["restricted_metric_ids"] = tuple(
            sorted(
                key for key in restricted if definitions[key].family == coverage.family
            )
        )
        result.append(s.PublicCompanyCoverage.model_validate(fields))
    return tuple(result)
