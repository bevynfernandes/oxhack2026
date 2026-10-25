"""Bounded HN pagination and time subdivision with resumable exact-domain records."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import orjson

from oxhack2026.api.research_v2_schemas import Event, Observation
from oxhack2026.api.schemas import Window
from oxhack2026.research.network import CollectionError

if TYPE_CHECKING:
    from oxhack2026.research.collectors import Collector


def _hits(
    collector: "Collector", payload: dict[str, object], low: int, high: int
) -> None:
    hits = payload.get("hits")
    if not isinstance(hits, list):
        raise CollectionError("invalid_hn_response")
    known = {row.event_id for row in collector.events}
    for index, row in enumerate(hits):
        if not isinstance(row, dict):
            continue
        identifier, timestamp = str(row.get("objectID", "")), row.get("created_at_i")
        if not identifier.isdigit() or not isinstance(timestamp, int):
            continue
        host = (
            (urlsplit(str(row.get("url", ""))).hostname or "")
            .removeprefix("www.")
            .lower()
        )
        if (
            host != collector.identity.canonical_domain
            or not low <= timestamp < high
            or f"hn-{identifier}" in known
        ):
            continue
        title = str(row.get("title") or "")
        item = collector._hn_title_evidence(title, index, collector.support[-1])
        collector.events.append(
            Event(
                event_id=f"hn-{identifier}",
                kind="hn_exact_domain_story",
                title=title,
                url=f"https://news.ycombinator.com/item?id={identifier}",
                published_at=datetime.fromtimestamp(timestamp, UTC).isoformat(),
                evidence_ids=(item.evidence_id,),
            )
        )
        known.add(f"hn-{identifier}")


def _window(
    cursor: str | None,
) -> tuple[datetime, datetime, list[tuple[int, int, int, int]], bool]:
    end = datetime.now(UTC)
    start = end - timedelta(days=30)
    if not cursor:
        return start, end, [(int(start.timestamp()), int(end.timestamp()), 0, 0)], False
    saved = orjson.loads(cursor)
    return (
        datetime.fromtimestamp(saved["start"], UTC),
        datetime.fromtimestamp(saved["end"], UTC),
        [tuple(row) for row in saved["pending"]],
        saved["uncertain"],
    )


def collect_hn(collector: "Collector") -> None:
    """Retain records independently of a provably complete provider window.

    Args:
        collector: Source checkpoint, controlled fetcher and confirmed domain.
    Raises:
        CollectionError: Provider payload or saved pagination checkpoint is invalid.
    """
    start, end, pending, uncertain = _window(collector.cursor)
    limit = {"fast": 10, "thorough": 20, "deep": 40}[collector.limits.profile]
    for _ in range(limit):
        if not pending:
            break
        low, high, page, depth = pending.pop(0)
        query = urlencode(
            {
                "query": collector.identity.canonical_domain,
                "tags": "story",
                "hitsPerPage": 100,
                "page": page,
                "restrictSearchableAttributes": "url",
                "numericFilters": f"created_at_i>={low},created_at_i<{high}",
            }
        )
        try:
            payload, _ = collector.json(
                f"https://hn.algolia.com/api/v1/search_by_date?{query}"
            )
        except CollectionError:
            pending.insert(0, (low, high, page, depth))
            collector.cursor = orjson.dumps(
                {
                    "start": int(start.timestamp()),
                    "end": int(end.timestamp()),
                    "pending": pending,
                    "uncertain": uncertain,
                }
            ).decode()
            raise
        if not isinstance(payload, dict) or not isinstance(payload.get("nbPages"), int):
            raise CollectionError("invalid_hn_response")
        _hits(collector, payload, int(start.timestamp()), int(end.timestamp()))
        exhaustive = payload.get("exhaustiveNbHits") is True
        if not exhaustive and high - low > 3600 and depth < 10:
            middle = (low + high) // 2
            pending.extend(((low, middle, 0, depth + 1), (middle, high, 0, depth + 1)))
        elif page + 1 < payload["nbPages"]:
            pending.insert(0, (low, high, page + 1, depth))
        elif not exhaustive:
            uncertain = True
        collector.cursor = (
            orjson.dumps(
                {
                    "start": int(start.timestamp()),
                    "end": int(end.timestamp()),
                    "pending": pending,
                    "uncertain": uncertain,
                }
            ).decode()
            if pending
            else None
        )
        collector._save_progress()
    complete = not pending and not uncertain
    collector.observations = [
        row for row in collector.observations if not row.metric_id.startswith("hn_")
    ]
    count = sum(event.kind == "hn_exact_domain_story" for event in collector.events)
    for metric, value in (
        ("hn_retrieved_exact_domain_records_30d", count),
        ("hn_complete_exact_domain_count_30d", count if complete else None),
    ):
        collector.observations.append(
            Observation(
                observation_id=uuid4().hex,
                metric_id=metric,
                definition=(
                    "Exact-domain HN story links; retrieved and complete-window "
                    "counts are distinct, not users or sentiment."
                ),
                unit="story_links",
                value=value,
                window=Window(start=start, end=end),
                collected_at=datetime.now(UTC),
                evidence_ids=tuple(item.evidence_id for item in collector.support),
                missing_reason=None
                if value is not None
                else "non_exhaustive_or_truncated",
            )
        )
    if not complete:
        collector.reasons.append("hn_non_exhaustive_or_truncated")
