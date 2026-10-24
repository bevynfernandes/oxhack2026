"""Bounded exact-domain HN observations, separate from v1 company metric families."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from oxhack2026.api.research_schemas import AttentionObservation
from oxhack2026.catalog.company import SourceEvidence
from oxhack2026.catalog.schemas import TimeWindow
from oxhack2026.ingest.capture import CaptureRequest, capture_get
from oxhack2026.storage.artifacts import FileArtifactStore


class _Hit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    objectID: str
    url: str | None = None
    created_at_i: int


class _Page(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hits: Annotated[tuple[_Hit, ...], Field(max_length=100)]
    nbHits: Annotated[int, Field(ge=0)]
    nbPages: Annotated[int, Field(ge=0)]
    exhaustiveNbHits: bool = True


@dataclass(frozen=True)
class AttentionQuery:
    """Exact confirmed identity/window; source requests never fetch the domain."""

    company_id: str
    domain: str
    window: TimeWindow


@dataclass(frozen=True)
class AttentionCapture:
    """Fresh observation and raw-backed evidence; incomplete counts stay missing."""

    observation: AttentionObservation
    evidence: SourceEvidence
    complete: bool


def collect_attention(
    query: AttentionQuery, client: httpx.Client, root: Path, run_id: str
) -> AttentionCapture:
    """Capture one bounded HN page and count exact-domain links in its time window.

    Args:
        query: Confirmed identity and declared start-inclusive/end-exclusive window.
        client: Injected HTTP client; no hosted model or target-domain request.
        root: Existing raw artifact/checkpoint root.
        run_id: Unique durable job ID; restart reuses identical captured bytes.
    Returns:
        Raw-backed evidence and an observed count only when pagination is complete.
    Raises:
        ValueError: Provider payload, window or capture integrity is invalid.
        RuntimeError: Provider access/rate budget is unavailable.
        httpx.HTTPError: Provider transport or HTTP request fails.
        OSError: Raw artifact/checkpoint persistence fails.
    """
    start = int(query.window.start.timestamp())
    end = int(query.window.end.timestamp())
    request = CaptureRequest(
        url="https://hn.algolia.com/api/v1/search_by_date",
        query_parameters=(
            ("query", query.domain),
            ("tags", "story"),
            ("restrictSearchableAttributes", "url"),
            ("numericFilters", f"created_at_i>={start},created_at_i<{end}"),
            ("hitsPerPage", "100"),
            ("page", "0"),
        ),
    )
    captured = capture_get(request, client, root, run_id)
    page = _Page.model_validate_json(FileArtifactStore(root).read(captured.artifact))
    complete = (
        page.nbPages <= 1 and page.nbHits == len(page.hits) and page.exhaustiveNbHits
    )
    ids = {
        hit.objectID
        for hit in page.hits
        if (urlsplit(hit.url or "").hostname or "").removeprefix("www.") == query.domain
        and start <= hit.created_at_i < end
    }
    if len({hit.objectID for hit in page.hits}) != len(page.hits):
        message = "Provider returned duplicate attention story identities"
        raise ValueError(message)
    evidence_id = f"hn-evidence-{run_id}"
    observation = AttentionObservation(
        observation_id=f"hn-observation-{run_id}",
        company_id=query.company_id,
        window=query.window,
        value=len(ids) if complete else None,
        state="observed" if complete else "missing",
        available_at=captured.collected_at,
        collected_at=captured.collected_at,
        evidence_ids=(evidence_id,),
        reason_codes=() if complete else ("provider_results_truncated",),
    )
    evidence = SourceEvidence(
        evidence_id=evidence_id,
        company_id=query.company_id,
        provider="hn_algolia",
        url=request.url,
        access="public",
        raw_artifact=captured.artifact,
        locator="hits: exact URL host and declared created_at_i window",
        assertion=(
            f"Complete bounded query: {len(ids)} exact-domain HN story links."
            if complete
            else "Bounded HN query is truncated; a complete count is unavailable."
        ),
        published_at=None,
        available_at=captured.collected_at,
        collected_at=captured.collected_at,
        availability_basis="first_observed",
        kind="platform_observed",
        review_state="verified",
    )
    return AttentionCapture(observation, evidence, complete)
