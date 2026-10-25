"""Deterministic public-page selection and actionable coverage explanations."""

import re
from urllib.parse import urlsplit

from oxhack2026.api.research_configuration import SourceIssue

_FAMILIES = (
    ("legal", r"legal|terms|privacy|imprint|impressum|investor"),
    ("documentation", r"docs?|developers?|sdk|librar|quickstart"),
    ("hiring", r"career|jobs|positions"),
    ("commercial", r"pricing|plans|customers?|case-stud"),
    ("company", r"about|company|team"),
    ("updates", r"news|blog|changelog|release|rss|feed|sitemap"),
    ("product", r"product|platform|solution|feature"),
)
_ASSET = re.compile(r"\.(?:js|css|woff2?|png|jpe?g|svg|gif|mp4|zip|ico)$", re.I)
NPM_ASSOCIATION_VERIFIED = "npm_company_association_validated"
_OFFICIAL_PREFIXES = frozenset(
    {
        "docs",
        "developers",
        "careers",
        "jobs",
        "blog",
        "newsroom",
        "changelog",
    }
)


def official_host(host: str, domain: str) -> bool:
    """Recognize the confirmed host and linked public company content subdomains.

    Args:
        host: Normalized destination hostname with an optional www prefix removed.
        domain: Explicitly confirmed company hostname.
    Returns:
        Whether collection may use this host; this establishes no legal identity.
    """
    prefix, _, parent = host.partition(".")
    return host == domain or (parent == domain and prefix in _OFFICIAL_PREFIXES)


def crawl_family(url: str) -> str:
    """Return a stable page family for balanced official-site sampling."""
    path = urlsplit(url).path.lower()
    return next(
        (name for name, pattern in _FAMILIES if re.search(pattern, path)), "other"
    )


def crawl_candidate(url: str, domain: str) -> bool:
    """Accept relevant official pages, including linked docs/careers subdomains.

    Args:
        url: Already validated public HTTPS URL with credentials/query removed.
        domain: Explicitly confirmed company hostname.
    Returns:
        Whether this page can enter the bounded public crawl frontier.
    """
    parsed = urlsplit(url)
    host = (parsed.hostname or "").removeprefix("www.")
    return (
        official_host(host, domain)
        and not _ASSET.search(parsed.path)
        and not re.match(
            r"/(?:login|signin|signup|account|auth|cart|checkout|search|calendar)(?:/|$)",
            parsed.path,
            re.I,
        )
    )


def source_issue(code: str) -> SourceIssue:
    """Translate stable diagnostic codes to severity, explanation and next action."""
    messages = {
        "http_403": (
            "The source denied access to this request.",
            "Review provider credentials and access policy before refreshing.",
        ),
        "http_429": (
            "The source rate-limited this request; its backoff applies across jobs.",
            "Wait for the provider's limit to reset before refreshing.",
        ),
        "capture_size_limit": (
            "A public response exceeded the per-response capture limit.",
            "Other pages remain usable; this response was not interpreted.",
        ),
        "browser_request_blocked": (
            "A rendered page requested a resource that could not be collected safely.",
            "Retained HTML remains available; rendering does not bypass access limits.",
        ),
        "browser_unavailable_or_timeout": (
            "Local rendering was unavailable or exceeded its time limit.",
            "Review retained HTML; enable Chromium to retry JavaScript content.",
        ),
        "website_page_limit": (
            "The selected company-page limit was reached.",
            "Continue research to collect remaining pages.",
        ),
        "website_frontier_limit": (
            "Additional discovered links exceeded the retained frontier.",
            "Choose a deeper profile and refresh research.",
        ),
        "unverified_repository_mapping": (
            "No verified public repository was discovered.",
            "Review official documentation or continue remaining discovery.",
        ),
        "unverified_package_mapping": (
            "No verified public npm package was discovered.",
            "Package adoption is unavailable without an official association.",
        ),
        "unverified_package_ownership": (
            "An npm link or installation command did not establish package ownership.",
            "Verify the package's company homepage or reciprocal repository manifest.",
        ),
        "careers_page_without_structured_opening_count": (
            (
                "Careers content was collected, but a complete openings count "
                "could not be established."
            ),
            "Review the careers evidence; openings are not headcount.",
        ),
        "hn_non_exhaustive_or_truncated": (
            (
                "HN records were retrieved, but the provider did not establish "
                "a complete count."
            ),
            "Use the retrieved records; the complete-window count remains unknown.",
        ),
        "unverified_or_ambiguous_registry_mapping": (
            "No unambiguous legal-entity identifier was verified.",
            "A matching company name alone cannot establish legal identity.",
        ),
        "news_unmatched_candidates": (
            "Some retrieved articles could not be matched to the company.",
            "Unverified candidates are excluded from company findings.",
        ),
    }
    info = (
        code.endswith("_validated")
        or code == "sec_identity_verified_by_reciprocal_official_links"
        or code
        in {
            "news_no_articles",
            "no_public_openings",
        }
    )
    if code.startswith("missing_"):
        message, remedy = (
            "This source needs provider configuration.",
            "Configure the named provider on the backend and refresh research.",
        )
    else:
        message, remedy = messages.get(
            code,
            (
                code.replace("_", " ").capitalize() + ".",
                "Review source evidence and retry or continue if work remains.",
            ),
        )
    return SourceIssue(
        code=code,
        severity="info" if info else "warning",
        message=message,
        remedy=None if info else remedy,
    )
