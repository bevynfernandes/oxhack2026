"""Registry adapters gated on explicit reviewed entity mappings, never fuzzy names."""

import base64
import os
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from pydantic import Field, TypeAdapter

from oxhack2026.api.research_v2_schemas import Claim
from oxhack2026.api.schemas import DTO, PublicURL
from oxhack2026.research.network import CollectionError

if TYPE_CHECKING:
    from oxhack2026.research.collectors import Collector


class RegistryMapping(DTO):
    """Operator-reviewed association with a public supporting URL and jurisdiction."""

    domain: str
    jurisdiction: str
    evidence_url: PublicURL
    reviewed: bool
    cik: Annotated[str, Field(pattern=r"^[0-9]{1,10}$")] | None = None
    company_number: Annotated[str, Field(pattern=r"^[A-Z0-9]{8}$")] | None = None


def _registry_claims(
    payload: object, jurisdiction: str, support: tuple[str, ...], provider: str
) -> tuple[Claim, ...]:
    if not isinstance(payload, dict):
        return ()
    keys = (
        "name",
        "company_name",
        "company_number",
        "cik",
        "date_of_creation",
        "company_status",
        "jurisdiction",
        "accounts",
    )
    return tuple(
        Claim(
            claim_id=uuid4().hex,
            category=f"{provider}_registry_fact",
            text=f"{jurisdiction}: {key} = {payload[key]}",
            attribution="registry",
            evidence_ids=support,
        )
        for key in keys
        if payload.get(key) is not None
    )


def collect_registry(collector: "Collector") -> None:
    """Fetch registry facts for exact reviewed mappings; missing keys remain explicit.

    Raises:
        CollectionError: Missing mapping, credentials, public verification or payload.
        OSError: Mapping configuration cannot be read.
        ValueError: Mapping configuration is invalid.
    """
    selection = os.environ.get("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS", "")
    if not selection:
        raise CollectionError("unverified_registry_mapping")
    with open(selection, "rb") as stream:
        content = stream.read(65537)
    if len(content) > 65536:
        raise CollectionError("registry_mapping_size_limit")
    mappings = TypeAdapter(tuple[RegistryMapping, ...]).validate_json(content)
    matches = [
        row
        for row in mappings
        if row.domain == collector.identity.canonical_domain and row.reviewed
    ]
    provider = collector.source.provider
    matches = [
        row for row in matches if (row.cik if provider == "sec" else row.company_number)
    ]
    if len(matches) != 1:
        raise CollectionError("unverified_or_ambiguous_registry_mapping")
    mapping = matches[0]
    capture, content = collector.fetcher.fetch(mapping.evidence_url)
    from oxhack2026.research.extraction import evidence

    item = evidence(
        capture,
        content[:2000].decode(errors="replace"),
        "reviewed_registry_mapping_support",
    )
    collector.support.append(item)
    if provider == "sec":
        user_agent = os.environ.get("SEC_USER_AGENT", "")
        if not user_agent:
            raise CollectionError("missing_sec_user_agent")
        cik = (mapping.cik or "").zfill(10)
        endpoints = [
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        ]
        headers = {"User-Agent": user_agent}
    else:
        key = os.environ.get("COMPANIES_HOUSE_API_KEY", "")
        if not key:
            raise CollectionError("missing_companies_house_credentials")
        base = f"https://api.company-information.service.gov.uk/company/{mapping.company_number}"
        endpoints = [base, f"{base}/filing-history?items_per_page=20"]
        headers = {
            "Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()
        }
    for endpoint in endpoints:
        payload, support = collector.json(endpoint, headers)
        collector.claims.extend(
            _registry_claims(
                payload,
                mapping.jurisdiction,
                (support.evidence_id, item.evidence_id),
                provider,
            )
        )
        collector.claims.append(
            Claim(
                claim_id=uuid4().hex,
                category=f"{provider}_registry_metadata",
                text=(
                    f"Registry record in {mapping.jurisdiction}. "
                    "Periods and units are retained in the raw disclosure. "
                    "This does not establish private-startup financial coverage."
                ),
                attribution="registry",
                evidence_ids=(support.evidence_id, item.evidence_id),
            )
        )
    collector.reasons.append("bounded_registry_history_periods_preserved_in_capture")
