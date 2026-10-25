"""Official careers traversal and deduplicated public ATS job postings."""

import logging
import re
from collections import deque
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

import orjson
from bs4 import BeautifulSoup

from oxhack2026.api.research_v2_schemas import Capture, ResearchEvidence
from oxhack2026.research.extraction import Page, evidence, parse_page
from oxhack2026.research.network import CollectionError

if TYPE_CHECKING:
    from oxhack2026.research.collectors import Collector

logger = logging.getLogger(__name__)
_CAREERS = re.compile(r"career|jobs|positions|greenhouse|lever\.co|ashbyhq", re.I)


def _endpoint(url: str) -> tuple[str, str | None] | None:
    parsed = urlsplit(url)
    board = quote(parsed.path.strip("/").split("/")[0], safe="")
    if not board:
        return None
    if parsed.hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", "jobs"
    if parsed.hostname in {"jobs.lever.co", "jobs.eu.lever.co"}:
        host = (
            "api.eu.lever.co"
            if parsed.hostname == "jobs.eu.lever.co"
            else "api.lever.co"
        )
        return f"https://{host}/v0/postings/{board}?mode=json&limit=100&skip=0", None
    if parsed.hostname == "jobs.ashbyhq.com":
        return f"https://api.ashbyhq.com/posting-api/job-board/{board}", "jobs"
    return None


def _board(collector: "Collector", url: str) -> dict[str, ResearchEvidence] | None:
    endpoint = _endpoint(url)
    if not endpoint:
        return None
    base, key = endpoint
    found: dict[str, ResearchEvidence] = {}
    for page in range(5):
        value, item = collector.json(base.replace("skip=0", f"skip={page * 100}"))
        rows = value.get(key) if key and isinstance(value, dict) else value
        if not isinstance(rows, list):
            raise CollectionError("unrecognized_hiring_payload")
        collector._association("hiring", url, item)
        for row in rows:
            if not isinstance(row, dict) or row.get("isListed") is False:
                continue
            identifier = (
                row.get("id")
                or row.get("jobUrl")
                or row.get("hostedUrl")
                or row.get("absolute_url")
            )
            if identifier is not None:
                found[f"{base}/{identifier}"] = item
        if key or len(rows) < 100:
            break
        if page == 4:
            collector.reasons.append("hiring_pagination_limit")
    return found


def _structured_jobs(content: bytes) -> list[dict[str, object]]:
    soup = BeautifulSoup(content, "lxml")
    found: list[dict[str, object]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = orjson.loads(script.get_text())
        except orjson.JSONDecodeError:
            logger.error("Invalid careers JSON-LD")  # noqa: TRY400
            continue
        rows = value if isinstance(value, list) else [value]
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("@type") == "JobPosting":
                found.append(row)
            graph = row.get("@graph")
            if isinstance(graph, list):
                found.extend(
                    item
                    for item in graph
                    if isinstance(item, dict) and item.get("@type") == "JobPosting"
                )
    return found


def _careers_page(collector: "Collector", capture: "Capture", content: bytes) -> Page:
    page = parse_page(capture, content)
    if any(_endpoint(link) for link in page.links):
        return page
    return collector._website_page(capture, content)


def collect_hiring(collector: "Collector") -> None:
    """Follow official careers pages to public boards without inferring headcount.

    Args:
        collector: Current source, verified official links and controlled fetcher.
    Raises:
        CollectionError: No official careers link or a provider request failed.
    """
    queue = deque(
        sorted(url for url in collector.identity.official_links if _CAREERS.search(url))
    )
    if not queue:
        raise CollectionError("official_careers_link_unavailable")
    visited: set[str] = set()
    openings: dict[str, ResearchEvidence] = {}
    structured = False
    limit = {"fast": 6, "thorough": 12, "deep": 24}[collector.limits.profile]
    while queue and len(visited) < limit:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        board = _board(collector, url)
        if board is not None:
            structured = True
            openings.update(board)
            continue
        capture, content = collector.fetcher.fetch(url)
        page = _careers_page(collector, capture, content)
        collector.support.extend(page.evidence)
        collector.links.update(page.links)
        queue.extend(
            link for link in page.links if link not in visited and _CAREERS.search(link)
        )
        for row in _structured_jobs(content):
            identifier = row.get("url") or row.get("identifier")
            if isinstance(identifier, dict):
                identifier = identifier.get("value")
            if not isinstance(identifier, str):
                continue
            item = evidence(
                capture, orjson.dumps(row).decode()[:3000], "jsonld:JobPosting"
            )
            collector.support.append(item)
            openings[identifier] = item
        collector._save_progress()
    if structured and collector.support:
        collector.metric("advertised_openings", len(openings), collector.support[-1])
    else:
        collector.reasons.append("careers_page_without_structured_opening_count")
    if queue:
        collector.reasons.append("hiring_board_limit")
