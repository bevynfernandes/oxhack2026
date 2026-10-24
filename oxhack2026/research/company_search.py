"""Offline, source-backed company-name candidates before identity confirmation."""

import logging
import re
from pathlib import Path

import polars as pl
from tld import get_fld

from oxhack2026.api.research_v2_schemas import (
    CompanySearchCandidate,
    CompanySearchResult,
)
from oxhack2026.research.network import normalize_domain

logger = logging.getLogger(__name__)
DOMAIN_INDEX = Path(__file__).parent / "bundled" / "company-domains.parquet"
DIRECTORY_URL = "https://majestic.com/reports/majestic-million"
DIRECTORY_ATTRIBUTION = "Majestic Million, CC BY 3.0; domain-only snapshot 2026-10-25"


def company_search(query: str) -> CompanySearchResult:
    """Resolve explicit URLs or look up unverified directory candidates locally.

    Args:
        query: Company name or public HTTPS URL, at most 200 characters.
    Returns:
        Up to five possible websites, requiring identity preview. Directory absence
        means missing coverage, not a nonexistent business. No domain is guessed.
    Raises:
        ValueError: Input is empty, excessive, contains controls, or an invalid URL.
    """
    query = query.strip()
    if not 2 <= len(query) <= 200 or any(ord(char) < 32 for char in query):
        message = "Supply a company name or public HTTPS URL"
        raise ValueError(message)
    if "://" in query or (
        "." in query
        and not any(c.isspace() for c in query)
        and get_fld(f"https://{query}", fail_silently=True) is not None
    ):
        domain = normalize_domain(query)
        return CompanySearchResult(
            query=query,
            candidates=(
                CompanySearchCandidate(
                    name=domain,
                    domain=domain,
                    website=f"https://{domain}",
                    source="input",
                ),
            ),
            reason_codes=("identity_preview_required",),
        )
    try:
        candidates = search_candidates(query, DOMAIN_INDEX)
    except (OSError, pl.exceptions.PolarsError) as error:
        logger.error(  # noqa: TRY400
            "Company-name directory unavailable: %s", type(error).__name__
        )
        return CompanySearchResult(
            query=query,
            candidates=(),
            reason_codes=("name_search_unavailable", "supply_exact_company_domain"),
        )
    return CompanySearchResult(
        query=query,
        candidates=candidates,
        reason_codes=("unverified_directory_candidates", "identity_preview_required")
        if candidates
        else ("directory_name_not_found", "supply_exact_company_domain"),
        source_url=DIRECTORY_URL,
        source_attribution=DIRECTORY_ATTRIBUTION,
    )


def search_candidates(query: str, index: Path) -> tuple[CompanySearchCandidate, ...]:
    """Find exact normalized brand/domain-label matches in a published snapshot.

    Args:
        query: Company name, with spaces and punctuation ignored for matching.
        index: Sorted Parquet directory; its manifest records source and hashes.
    Returns:
        Up to five unverified candidates, ordered by source rank for discovery
        only. Subdomains and marketing suffixes cannot establish brand identity.
        A lexical match is not ownership proof; aliases require exact URL input.
    Raises:
        ValueError: No meaningful company-name token exists.
        OSError: The directory cannot be read.
        polars.exceptions.PolarsError: The directory schema or data is invalid.
    """
    compact_name = re.sub(r"[^a-z0-9]", "", query.casefold())
    if not compact_name:
        message = "A searchable company name is required"
        raise ValueError(message)
    rows = (
        pl.scan_parquet(index)
        .filter(pl.col("name_key") == compact_name)
        .sort("source_rank")
        .select("domain")
        .collect()
    )
    candidates: dict[str, CompanySearchCandidate] = {}
    for (value,) in rows.iter_rows():
        try:
            domain = normalize_domain(value)
        except ValueError:
            logger.debug("Rejected malformed domain-directory candidate")
            continue
        registered = get_fld(f"https://{domain}", fail_silently=True)
        if registered != domain:
            continue
        if re.sub(r"[^a-z0-9]", "", domain.split(".")[0]) != compact_name:
            continue
        candidates.setdefault(
            domain,
            CompanySearchCandidate(
                name=query,
                domain=domain,
                website=f"https://{domain}",
                source="public_directory",
            ),
        )
        if len(candidates) == 5:
            break
    return tuple(candidates.values())
