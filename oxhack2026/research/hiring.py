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
from oxhack2026.research.network import BudgetExceeded, CollectionError

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
    if content.lstrip().startswith(b"<?xml"):
        return []
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
    state = _restore_hiring(collector)
    queue = deque(state[0])
    if not queue:
        raise CollectionError("official_careers_link_unavailable")
    visited: set[str] = set()
    openings, structured = state[1:]
    limit = {"fast": 6, "thorough": 12, "deep": 24}[collector.limits.profile]
    failed: list[str] = []
    while queue and len(visited) < limit:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            board = _board(collector, url)
            if board is not None:
                structured = True
                openings.update(board)
            else:
                queue.extend(_hiring_page(collector, url, openings))
        except CollectionError as error:
            failed.append(url)
            collector.reasons.append(str(error))
            logger.error("Official hiring page unavailable: %s", str(error))  # noqa: TRY400
            if isinstance(error, BudgetExceeded):
                break
        _checkpoint_hiring(collector, list(queue) + failed, openings, structured)
    remaining = list(dict.fromkeys((*queue, *failed)))
    _checkpoint_hiring(collector, remaining, openings, structured)
    if structured and collector.support:
        collector.observations[:] = [
            row
            for row in collector.observations
            if row.metric_id != "advertised_openings"
        ]
        collector.metric(
            "advertised_openings",
            None if remaining else len(openings),
            collector.support[-1],
        )
        identifiers = tuple(dict.fromkeys(row.evidence_id for row in openings.values()))
        if identifiers:
            collector.observations[-1] = collector.observations[-1].model_copy(
                update={"evidence_ids": identifiers}
            )
    else:
        collector.reasons.append("careers_page_without_structured_opening_count")
    if remaining:
        collector.reasons.append("hiring_board_limit")


def _restore_hiring(
    collector: "Collector",
) -> tuple[list[str], dict[str, ResearchEvidence], bool]:
    """Restore official URLs and supported opening IDs from the durable cursor."""
    if not collector.cursor:
        return (
            sorted(
                url for url in collector.identity.official_links if _CAREERS.search(url)
            ),
            {},
            False,
        )
    value = orjson.loads(collector.cursor)
    if not isinstance(value, dict):
        raise CollectionError("invalid_hiring_checkpoint")
    queue, openings = value.get("queue"), value.get("openings")
    if (
        not isinstance(queue, list)
        or not all(isinstance(url, str) for url in queue)
        or not isinstance(openings, dict)
    ):
        raise CollectionError("invalid_hiring_checkpoint")
    evidence_by_id = {item.evidence_id: item for item in collector.support}
    restored = {
        key: evidence_by_id[identifier]
        for key, identifier in openings.items()
        if isinstance(key, str)
        and isinstance(identifier, str)
        and identifier in evidence_by_id
    }
    return queue, restored, value.get("structured") is True


def _checkpoint_hiring(
    collector: "Collector",
    queue: list[str],
    openings: dict[str, ResearchEvidence],
    structured: bool,
) -> None:
    """Persist remaining official URLs and deduplicated opening evidence after work."""
    collector.cursor = (
        orjson.dumps(
            {
                "queue": queue,
                "openings": {key: item.evidence_id for key, item in openings.items()},
                "structured": structured,
            }
        ).decode()
        if queue
        else None
    )
    collector._save_progress()


def _hiring_page(
    collector: "Collector", url: str, openings: dict[str, ResearchEvidence]
) -> list[str]:
    """Collect one careers wrapper, explicit job claims and linked official boards."""
    capture, content = collector.fetcher.fetch(url)
    page = _careers_page(collector, capture, content)
    collector.support.extend(page.evidence)
    collector.links.update(page.links)
    for row in _structured_jobs(content):
        identifier = row.get("url") or row.get("identifier")
        if isinstance(identifier, dict):
            identifier = identifier.get("value")
        if not isinstance(identifier, str):
            continue
        item = evidence(capture, orjson.dumps(row).decode()[:3000], "jsonld:JobPosting")
        collector.support.append(item)
        openings[identifier] = item
    return [link for link in page.links if _CAREERS.search(link)]
