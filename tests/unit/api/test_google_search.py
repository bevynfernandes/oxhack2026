"""Discovery provenance, identity matching, bounded collection and recovery."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import httpx
import orjson
import pytest

from oxhack2026.api.research_configuration import ResearchSettings
from oxhack2026.api.research_v2_schemas import (
    LEGACY_PROVIDERS,
    PROVIDERS,
    DiscoveryRequest,
    Identity,
    Job,
    SourceState,
)
from oxhack2026.explanations.gemini import GeminiInterpreter, MappingUnavailable
from oxhack2026.research.collectors import Collector
from oxhack2026.research.network import FetchBudget, Fetcher, Quotas
from oxhack2026.research.v2_service import V2Service
from oxhack2026.research.v2_store import V2Store
from oxhack2026.storage.artifacts import FileArtifactStore


def _collector(
    tmp_path: Path,
    respond: Callable[[httpx.Request], httpx.Response],
    source: SourceState | None = None,
) -> Collector:
    identity = Identity(
        identity_id="identity",
        request=DiscoveryRequest(domain="qdrant.tech"),
        state="ready",
        requested_at=datetime.now(UTC),
        requested_domain="qdrant.tech",
        canonical_domain="qdrant.tech",
        company_name="Qdrant",
    )
    fetcher = Fetcher(
        FileArtifactStore(tmp_path),
        Quotas(interval=0),
        httpx.MockTransport(respond),
        shared_budget=FetchBudget(120, 32 * 1024 * 1024),
    )
    return Collector(
        fetcher,
        identity,
        source or SourceState(provider="google_search", name="Search"),
        settings=ResearchSettings(google_search_enabled=True),
        run_id="job",
    )


def _discovery(
    monkeypatch: pytest.MonkeyPatch,
    urls: list[str],
) -> Mock:
    payload = [
        {
            "web_search_queries": ["qdrant.tech funding"],
            "grounding_chunks": [
                {"web": {"uri": url, "title": "Page"}} for url in urls
            ],
            "search_entry_point": {"rendered_content": "<p>Search suggestions</p>"},
            "response": "INVENTED GENERATED FINANCIAL ASSERTION",
        }
    ]
    calls = Mock()

    def generate(
        interpreter: GeminiInterpreter,
        prompt: str,
        *,
        search: bool = False,
    ) -> str:
        calls(prompt, search=search)
        interpreter.attempts += 1
        interpreter.reserved_input += 3000
        interpreter.input_tokens = 100
        interpreter.output_tokens = 50
        interpreter.usage_available = True
        return orjson.dumps(payload).decode()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(GeminiInterpreter, "generate", generate)
    return calls


def test_search_retains_captures_and_excludes_unmatched_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only original matched pages support findings; generated text never does."""
    calls = _discovery(
        monkeypatch,
        [
            "https://qdrant.tech/pricing?utm_source=search",
            "https://qdrant.tech/pricing",
            "https://publisher.example/matched",
            "https://publisher.example/unrelated",
        ],
    )

    def respond(request: httpx.Request) -> httpx.Response:
        text = "Qdrant at qdrant.tech offers a vector database for developers."
        if request.url.path == "/unrelated":
            text = "An unrelated company reports revenue of $100 million in 2025."
        return httpx.Response(
            200,
            content=f"<html><main><p>{text}</p></main></html>".encode(),
            headers={"content-type": "text/html"},
        )

    collector = _collector(tmp_path, respond)
    result = collector.collect()

    assert calls.call_count == 1
    assert calls.call_args.kwargs == {"search": True}
    assert result.discovery and result.discovery.artifact
    assert result.discovery.requests == 1
    assert result.discovery.reserved_input == 3000
    assert [row.state for row in result.discovery.candidates] == [
        "matched",
        "matched",
        "unmatched",
    ]
    assert len(result.captures) == 3
    assert all("unrelated" not in row.excerpt for row in result.evidence)
    assert all("?" not in row.url for row in result.discovery.candidates)
    artifact = collector.fetcher.artifacts.read(result.discovery.artifact)
    assert b"INVENTED GENERATED" not in artifact
    assert b"test-key" not in artifact
    assert result.state == "partial"


def test_search_continuation_reuses_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending candidates resume without repeating provider discovery or old pages."""
    calls = _discovery(monkeypatch, [f"https://qdrant.tech/page/{i}" for i in range(8)])
    fetched: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=(
                b"<main><p>Qdrant provides an open source vector database "
                b"for developers."
                b"</p></main>"
            ),
        )

    first = _collector(tmp_path, respond).collect()
    assert first.discovery and first.details
    assert len(first.details.frontier) == 2
    assert len(first.captures) == 6
    second = _collector(tmp_path, respond, first).collect()

    assert second.discovery and second.details
    assert not second.details.frontier
    assert len(second.captures) == 8
    assert len(fetched) == len(set(fetched)) == 8
    assert calls.call_count == 1
    assert second.state == "completed"


@pytest.mark.parametrize(
    "reason", ["gemini_rate_limited", "gemini_provider_unavailable"]
)
def test_search_failure_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    """Provider failure is durable and cannot become a successful empty search."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fail(
        interpreter: GeminiInterpreter, prompt: str, *, search: bool = False
    ) -> str:
        interpreter.attempts += 1
        raise MappingUnavailable(reason)

    monkeypatch.setattr(GeminiInterpreter, "generate", fail)
    result = _collector(tmp_path, lambda request: httpx.Response(200)).collect()
    assert result.state == "failed"
    assert result.reason_codes == (reason,)
    assert result.discovery and result.discovery.requests == 1
    assert not result.evidence


def test_search_disable_and_missing_grounding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rules-only mode never calls the model; absent metadata is a failure."""
    calls = _discovery(monkeypatch, [])
    collector = _collector(tmp_path, lambda request: httpx.Response(200))
    collector.settings = ResearchSettings(
        google_search_enabled=True, mapping_mode="rules"
    )
    assert collector.collect().state == "skipped"
    calls.assert_not_called()
    monkeypatch.setattr(GeminiInterpreter, "generate", lambda *args, **kwargs: "[]")
    failed = _collector(tmp_path, lambda request: httpx.Response(200)).collect()
    assert failed.state == "failed"
    assert "google_search_missing_grounding" in failed.reason_codes


def test_legacy_source_states_and_capabilities_are_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eight-source jobs retain their bytes; new jobs expose a ninth source."""
    for providers in [LEGACY_PROVIDERS, PROVIDERS]:
        job = Job(
            job_id="job",
            identity_id="identity",
            requested_at=datetime.now(UTC),
            sources=tuple(
                SourceState(provider=provider, name=provider) for provider in providers
            ),
        )
        serialized = job.model_dump_json()
        assert Job.model_validate_json(serialized).model_dump_json() == serialized
        assert '"discovery"' not in serialized
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_GOOGLE_SEARCH", "0")
    service = V2Service(V2Store(tmp_path))
    assert service._settings("thorough").model == "gemma-4-31b-it"
    capability = next(
        row
        for row in service.capabilities().providers
        if row.provider == "google_search"
    )
    assert capability.available is False
