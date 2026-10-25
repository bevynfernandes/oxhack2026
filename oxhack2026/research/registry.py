"""Registry adapters gated on explicit reviewed entity mappings, never fuzzy names."""

import base64
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlsplit
from uuid import uuid4

import orjson
import polars as pl
from pydantic import Field, TypeAdapter

from oxhack2026.api.research_v2_schemas import Claim, Observation, ResearchEvidence
from oxhack2026.api.schemas import DTO, PublicURL, Window
from oxhack2026.features.disclosure_timing import sec_disclosure_timing
from oxhack2026.features.sec_financials import (
    sec_annual_filing_metadata,
    sec_annual_financials,
)
from oxhack2026.models.financial_inference import estimate_annual_cash_flow
from oxhack2026.research.extraction import evidence
from oxhack2026.research.network import CollectionError
from oxhack2026.research.sec_identity import (
    sec_filing_candidates,
    sec_issuer_website_quote,
)

if TYPE_CHECKING:
    from oxhack2026.research.collectors import Collector

logger = logging.getLogger(__name__)


def registry_mapping_path() -> Path:
    """Locate operator overrides or the small bundled reviewed identity catalog.

    Returns:
        Explicit SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS path when set; otherwise
        the packaged catalog. A catalog entry still requires its retrieved quote
        and matching issuer response. Unknown domains do not inherit a mapping.
    """
    configured = os.environ.get("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS")
    return (
        Path(configured)
        if configured
        else (Path(__file__).with_name("bundled") / "reviewed-registry-mappings.json")
    )


class RegistryMapping(DTO):
    """Configured or reciprocally evidenced association with an exact registry ID."""

    domain: str
    jurisdiction: str
    evidence_url: PublicURL
    reviewed: bool
    evidence_quote: Annotated[str, Field(min_length=10, max_length=1000)] | None = None
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
) -> dict[str, object]:
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
    return history


def _check_sec_response(
    collector: "Collector",
    payload: object,
    cik: str,
    headers: dict[str, str],
    include_history: bool,
) -> dict[str, object] | None:
    if not isinstance(payload, dict) or str(payload.get("cik", "")).zfill(10) != cik:
        raise CollectionError("sec_cik_mismatch")
    if not include_history:
        return None
    try:
        return _sec_history(collector, payload, cik, headers)
    except (CollectionError, orjson.JSONDecodeError) as error:
        reason = (
            str(error)
            if isinstance(error, CollectionError)
            else "sec_invalid_history_json"
        )
        logger.error("SEC annual history is unavailable: %s", reason)  # noqa: TRY400
        collector.reasons.append(reason)
        return None


def _sec_financial_observations(
    collector: "Collector",
    payload: object,
    filings: pl.DataFrame,
    cik: str,
    as_of: datetime,
) -> None:
    from oxhack2026.research.extraction import evidence

    parsed = sec_annual_financials(payload, filings, cik, as_of.date())
    if parsed.is_empty() or not isinstance(payload, dict):
        return
    latest = parsed.filter(pl.col("accession_number") == parsed["accession_number"][-1])
    capture = collector.fetcher.captures[-1]
    for row in latest.iter_rows(named=True):
        if row["status"] != "observed":
            continue
        concept = row["concepts"][0]
        facts = payload["facts"]["us-gaap"][concept]["units"]["USD"]
        index, fact = next(
            (index, fact)
            for index, fact in enumerate(facts)
            if fact.get("accn") == row["accession_number"]
            and fact.get("filed") == row["filing_date"].isoformat()
            and fact.get("end") == row["period_end"].isoformat()
            and fact.get("start")
            == (row["period_start"].isoformat() if row["period_start"] else None)
            and float(fact["val"]) == row["value"]
        )
        item = evidence(
            capture,
            orjson.dumps(fact).decode(),
            f"json:$.facts.us-gaap.{concept}.units.USD[{index}]",
        )
        collector.support.append(item)
        start = row["period_start"] or row["period_end"]
        end = row["period_end"] + timedelta(days=1)
        collector.observations.append(
            Observation(
                observation_id=uuid4().hex,
                metric_id="revenue"
                if row["metric"] == "revenue"
                else f"sec_{row['metric']}_usd",
                definition=(
                    f"Consolidated {row['metric'].replace('_', ' ')}, "
                    "company-reported in "
                    f"original SEC accession {row['accession_number']}; "
                    f"period ended {row['period_end']}. "
                    "Cash is not unrestricted runway."
                ),
                unit="USD",
                value=row["value"],
                collected_at=as_of,
                window=Window(
                    start=datetime.combine(start, datetime.min.time(), UTC),
                    end=datetime.combine(end, datetime.min.time(), UTC),
                ),
                evidence_ids=(item.evidence_id,),
            )
        )


def _sec_cash_flow_research(
    collector: "Collector",
    payload: object,
    submissions: object,
    cik: str,
    history: dict[str, object] | None,
) -> None:
    if history is None:
        collector.reasons.append("sec_financial_model_requires_complete_metadata")
        return
    try:
        now = datetime.now(UTC)
        filings = sec_annual_filing_metadata(submissions, cik, now.date(), history)
        _sec_financial_observations(collector, payload, filings, cik, now)
        collector.cash_flow_research = estimate_annual_cash_flow(
            payload,
            filings,
            cik,
            now,
            tuple(item.evidence_id for item in collector.support),
        )
        collector.reasons.append("experimental_cash_flow_research_model_ran")
    except (TypeError, ValueError, OSError, pl.exceptions.PolarsError) as error:
        logger.error("SEC financial inference unavailable: %s", type(error).__name__)  # noqa: TRY400
        collector.reasons.append(
            str(error)
            if isinstance(error, ValueError) and str(error).startswith("sec_")
            else "sec_cash_flow_research_unavailable"
        )


def _mapping_support_headers(provider: str, url: str) -> dict[str, str] | None:
    if provider == "sec" and urlsplit(url).hostname in {
        "sec.gov",
        "www.sec.gov",
        "data.sec.gov",
    }:
        user_agent = os.environ.get("SEC_USER_AGENT", "")
        if user_agent:
            return {"User-Agent": user_agent}
    return None


def _mapping_support(
    collector: "Collector", mapping: RegistryMapping
) -> ResearchEvidence:
    from oxhack2026.research.extraction import evidence

    capture, content = collector.fetcher.fetch(
        mapping.evidence_url,
        _mapping_support_headers(collector.source.provider, mapping.evidence_url),
    )
    text = content.decode(errors="replace")
    location = "reviewed_registry_mapping_support"
    excerpt = text[:2000]
    if mapping.evidence_quote:
        position = text.find(mapping.evidence_quote)
        if position < 0:
            raise CollectionError("registry_mapping_quote_not_found")
        location += f":character:{position}"
        excerpt = text[
            max(0, position - 200) : position + len(mapping.evidence_quote) + 200
        ]
    return evidence(capture, excerpt, location)


def _sec_linked_candidates(collector: "Collector") -> tuple[tuple[str, str], ...]:
    from oxhack2026.research.extraction import parse_page

    domain = collector.identity.canonical_domain
    links = set(collector.identity.official_links)
    candidates = sec_filing_candidates(links)
    visited: set[str] = set()
    for _ in range(3):
        if candidates:
            break
        investor_pages = sorted(
            (
                link
                for link in links - visited
                if (urlsplit(link).hostname or "")
                in {f"{prefix}.{domain}" for prefix in ("ir", "investor", "investors")}
            ),
            key=lambda link: (
                not re.search(r"sec-filing|annual|financial", urlsplit(link).path),
                link,
            ),
        )
        if not investor_pages:
            break
        link = investor_pages[0]
        visited.add(link)
        capture, content = collector.fetcher.fetch(link)
        if urlsplit(capture.final_url).hostname != urlsplit(link).hostname:
            raise CollectionError("sec_investor_page_unconfirmed_redirect")
        page = parse_page(capture, content)
        collector.support.extend(page.evidence[:1])
        links.update(page.links)
        candidates = sec_filing_candidates(links)
    return candidates


def _discover_sec_mapping(
    collector: "Collector",
) -> tuple[RegistryMapping, ResearchEvidence]:
    from oxhack2026.research.extraction import evidence

    headers = _mapping_support_headers("sec", "https://www.sec.gov/")
    if headers is None:
        raise CollectionError("missing_sec_user_agent")
    domain = collector.identity.canonical_domain
    candidates = _sec_linked_candidates(collector)
    if len({cik for cik, _ in candidates}) != 1:
        raise CollectionError("unverified_or_ambiguous_registry_mapping")
    verified: list[tuple[RegistryMapping, ResearchEvidence]] = []
    for cik, link in candidates[:2]:
        capture, content = collector.fetcher.fetch(link, headers)
        if capture.final_url != link:
            raise CollectionError("sec_identity_filing_unconfirmed_redirect")
        quote = sec_issuer_website_quote(content, cik, domain)
        if quote is None:
            continue
        text = content.decode(errors="replace")
        position = text.index(quote)
        verified.append(
            (
                RegistryMapping(
                    domain=domain,
                    jurisdiction="US",
                    reviewed=False,
                    cik=cik,
                    evidence_url=link,
                ),
                evidence(
                    capture,
                    text[max(0, position - 400) : position + len(quote) + 200],
                    f"sec_reciprocal_issuer_website:character:{position}",
                ),
            )
        )
    if not verified:
        raise CollectionError("sec_reciprocal_issuer_website_not_established")
    collector.reasons.append("sec_identity_verified_by_reciprocal_official_links")
    return verified[0]


def _discover_company_number(
    collector: "Collector",
) -> tuple[RegistryMapping, ResearchEvidence]:
    if not os.environ.get("COMPANIES_HOUSE_API_KEY"):
        raise CollectionError("missing_companies_house_credentials")
    links = [
        url
        for url in collector.identity.official_links
        if re.search(r"legal|terms|privacy|imprint", urlsplit(url).path)
        and (urlsplit(url).hostname or "").removeprefix("www.")
        == collector.identity.canonical_domain
    ]
    candidates: dict[str, tuple[RegistryMapping, ResearchEvidence]] = {}
    from bs4 import BeautifulSoup

    for url in sorted(links, key=lambda link: (len(link), link))[:3]:
        capture, content = collector.fetcher.fetch(url)
        text = BeautifulSoup(content, "lxml").get_text(" ", strip=True)
        for match in re.finditer(
            r"(?:company|registration|registered)\s+(?:number|no\.?|#)\s*[:.]?\s*([A-Z]{2}\d{6}|\d{8})\b",
            text,
            re.I,
        ):
            number = match.group(1).upper()
            quote = text[max(0, match.start() - 100) : match.end() + 100]
            item = evidence(capture, quote, "legal:company_number")
            mapping = RegistryMapping(
                domain=collector.identity.canonical_domain,
                jurisdiction="UK",
                evidence_url=url,
                reviewed=False,
                evidence_quote=quote,
                company_number=number,
            )
            candidates[number] = (mapping, item)
    if len(candidates) != 1:
        raise CollectionError("unverified_or_ambiguous_registry_mapping")
    return next(iter(candidates.values()))


def _registry_selection(
    collector: "Collector",
) -> tuple[RegistryMapping, ResearchEvidence]:
    selection = registry_mapping_path()
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
    if not matches and provider == "sec":
        mapping, item = _discover_sec_mapping(collector)
    elif not matches and provider == "companies_house":
        mapping, item = _discover_company_number(collector)
    elif len(matches) != 1:
        raise CollectionError("unverified_or_ambiguous_registry_mapping")
    else:
        mapping = matches[0]
        item = _mapping_support(collector, mapping)
    return mapping, item


def collect_registry(collector: "Collector") -> None:
    """Fetch facts for reviewed or reciprocally verified SEC issuer mappings.

    Raises:
        CollectionError: Missing mapping, credentials, public verification or payload.
        OSError: Mapping configuration cannot be read.
        ValueError: Mapping configuration is invalid.
    """
    mapping, item = _registry_selection(collector)
    provider = collector.source.provider
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
    submissions: object = None
    history: dict[str, object] | None = None
    for index, endpoint in enumerate(endpoints):
        payload, support = collector.json(endpoint, headers)
        if provider == "sec":
            checked_history = _check_sec_response(
                collector, payload, cik, headers, index == 0
            )
            if index == 0:
                submissions, history = payload, checked_history
            else:
                _sec_cash_flow_research(collector, payload, submissions, cik, history)
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
