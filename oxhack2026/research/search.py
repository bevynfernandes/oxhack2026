"""Grounding discovers candidates; only captured matched pages are evidence."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

import orjson
from pydantic import TypeAdapter

from oxhack2026.api.research_configuration import CrawlTarget
from oxhack2026.api.research_discovery import SearchCandidate, SearchDiscovery
from oxhack2026.explanations.config import gemini_api_key
from oxhack2026.explanations.gemini import GeminiInterpreter, MappingUnavailable
from oxhack2026.explanations.gemini_text import GroundingSnapshot
from oxhack2026.research.extraction import parse_page
from oxhack2026.research.frontier import official_host
from oxhack2026.research.network import CollectionError, public_url

if TYPE_CHECKING:
    from oxhack2026.research.collectors import Collector

logger = logging.getLogger(__name__)


def collect_search(collector: "Collector") -> None:
    """Capture up to six discovery candidates within shared collection budgets.

    Args:
        collector: Protected fetcher, confirmed identity, limits and checkpoints.
    Raises:
        CollectionError: Discovery is disabled, unavailable or over budget.
    """
    if not collector.limits.google_search_enabled:
        raise CollectionError("missing_google_search_enablement")
    if collector.limits.mapping_mode == "rules":
        raise CollectionError("missing_google_search_enablement")
    if not collector.discovery or not collector.discovery.artifact:
        _discover(collector)
    discovery = collector.discovery
    if discovery is None:
        raise CollectionError("google_search_missing_grounding")
    candidates = list(discovery.candidates)
    processed = 0
    for index, candidate in enumerate(candidates):
        if candidate.state != "pending":
            continue
        if processed >= min(6, collector.limits.article_pages):
            collector.reasons.append("google_search_page_limit")
            break
        processed += 1
        candidates[index] = _collect_candidate(collector, candidate)
        collector.discovery = discovery.model_copy(
            update={"candidates": tuple(candidates)}
        )
        collector.frontier = tuple(
            CrawlTarget(url=item.url) for item in candidates if item.state == "pending"
        )
        collector._save_progress()


def _collect_candidate(
    collector: "Collector", candidate: SearchCandidate
) -> SearchCandidate:
    from oxhack2026.research.collectors import _news_domain_matches

    if candidate.url in collector.known_urls:
        return candidate.model_copy(update={"state": "already_collected"})
    try:
        capture, content = collector.fetcher.fetch(candidate.url)
        page = parse_page(capture, content)
        host = (urlsplit(capture.final_url).hostname or "").removeprefix("www.")
        official = official_host(host, collector.identity.canonical_domain)
        matched = official or _news_domain_matches(
            page, collector.identity.canonical_domain
        )
        if matched:
            collector.support.extend(page.evidence)
            collector.claims.extend(
                claim.model_copy(
                    update={
                        "attribution": "company_reported"
                        if official
                        else "coverage_candidate",
                    }
                )
                for claim in page.claims
            )
            collector.events.extend(page.events)
            if official:
                collector.links.update(page.links)
                collector._official_accounts(capture, page)
        else:
            collector.reasons.append("google_search_unmatched_candidate")
        return candidate.model_copy(
            update={
                "state": "matched" if matched else "unmatched",
                "final_url": capture.final_url,
                "capture_id": capture.capture_id,
                "reason": None if matched else "google_search_unmatched_candidate",
            }
        )
    except CollectionError as error:
        logger.error("Search candidate unavailable: %s", str(error))  # noqa: TRY400
        blocked = next(
            (
                capture
                for capture in reversed(collector.fetcher.captures)
                if capture.url == candidate.url
            ),
            None,
        )
        collector.reasons.append(str(error))
        return candidate.model_copy(
            update={
                "state": "blocked",
                "reason": str(error),
                "capture_id": blocked.capture_id if blocked else None,
                "final_url": blocked.final_url if blocked else None,
            }
        )


def _metadata(collector: "Collector", payload: str) -> SearchDiscovery:
    snapshots = TypeAdapter(list[GroundingSnapshot]).validate_json(payload)
    queries = dict.fromkeys(
        query[:1000] for snapshot in snapshots for query in snapshot.web_search_queries
    )
    if not snapshots or not queries:
        raise CollectionError("google_search_missing_grounding")
    candidates: dict[str, SearchCandidate] = {}
    suggestions = None
    for snapshot in snapshots:
        if snapshot.search_entry_point:
            suggestions = snapshot.search_entry_point.rendered_content or suggestions
        for chunk in snapshot.grounding_chunks:
            if chunk.web is None:
                continue
            try:
                url = public_url(chunk.web.uri)
            except CollectionError:
                logger.error("Invalid Search public URL")  # noqa: TRY400
                collector.reasons.append("google_search_invalid_candidate")
                continue
            if url not in candidates and len(candidates) < 100:
                candidates[url] = SearchCandidate(url=url, title=chunk.web.title)
    assert collector.discovery is not None  # noqa: S101
    return collector.discovery.model_copy(
        update={
            "queries": tuple(queries)[:64],
            "candidates": tuple(candidates.values()),
            "search_suggestions": suggestions,
        }
    )


def _save_discovery(collector: "Collector", discovery: SearchDiscovery) -> None:
    serialized = orjson.dumps(discovery.model_dump(mode="json"))
    fetcher = collector.fetcher
    if fetcher.byte_count + len(serialized) > fetcher.max_bytes:
        raise CollectionError("capture_size_limit")
    if fetcher.shared_budget:
        fetcher.shared_budget.capture(len(serialized))
    fetcher.byte_count += len(serialized)
    artifact = fetcher.artifacts.write(serialized, "application/json")
    collector.discovery = discovery.model_copy(update={"artifact": artifact})
    if not discovery.candidates:
        collector.reasons.append("google_search_no_candidates")
    collector.frontier = tuple(
        CrawlTarget(url=candidate.url) for candidate in discovery.candidates
    )
    collector._save_progress()


def _usage(collector: "Collector", interpreter: GeminiInterpreter) -> None:
    assert collector.discovery is not None  # noqa: S101
    collector.discovery = collector.discovery.model_copy(
        update={
            "model_version": interpreter.model_version,
            "requests": interpreter.attempts,
            "reserved_input": interpreter.reserved_input,
            "input_tokens": interpreter.input_tokens
            if interpreter.usage_available
            else None,
            "output_tokens": interpreter.output_tokens
            if interpreter.usage_available
            else None,
        }
    )


def _discover(collector: "Collector") -> None:
    if not gemini_api_key():
        raise CollectionError("missing_gemini_credentials")
    if collector.fetcher.requests >= collector.fetcher.max_requests:
        raise CollectionError("request_or_time_budget")
    if collector.fetcher.shared_budget:
        collector.fetcher.shared_budget.request()
    collector.fetcher.requests += 1
    interpreter = GeminiInterpreter(
        deadline=collector.fetcher.deadline,
        model=collector.limits.model,
        max_requests=1,
        max_input=collector.limits.input_reservation,
    )
    collector.discovery = SearchDiscovery(
        run_id=collector.run_id or uuid4().hex,
        model=interpreter.model,
        collected_at=datetime.now(UTC),
        requests=1,
    )
    collector._save_progress()
    try:
        payload = interpreter.generate(
            "Use Google Search to discover relevant official and independent public "
            "pages about the confirmed company below. Find at most six pages about "
            "product releases, pricing, adoption, funding, financial disclosures "
            "and hiring. Cite original HTTPS sources. Do not establish account or "
            "legal ownership through names, or infer absent financial metrics. "
            f"Company: {collector.identity.company_name}; "
            f"confirmed domain: {collector.identity.canonical_domain}.",
            search=True,
        )
        _usage(collector, interpreter)
        _save_discovery(collector, _metadata(collector, payload))
    except (MappingUnavailable, ImportError) as error:
        logger.error("Search unavailable: %s", type(error).__name__)  # noqa: TRY400
        raise CollectionError(
            str(error)
            if isinstance(error, MappingUnavailable)
            else "missing_gemini_sdk"
        ) from error
    finally:
        _usage(collector, interpreter)
        interpreter.close_session()
