"""Name discovery is bounded, source-backed and independent of model scores."""

from concurrent.futures import Executor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import polars as pl
import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.app import create_app
from oxhack2026.api.routes.research_v2 import get_v2_service
from oxhack2026.research.company_search import company_search, search_candidates
from oxhack2026.research.v2_service import V2Service
from oxhack2026.research.v2_store import V2Store


def test_gemini_transport_failure_stops_remaining_batches() -> None:
    """A failed optional provider does not consume all remaining batch attempts."""
    import time
    from unittest.mock import patch

    from oxhack2026.explanations.gemini import GeminiInterpreter, MappingUnavailable
    from oxhack2026.research.documents import DocumentBlock, EvidenceDocument
    from oxhack2026.research.evidence_mapping import MappingEngine, MappingWork

    document = EvidenceDocument(
        capture_id="capture",
        url="https://example.com",
        title="Example",
        language="en",
        text="text",
        sha256="a" * 64,
        blocks=(),
    )
    block = DocumentBlock(
        block_id="block",
        text="text " * 240,
        heading="",
        location="paragraph",
        start=0,
        end=1200,
        role="paragraph",
    )
    engine = MappingEngine(Path("mock-unused"))
    report = Mock()
    report.identity.company_name = "Example"
    with (
        patch.object(
            MappingEngine,
            "_response",
            side_effect=MappingUnavailable("gemini_rate_limited"),
        ) as response,
        patch.object(MappingEngine, "_progress"),
    ):
        engine._interpret(
            report,
            [(document, block)] * 20,
            MappingWork(),
            GeminiInterpreter(time.monotonic() + 5),
            datetime.now(UTC),
        )
    assert response.call_count == 1
    assert "gemini_rate_limited" in engine._reasons


def test_direct_url_uses_existing_preview_without_search_fetch() -> None:
    """Explicit company domains never need a directory or provider call."""
    with patch("oxhack2026.research.company_search.search_candidates") as lookup:
        result = company_search("https://www.example.com/product")
    assert result.candidates[0].domain == "example.com"
    assert result.candidates[0].source == "input"
    assert result.reason_codes == ("identity_preview_required",)
    lookup.assert_not_called()


def test_search_retains_ambiguity_and_rejects_impostor_domains() -> None:
    """Subdomains and 'official' suffixes do not establish company identity."""
    directory = pl.DataFrame(
        {
            "name_key": ["example"] * 8,
            "domain": [
                "example.com",
                "docs.example.com",
                "example.co.uk",
                "example.evil.com",
                "exampleofficial.com",
                "en.wikipedia.org",
                "127.0.0.1",
                "[bad",
            ],
            "source_rank": list(range(1, 9)),
        }
    )
    with patch("polars.scan_parquet", return_value=directory.lazy()):
        result = search_candidates("Example", Path("mock-index"))
    assert [item.domain for item in result] == ["example.com", "example.co.uk"]
    assert all(item.source == "public_directory" for item in result)


def test_unmatched_name_is_not_changed_into_a_guessed_com_domain() -> None:
    """Directory absence prompts an exact domain rather than fabricated identity."""
    with patch("oxhack2026.research.company_search.search_candidates", return_value=()):
        result = company_search("Unrecorded business")
    assert result.candidates == ()
    assert "directory_name_not_found" in result.reason_codes
    assert result.source_url == "https://majestic.com/reports/majestic-million"
    assert "CC BY 3.0" in (result.source_attribution or "")


@pytest.mark.parametrize(
    "query", ["", "x", "name\nattack", "x" * 201, "http://example.com"]
)
def test_invalid_query_never_searches(query: str) -> None:
    """Malformed name and URL requests are rejected before source access."""
    with (
        patch("oxhack2026.research.company_search.search_candidates") as lookup,
        pytest.raises(ValueError),
    ):
        company_search(query)
    lookup.assert_not_called()


def test_directory_failure_is_explicit_and_does_not_guess() -> None:
    """An unreadable artifact is an actionable state, not an invented company."""
    with patch(
        "oxhack2026.research.company_search.search_candidates",
        side_effect=OSError("unavailable"),
    ) as lookup:
        result = company_search("Example")
    assert result.candidates == ()
    assert "name_search_unavailable" in result.reason_codes
    assert lookup.call_count == 1


def test_dotted_brand_is_not_assumed_to_be_a_public_domain() -> None:
    """Node.js is a brand lookup because .js is not a recognized public suffix."""
    with patch(
        "oxhack2026.research.company_search.search_candidates", return_value=()
    ) as lookup:
        company_search("Node.js")
    assert lookup.call_args.args[0] == "Node.js"


def test_company_search_api_and_disabled_runtime() -> None:
    """The endpoint previews domains and respects collector configuration."""
    service = V2Service(V2Store(Path("mock-unused")), executor=Mock(spec=Executor))
    app = create_app()
    app.dependency_overrides[get_v2_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v2/company-search", json={"query": "example.com"})
        assert response.status_code == 200
        assert response.json()["candidates"][0]["domain"] == "example.com"
        service.collection_enabled = False
        assert (
            client.post("/api/v2/company-search", json={"query": "Example"}).status_code
            == 503
        )


def test_directory_build_preserves_provenance_and_sorts_index() -> None:
    """Only selected columns become candidates; the original CSV remains untouched."""
    import io
    from types import SimpleNamespace

    import orjson

    from oxhack2026.research.build_name_index import build_name_index

    source = pl.DataFrame(
        {"GlobalRank": [3, 1, 2], "Domain": ["beta.io", "EXAMPLE.COM", "alpha.org"]}
    )
    with (
        patch("polars.read_csv", return_value=source),
        patch.object(pl.DataFrame, "write_parquet", autospec=True) as write,
        patch.object(Path, "mkdir"),
        patch.object(
            Path, "open", side_effect=[io.BytesIO(b"csv"), io.BytesIO(b"index")]
        ),
        patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime=0)),
        patch.object(Path, "write_bytes") as manifest,
    ):
        build_name_index(Path("mock.csv"), Path("mock.parquet"))
    directory = write.call_args.args[0]
    assert directory["name_key"].to_list() == ["alpha", "beta", "example"]
    assert directory["domain"].to_list() == ["alpha.org", "beta.io", "example.com"]
    provenance = orjson.loads(manifest.call_args.args[0])
    assert provenance["rows"] == 3
    assert len(provenance["source_sha256"]) == 64
    assert "never model inputs" in provenance["purpose"]
