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


def test_continuation_retains_unresolved_page_limitations(tmp_path: Path) -> None:
    """Finishing unseen pages cannot declare an unrendered homepage complete."""
    from oxhack2026.api.research_configuration import CrawlTarget, SourceDetails

    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            text="<main>"
            + "Our platform offers public software for teams. " * 5
            + "</main>",
        )
    )
    resumed = collector(tmp_path, "website", (), transport)
    resumed.source = resumed.source.model_copy(
        update={
            "state": "running",
            "reason_codes": (
                "website_page_limit",
                "browser_required_unavailable_or_budget",
                "website_frontier_limit",
            ),
            "details": SourceDetails(
                execution="pending",
                scope="planned_sample",
                coverage="limited",
                frontier=(CrawlTarget(url="https://example.com/about", depth=1),),
                visited=("https://example.com/",),
            ),
        }
    )
    resumed.__post_init__()
    result = resumed.collect()
    assert result.details and not result.details.frontier
    assert "website_page_limit" not in result.reason_codes
    assert "browser_required_unavailable_or_budget" in result.reason_codes
    assert "website_frontier_limit" in result.reason_codes
    assert result.state == "partial"
    assert result.details.coverage == "limited"


def test_continuation_discovers_github_then_npm(tmp_path: Path) -> None:
    """Continued official discovery reconsiders skipped dependent collectors."""
    from concurrent.futures import Executor
    from datetime import timedelta
    from unittest.mock import Mock

    from oxhack2026.api.research_configuration import ContinueRequest
    from oxhack2026.api.research_v2_schemas import JobRequest
    from oxhack2026.research.v2_service import V2Service
    from oxhack2026.research.v2_store import V2Store

    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        path = request.url.path
        if request.url.host == "example.com":
            link = (
                '<a href="https://github.com/example/sdk">SDK</a>'
                if path == "/docs"
                else '<a href="/docs">Documentation</a>'
            )
            return httpx.Response(
                200,
                text="<main>"
                + "Our platform offers public software for teams. " * 5
                + link
                + "</main>",
            )
        if path.endswith("package.json"):
            data: object = {
                "content": base64.b64encode(
                    orjson.dumps({"name": "@example/sdk"})
                ).decode()
            }
        elif path.endswith("/latest"):
            data = {
                "name": "@example/sdk",
                "repository": {"url": "git+https://github.com/example/sdk.git"},
            }
        elif path.endswith("/releases"):
            data = []
        elif request.url.host == "api.npmjs.org":
            end = datetime.now(UTC).date() - timedelta(days=1)
            data = {
                "downloads": [
                    {"day": (end - timedelta(days=i)).isoformat(), "downloads": 1}
                    for i in range(65)
                ]
            }
        else:
            data = {"stargazers_count": 5, "open_issues_count": 2}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(respond)
    initial = collector(tmp_path, "website", (), transport)
    initial.settings = profile_settings("fast").model_copy(update={"company_pages": 1})
    website = initial.collect()
    assert website.details and website.details.frontier
    store = V2Store(tmp_path)
    identity = initial.identity
    store.save_identity(identity.model_copy(update={"state": "queued"}))
    store.save_identity(identity)
    service = V2Service(
        store,
        Mock(spec=Executor),
        transport=transport,
        quotas=Quotas(interval=0),
        mapping_enabled=False,
    )
    queued = service.create(
        JobRequest(identity_id=identity.identity_id, identity_confirmed=True)
    )
    prior = queued.model_copy(
        update={
            "state": "running",
            "started_at": datetime.now(UTC),
            "sources": tuple(
                website
                if s.provider == "website"
                else s.model_copy(
                    update={
                        "state": "skipped"
                        if s.provider in {"github", "npm", "hiring"}
                        else "completed",
                        "finished_at": datetime.now(UTC),
                        "reason_codes": ("unverified_repository_mapping",)
                        if s.provider == "github"
                        else ("unverified_package_mapping",)
                        if s.provider == "npm"
                        else (),
                    }
                )
                for s in queued.sources
            ),
        }
    )
    store.save_job(prior)
    service._finish(prior, identity)
    finished = store.job(prior.job_id)
    assert finished.report_id
    original = store.report(finished.report_id).model_dump_json()
    continued = service.continue_job(prior.job_id, ContinueRequest(profile="fast"))
    service.run(continued.job_id)
    result = store.job(continued.job_id)
    github = next(s for s in result.sources if s.provider == "github")
    npm = next(s for s in result.sources if s.provider == "npm")
    assert github.state == "completed"
    assert npm.state == "completed"
    assert [row.value for row in npm.observations] == [30, 30]
    assert any("api.github.com/repos/example/sdk" in url for url in requests)
    assert any("api.npmjs.org/downloads/range/" in url for url in requests)
    assert store.report(finished.report_id).model_dump_json() == original
