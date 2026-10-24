"""Regressions for reviewed news identity matching and public HN permalinks."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from oxhack2026.api.research_v2_schemas import (
    DiscoveryRequest,
    Event,
    Identity,
    SourceState,
)
from oxhack2026.research.collectors import Collector
from oxhack2026.research.network import Fetcher, Quotas
from oxhack2026.storage.artifacts import FileArtifactStore


def _identity() -> Identity:
    return Identity(
        identity_id="qdrant-preview",
        request=DiscoveryRequest(domain="qdrant.tech"),
        state="ready",
        requested_at=datetime.now(UTC),
        requested_domain="qdrant.tech",
        canonical_domain="qdrant.tech",
        company_name="Qdrant",
    )


@pytest.mark.parametrize(
    "text,matched",
    [
        ("Qdrant at qdrant.tech announced a release.", True),
        ("Visit https://www.qdrant.tech/ for details.", True),
        ("QDRANT.TECH is mentioned here.", True),
        ("Visit evilqdrant.tech instead.", False),
        ("Visit qdrant.tech.example instead.", False),
        ("Visit prefix-qdrant.tech instead.", False),
        ("Visit \u0435qdrant.tech instead.", False),
        ("Unrelated company announcement.", False),
    ],
)
def test_news_requires_exact_domain_token(
    tmp_path: Path, text: str, matched: bool
) -> None:
    """Lookalike text stays a candidate; genuine domain tokens can establish a match."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.gdeltproject.org":
            return httpx.Response(
                200,
                json={
                    "articles": [
                        {"url": "https://publisher.example/story", "title": "Story"}
                    ]
                },
            )
        return httpx.Response(200, content=f"<p>{text}</p>".encode())

    fetcher = Fetcher(
        FileArtifactStore(tmp_path), Quotas(interval=0), httpx.MockTransport(respond)
    )
    result = Collector(
        fetcher, _identity(), SourceState(provider="news", name="News")
    ).collect()
    assert len(result.events) == 1
    expected = "news_domain_matched" if matched else "news_unverified_candidate"
    assert result.events[0].kind == expected
    assert len(result.captures) == 2


def test_exact_official_link_can_match_news(tmp_path: Path) -> None:
    """A parsed exact hostname is sufficient even if visible prose omits the domain."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.gdeltproject.org":
            return httpx.Response(
                200, json={"articles": [{"url": "https://publisher.example/story"}]}
            )
        return httpx.Response(
            200, content=b'<a href="https://www.qdrant.tech/product">Product</a>'
        )

    fetcher = Fetcher(
        FileArtifactStore(tmp_path), Quotas(interval=0), httpx.MockTransport(respond)
    )
    result = Collector(
        fetcher, _identity(), SourceState(provider="news", name="News")
    ).collect()
    assert result.events[0].kind == "news_domain_matched"


def test_hn_event_preserves_working_permalink(tmp_path: Path) -> None:
    """HN permalinks retain only their allowlisted numeric item ID query."""
    timestamp = int((datetime.now(UTC) - timedelta(days=1)).timestamp())
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "objectID": "123",
                        "url": "https://qdrant.tech/",
                        "created_at_i": timestamp,
                    }
                ],
                "nbPages": 1,
                "exhaustiveNbHits": True,
            },
        )
    )
    fetcher = Fetcher(FileArtifactStore(tmp_path), Quotas(interval=0), transport)
    result = Collector(
        fetcher, _identity(), SourceState(provider="hn", name="HN")
    ).collect()
    assert result.events[0].url == "https://news.ycombinator.com/item?id=123"
    assert "?" not in result.captures[0].url


@pytest.mark.parametrize(
    "url",
    [
        "https://news.ycombinator.com/item?id=123&token=secret",
        "https://news.ycombinator.com/item?id=not-a-number",
        "https://news.ycombinator.com/item?id=123#fragment",
        "https://news.ycombinator.com.example/item?id=123",
        "https://user:password@news.ycombinator.com/item?id=123",
        "https://other.example/story?token=secret",
    ],
)
def test_event_url_rejects_unapproved_query_data(url: str) -> None:
    """The HN permalink exception cannot allow credentials or arbitrary query data."""
    with pytest.raises(ValidationError):
        Event(event_id="event", kind="story", title="Title", url=url, evidence_ids=())
