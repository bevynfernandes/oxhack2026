"""Deterministic public HTML/XML extraction with excerpts and source locations."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import orjson
from bs4 import BeautifulSoup

from oxhack2026.api.research_v2_schemas import Capture, Claim, Event, ResearchEvidence
from oxhack2026.research.frontier import crawl_candidate
from oxhack2026.research.network import CollectionError, public_url

logger = logging.getLogger(__name__)

_RELEVANT = re.compile(
    r"about|pricing|customer|product|blog|changelog|news|career|jobs|sitemap|rss|feed",
    re.IGNORECASE,
)
_CLAIM = re.compile(
    r"\b(revenue|ARR|retention|funding|raised|profitable|profitability|employees|"
    r"customers|million|billion|headcount)\b",
    re.IGNORECASE,
)
_BLOCKED = re.compile(
    r"verify you are human|checking your browser|captcha|access denied|"
    r"subscribe to (?:continue|read)|sign in to (?:continue|read)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Page:
    """Parsed page plus provenance; links never imply ownership beyond official
    linkage."""

    name: str
    text: str
    links: tuple[str, ...]
    evidence: tuple[ResearchEvidence, ...]
    claims: tuple[Claim, ...]
    events: tuple[Event, ...]
    organizations: tuple[str, ...]
    needs_browser: bool
    account_evidence: tuple[tuple[str, ResearchEvidence], ...] = ()


def evidence(capture: Capture, excerpt: str, location: str) -> ResearchEvidence:
    """Create a bounded public excerpt referring to an exact capture and location."""
    return ResearchEvidence(
        evidence_id=uuid4().hex,
        capture_id=capture.capture_id,
        url=capture.final_url,
        excerpt=excerpt[:4000],
        location=location,
        collected_at=capture.collected_at,
    )


def _organizations(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(name for item in value for name in _organizations(item))
    if not isinstance(value, dict):
        return ()
    result = list(_organizations(value.get("@graph")))
    kind = value.get("@type", "")
    if kind == "Organization" or (isinstance(kind, list) and "Organization" in kind):
        name = value.get("name")
        if isinstance(name, str):
            result.append(name[:300])
    return tuple(result)


def _structured_names(soup: BeautifulSoup) -> list[str]:
    organizations: list[str] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            organizations.extend(_organizations(orjson.loads(script.get_text())))
        except orjson.JSONDecodeError:
            logger.error("Invalid public Organization JSON-LD")  # noqa: TRY400
    return organizations


def _organization_accounts(value: object, host: str) -> tuple[str, ...]:
    """Extract sameAs only from an Organization explicitly identifying this host."""
    if isinstance(value, list):
        return tuple(url for row in value for url in _organization_accounts(row, host))
    if not isinstance(value, dict):
        return ()
    linked = list(_organization_accounts(value.get("@graph"), host))
    reference = value.get("url") or value.get("@id")
    kind = value.get("@type")
    if not isinstance(reference, str) or not (
        kind == "Organization" or (isinstance(kind, list) and "Organization" in kind)
    ):
        return tuple(linked)
    if (urlsplit(reference).hostname or "").removeprefix("www.") != host:
        return tuple(linked)
    accounts = value.get("sameAs", [])
    if isinstance(accounts, str):
        accounts = [accounts]
    if isinstance(accounts, list):
        linked.extend(url for url in accounts if isinstance(url, str))
    return tuple(linked)


def _structured_accounts(
    soup: BeautifulSoup, capture: Capture
) -> dict[str, ResearchEvidence]:
    """Retain officially scoped JSON-LD account links with their actual location."""
    accounts: dict[str, ResearchEvidence] = {}
    host = (urlsplit(capture.final_url).hostname or "").removeprefix("www.")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            urls = _organization_accounts(orjson.loads(script.get_text()), host)
        except orjson.JSONDecodeError:
            logger.error("Invalid account JSON-LD")  # noqa: TRY400
            continue
        for url in urls:
            try:
                normalized = public_url(url)
            except CollectionError:
                continue
            accounts[normalized] = evidence(
                capture, normalized, "jsonld:Organization.sameAs"
            )
    return accounts


def _parse_markup(capture: Capture, content: bytes) -> BeautifulSoup:
    if "pdf" in capture.content_type:
        from oxhack2026.research.pdf import pdf_markup

        content = pdf_markup(content)
    xml = "xml" in capture.content_type or content.lstrip().startswith(b"<?xml")
    if xml and b"<!DOCTYPE" in content.upper():
        raise CollectionError("xml_doctype_not_supported")
    return BeautifulSoup(content, "xml" if xml else "lxml")


def _embedded_boards(content: bytes) -> dict[str, None]:
    links: dict[str, None] = {}
    for board_match in re.finditer(
        r"https://(?:jobs\.ashbyhq\.com|jobs(?:\.eu)?\.lever\.co|(?:job-)?boards\.greenhouse\.io)/[A-Za-z0-9_-]+",
        content.decode(errors="replace").replace(r"\/", "/"),
    ):
        links[board_match.group()] = None
    return links


def _package_commands(
    soup: BeautifulSoup, capture: Capture
) -> dict[str, ResearchEvidence]:
    """Return package associations from explicit installation commands and quotes."""
    packages: dict[str, ResearchEvidence] = {}
    for block in soup.select("pre, code"):
        code = block.get_text(" ", strip=True)
        for match in re.finditer(
            r"(?:npm\s+(?:install|i|add)|pnpm\s+(?:add|install)|yarn\s+add|bun\s+add)"
            r"\s+(?:--[\w-]+\s+)*(@[a-z0-9_.-]+/[a-z0-9_.-]+|[a-z0-9_.-]+)",
            code,
        ):
            package = match.group(1)
            if package.startswith("-"):
                continue
            url = f"https://www.npmjs.com/package/{package}"
            packages.setdefault(
                url, evidence(capture, match.group(), "code:package_install")
            )
    return packages


def _needs_browser(soup: BeautifulSoup, text: str) -> bool:
    """Detect short pages or empty main content obscured by navigation text."""
    main = soup.find("main")
    return len(text) < 200 or (
        main is not None and len(main.get_text(" ", strip=True)) < 80
    )


def parse_page(capture: Capture, content: bytes) -> Page:
    """Extract metadata, JSON-LD, visible blocks, claims, dates and public links.

    Args:
        capture: Metadata for the exact retained HTML/XML bytes.
        content: Bounded captured bytes.
    Returns:
        Deterministic evidence; ambiguous disclosures remain attributed prose.
    Raises:
        CollectionError: The page presents an access challenge or paywall.
    """
    soup = _parse_markup(capture, content)
    organizations = _structured_names(soup)
    metadata = soup.select_one('meta[property="og:site_name"]')
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    name = str(metadata.get("content", "")) if metadata else ""
    name = (name or (organizations[0] if organizations else "") or title)[:300]
    links: dict[str, None] = {}
    for element in soup.select("a[href], link[href], iframe[src], loc, link"):
        value = (
            element.get("href") or element.get("src") or element.get_text(strip=True)
        )
        if not isinstance(value, str) or not value:
            continue
        try:
            links[public_url(urljoin(capture.final_url, value))] = None
        except CollectionError:
            continue
    links.update(_embedded_boards(content))
    account_evidence = _structured_accounts(soup, capture)
    account_evidence.update(_package_commands(soup, capture))
    links.update(dict.fromkeys(account_evidence))
    for hidden in soup.select("script, style, noscript, template"):
        hidden.decompose()
    text = soup.get_text(" ", strip=True)
    if _BLOCKED.search(text[:12000]):
        raise CollectionError("access_challenge_or_paywall")
    support = [evidence(capture, text[:3000] or title, "visible_text")]
    support.extend(account_evidence.values())
    if name:
        support.append(evidence(capture, name, "metadata:og:site_name/jsonld/title"))
    claims: list[Claim] = []
    seen: set[str] = set()
    for index, block in enumerate(soup.select("p, li, td, th, h1, h2, h3")):
        statement = block.get_text(" ", strip=True)[:2000]
        match = _CLAIM.search(statement)
        if not match or statement in seen or len(claims) >= 50:
            continue
        seen.add(statement)
        item = evidence(capture, statement, f"visible_block[{index}]")
        support.append(item)
        claims.append(
            Claim(
                claim_id=uuid4().hex,
                text=statement,
                category=match.group().lower(),
                attribution="company_reported",
                evidence_ids=(item.evidence_id,),
            )
        )
    events: list[Event] = []
    for index, tag in enumerate(
        soup.select("time[datetime], meta[property='article:published_time']")[:20]
    ):
        published = str(tag.get("datetime") or tag.get("content") or "")[:100]
        item = evidence(capture, published, f"publication_date[{index}]")
        support.append(item)
        events.append(
            Event(
                event_id=uuid4().hex,
                kind="first_party_publication",
                title=title or name,
                url=capture.final_url,
                published_at=published,
                evidence_ids=(item.evidence_id,),
            )
        )
    return Page(
        name=name,
        text=text,
        links=tuple(links),
        evidence=tuple(support),
        claims=tuple(claims),
        events=tuple(events),
        organizations=tuple(organizations),
        needs_browser=_needs_browser(soup, text),
        account_evidence=tuple(account_evidence.items()),
    )


def company_links(links: tuple[str, ...], domain: str) -> tuple[str, ...]:
    """Select relevant same-domain crawl links; a subdomain alone is not a legal
    mapping."""
    return tuple(link for link in links if crawl_candidate(link, domain))
