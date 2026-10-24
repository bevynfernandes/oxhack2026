"""Registry adapters gated on explicit reviewed entity mappings, never fuzzy names."""

import base64
import logging
import os
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

import orjson
import polars as pl
from pydantic import Field, TypeAdapter

from oxhack2026.api.research_v2_schemas import Claim
from oxhack2026.api.schemas import DTO, PublicURL
from oxhack2026.features.disclosure_timing import sec_disclosure_timing
from oxhack2026.research.network import CollectionError

if TYPE_CHECKING:
    from oxhack2026.research.collectors import Collector

logger = logging.getLogger(__name__)


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


def _sec_history(
    collector: "Collector", payload: object, cik: str, headers: dict[str, str]
) -> None:
    if not isinstance(payload, dict) or not isinstance(payload.get("filings"), dict):
        raise CollectionError("sec_missing_submissions_history")
    references = payload["filings"].get("files")
    if not isinstance(references, list):
        raise CollectionError("sec_missing_history_page_manifest")
    if len(references) > 8:
        raise CollectionError("sec_history_page_limit_incomplete")
    names = [row.get("name") if isinstance(row, dict) else None for row in references]
    if any(
        not isinstance(name, str)
        or re.fullmatch(rf"CIK{cik}-submissions-[0-9]{{3}}\.json", name) is None
        for name in names
    ) or len(set(names)) != len(names):
        raise CollectionError("sec_invalid_history_page_manifest")
    history = {}
    for name in names:
        page, _ = collector.json(f"https://data.sec.gov/submissions/{name}", headers)
        history[str(name)] = page
    try:
        frame = sec_disclosure_timing(payload, cik, datetime.now(UTC).date(), history)
    except (TypeError, ValueError, pl.exceptions.PolarsError) as error:
        raise CollectionError("sec_invalid_annual_timing_metadata") from error
    collector.reasons.append(
        "sec_annual_timing_inputs_validated"
        if frame.height
        else "sec_no_annual_report_history"
    )


def _check_sec_response(
    collector: "Collector",
    payload: object,
    cik: str,
    headers: dict[str, str],
    include_history: bool,
) -> None:
    if not isinstance(payload, dict) or str(payload.get("cik", "")).zfill(10) != cik:
        raise CollectionError("sec_cik_mismatch")
    if not include_history:
        return
    try:
        _sec_history(collector, payload, cik, headers)
    except (CollectionError, orjson.JSONDecodeError) as error:
        reason = (
            str(error)
            if isinstance(error, CollectionError)
            else "sec_invalid_history_json"
        )
        logger.error("SEC annual history is unavailable: %s", reason)  # noqa: TRY400
        collector.reasons.append(reason)


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
    for index, endpoint in enumerate(endpoints):
        payload, support = collector.json(endpoint, headers)
        if provider == "sec":
            _check_sec_response(collector, payload, cik, headers, index == 0)
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
