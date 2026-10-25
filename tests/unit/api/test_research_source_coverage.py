"""Public discovery chains, durable crawling and independent source failures."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
import orjson
import pytest

from oxhack2026.api.research_configuration import profile_settings
from oxhack2026.api.research_v2_schemas import DiscoveryRequest, Identity, SourceState
from oxhack2026.research.collectors import Collector
from oxhack2026.research.frontier import crawl_candidate, source_issue
from oxhack2026.research.network import BudgetExceeded, FetchBudget, Fetcher, Quotas
from oxhack2026.storage.artifacts import FileArtifactStore


def collector(
    root: Path, provider: str, links: tuple[str, ...], handler: httpx.MockTransport
) -> Collector:
    """Build an isolated collector with a mocked transport and verified links."""
    identity = Identity(
        identity_id="identity",
        request=DiscoveryRequest(domain="example.com"),
        requested_at=datetime.now(UTC),
        state="ready",
        canonical_domain="example.com",
        requested_domain="example.com",
        company_name="Example",
        official_links=links,
    )
    fetcher = Fetcher(FileArtifactStore(root), Quotas(interval=0), handler)
    return Collector(
        fetcher,
        identity,
        SourceState.model_validate({"provider": provider, "name": provider}),
    )


def test_organization_discovers_verified_package(tmp_path: Path) -> None:
    """An official org, manifest and reciprocal registry URL establish a package."""

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/repos"):
            value: object = [{"full_name": "example/sdk", "fork": False}]
        elif path.endswith("package.json"):
            value = {
                "content": base64.b64encode(
                    orjson.dumps({"name": "@example/sdk"})
                ).decode()
            }
        elif path.endswith("/latest"):
            value = {
                "name": "@example/sdk",
                "repository": {"url": "git+https://github.com/example/sdk.git"},
            }
        elif path.endswith("/releases"):
            value = []
        else:
            value = {"stargazers_count": 5, "open_issues_count": 2}
        return httpx.Response(200, json=value)

    result = collector(
        tmp_path,
        "github",
        ("https://github.com/example",),
        httpx.MockTransport(respond),
    ).collect()
    assert result.state == "completed"
    assert "https://www.npmjs.com/package/@example/sdk" in result.links
    assert result.details and {a.kind for a in result.details.accounts} == {
        "github_repo",
        "npm",
    }
    assert [row.value for row in result.observations] == [5, 2]


def test_careers_follows_embedded_board_and_deduplicates(tmp_path: Path) -> None:
    """A careers wrapper reaches its actual board instead of stopping at prose."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(
                200, text='<iframe src="https://jobs.ashbyhq.com/example"></iframe>'
            )
        return httpx.Response(
            200,
            json={"jobs": [{"id": "a"}, {"id": "a"}, {"id": "b", "isListed": False}]},
        )

    result = collector(
        tmp_path,
        "hiring",
        ("https://example.com/careers",),
        httpx.MockTransport(respond),
    ).collect()
    assert result.state == "completed"
    assert result.observations[0].value == 1
    assert result.details and result.details.accounts[0].kind == "hiring"


def test_crawl_checkpoint_continues_without_refetch(tmp_path: Path) -> None:
    """Selected page limits preserve unseen URLs and retained evidence."""
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(
            200,
            text=(
                "<main>Our platform provides useful software.</main>"
                '<a href="/about">About</a>'
            ),
        )

    first = collector(tmp_path, "website", (), httpx.MockTransport(respond))
    first.settings = profile_settings("fast").model_copy(update={"company_pages": 1})
    result = first.collect()
    assert result.details and result.details.frontier
    before = requested.count("/")
    next_run = collector(tmp_path, "website", (), httpx.MockTransport(respond))
    next_run.source = result.model_copy(update={"state": "running"})
    next_run.__post_init__()
    resumed = next_run.collect()
    assert requested.count("/") == before
    assert resumed.evidence[: len(result.evidence)] == result.evidence
    assert resumed.details and not resumed.details.frontier


def test_shared_budget_is_atomic() -> None:
    """Concurrent providers cannot overdraw the job's request allowance."""
    budget = FetchBudget(3, 100)

    def reserve(_: int) -> bool:
        try:
            budget.request()
        except BudgetExceeded:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(20))) == 3
    budget.capture(100)
    with pytest.raises(BudgetExceeded):
        budget.capture(1)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://docs.example.com/quickstart", True),
        ("https://example.com/legal", True),
        ("https://example.com/docs/main.js", False),
        ("https://docs.example.com.evil.test/docs", False),
    ],
)
def test_public_frontier_scope(url: str, expected: bool) -> None:
    """Official docs are discovered without promoting unrelated domains/assets."""
    assert crawl_candidate(url, "example.com") is expected


def test_informational_reason_is_not_failure() -> None:
    """Validation metadata does not mark a successfully collected source partial."""
    assert source_issue("sec_annual_timing_inputs_validated").severity == "info"
    assert (
        source_issue("sec_reciprocal_issuer_website_not_established").severity
        == "warning"
    )


def test_scanned_and_invalid_pdf_are_explicit() -> None:
    """Unsupported documents cannot become empty successful website evidence."""
    from io import BytesIO

    from pypdf import PdfWriter

    from oxhack2026.research.network import CollectionError
    from oxhack2026.research.pdf import pdf_markup

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(CollectionError, match="scanned_pdf"):
        pdf_markup(stream.getvalue())
    with pytest.raises(CollectionError, match="invalid_public_pdf"):
        pdf_markup(b"not a PDF")
