"""Mocked identity, adapter, network, queue and additive API acceptance checks."""

import socket
import time
from concurrent.futures import Executor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from oxhack2026.api.app import create_app
from oxhack2026.api.research_v2_schemas import (
    PROVIDERS,
    DiscoveryRequest,
    Identity,
    JobRequest,
    SourceState,
)
from oxhack2026.api.routes.research_v2 import get_v2_service
from oxhack2026.research.collectors import Collector
from oxhack2026.research.extraction import parse_page
from oxhack2026.research.network import (
    BudgetExceeded,
    CollectionError,
    Fetcher,
    PinnedTransport,
    Quotas,
    normalize_domain,
    public_addresses,
)
from oxhack2026.research.v2_service import QueueFull, V2Service
from oxhack2026.research.v2_store import V2Store
from oxhack2026.storage.artifacts import FileArtifactStore


@pytest.mark.parametrize(
    "value", ["EXAMPLE.com", "https://www.example.com/product", "example.com."]
)
def test_normalization(value: str) -> None:
    """Equivalent HTTPS identities normalize without a catalogue lookup."""
    assert normalize_domain(value) == "example.com"


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com/?key=secret",
        "localhost",
        "127.0.0.1",
        "https://[::1]",
        "https://example.com:8443",
        "a b.example.com",
    ],
)
def test_invalid_identity_input(value: str) -> None:
    """Invalid inputs never reach a network boundary."""
    with pytest.raises(ValueError):
        normalize_domain(value)


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_strict_confirmation(value: object) -> None:
    """Only explicit boolean true authorizes collection of the preview."""
    with pytest.raises(ValidationError):
        JobRequest.model_validate(
            {"identity_id": "preview", "identity_confirmed": value}
        )


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "192.168.1.1",
        "::1",
        "fc00::1",
        "::ffff:8.8.8.8",
    ],
)
def test_rejects_nonpublic_dns(address: str) -> None:
    """Every DNS answer is checked, including IPv4 mapped IPv6 addresses."""
    with (
        patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
        ),
        pytest.raises(CollectionError, match="private_destination"),
    ):
        public_addresses("example.com")


def test_dns_mixed_answers_rejected() -> None:
    """A public answer cannot hide a private address later in the DNS answer set."""
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
        for address in ("8.8.8.8", "127.0.0.1")
    ]
    with (
        patch("socket.getaddrinfo", return_value=answers),
        pytest.raises(CollectionError),
    ):
        public_addresses("example.com")


def test_connection_pins_validated_address() -> None:
    """TLS connects to a validated literal IP and authenticates the original
    hostname."""
    response = Mock()
    response.read1.side_effect = [b"ok", b""]
    response.getheaders.return_value = []
    response.status = 200
    response.getheader.return_value = "identity"
    connection = Mock()
    connection.getresponse.return_value = response
    with (
        patch(
            "oxhack2026.research.network.public_addresses", return_value=("8.8.8.8",)
        ) as resolver,
        patch("http.client.HTTPSConnection", return_value=connection),
        patch("socket.create_connection") as connect,
        patch("ssl.create_default_context") as context,
    ):
        result = PinnedTransport().handle_request(
            httpx.Request("GET", "https://example.com/")
        )
        assert result.content == b"ok"
        resolver.assert_called_once_with("example.com", 5)
        assert connect.call_args.args == (("8.8.8.8", 443),)
        assert 14 < connect.call_args.kwargs["timeout"] <= 15
        context.return_value.wrap_socket.assert_called_once_with(
            connect.return_value, server_hostname="example.com"
        )


def _fetcher(tmp_path: Path, handler: httpx.MockTransport) -> Fetcher:
    return Fetcher(FileArtifactStore(tmp_path), Quotas(interval=0), handler)


def test_redirect_validation_and_credentials(tmp_path: Path) -> None:
    """Cross-host redirects discard provider credentials and never replay cookies."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "first.example":
            return httpx.Response(
                302,
                headers={
                    "location": "https://second.example/",
                    "set-cookie": "private=secret",
                },
            )
        return httpx.Response(200, content=b"public")

    fetcher = _fetcher(tmp_path, httpx.MockTransport(respond))
    capture, _ = fetcher.fetch(
        "https://first.example/?token=hidden", {"Authorization": "Bearer secret"}
    )
    assert "authorization" not in requests[-1].headers
    assert "cookie" not in requests[-1].headers
    assert "?" not in capture.url
    assert capture.artifact.byte_size == 6
    with pytest.raises(CollectionError, match="unsafe_url"):
        fetcher.fetch("http://127.0.0.1/")


def test_limits_and_deadline(tmp_path: Path) -> None:
    """Both captured-response limits and monotonic request deadlines are enforced."""
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 4194305)),
    )
    with pytest.raises(BudgetExceeded, match="response_size"):
        fetcher.fetch("https://example.com/")
    fetcher.deadline = time.monotonic() - 1
    with pytest.raises(BudgetExceeded, match="request_or_time"):
        fetcher.fetch("https://example.com/")


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://data.sec.gov/api/xbrl/companyfacts/CIK0001108524.json", True),
        ("https://data.sec.gov/submissions/CIK0001108524.json", False),
        (
            "https://data.sec.gov.evil.example/api/xbrl/companyfacts/CIK0001108524.json",
            False,
        ),
        ("https://data.sec.gov/api/xbrl/companyfacts/CIKwrong.json", False),
    ],
)
def test_larger_sec_facts_responses_keep_other_source_and_job_limits(
    tmp_path: Path, url: str, allowed: bool
) -> None:
    """A real-sized company-facts response gets a scoped limit, never unlimited I/O."""
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 4194305)),
    )
    if not allowed:
        with pytest.raises(BudgetExceeded, match="response_size"):
            fetcher.fetch(url)
        return
    capture, _ = fetcher.fetch(url)
    assert capture.artifact.byte_size == 4194305
    fetcher.byte_count = 33554432
    with pytest.raises(BudgetExceeded, match="capture_size"):
        fetcher.fetch(url)


def test_sec_facts_response_limit_remains_bounded(tmp_path: Path) -> None:
    """Even the larger SEC response allowance ends at sixteen MiB."""
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 16777217)),
    )
    with pytest.raises(BudgetExceeded, match="response_size"):
        fetcher.fetch("https://data.sec.gov/api/xbrl/companyfacts/CIK0001108524.json")


def _identity() -> Identity:
    return Identity(
        identity_id="identity",
        request=DiscoveryRequest(domain="example.com"),
        state="ready",
        requested_at=datetime.now(UTC),
        requested_domain="example.com",
        canonical_domain="example.com",
        company_name="Example",
        official_links=(
            "https://github.com/example/product",
            "https://www.npmjs.com/package/example",
        ),
    )


def test_extracts_claims_and_dates_without_inventing_metrics(tmp_path: Path) -> None:
    """Financial prose remains attributable evidence, with location and raw capture."""
    content = (
        b"<title>Example</title><p>We raised $10 million.</p>"
        b'<p>We raised $20 million.</p><time datetime="2026-01-01"></time>'
        b'<script type="application/ld+json">'
        b'{"@type":"Organization","name":"Example Inc"}</script>'
    )
    fetcher = _fetcher(
        tmp_path, httpx.MockTransport(lambda _: httpx.Response(200, content=content))
    )
    capture, body = fetcher.fetch("https://example.com/")
    page = parse_page(capture, body)
    assert len(page.claims) == 2
    assert {claim.attribution for claim in page.claims} == {"company_reported"}
    assert page.events[0].published_at == "2026-01-01"
    assert page.organizations == ("Example Inc",)
    assert all(item.capture_id == capture.capture_id for item in page.evidence)


def test_hn_nonexhaustive_retains_records_and_deduplicates(tmp_path: Path) -> None:
    """Non-exhaustive totals never erase matching records or manufacture complete
    counts."""
    stamp = int((datetime.now(UTC) - timedelta(days=1)).timestamp())

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "objectID": "123",
                        "url": "https://example.com/post",
                        "created_at_i": stamp,
                        "title": "Launch",
                    },
                    {
                        "objectID": "124",
                        "url": "https://notexample.com/",
                        "created_at_i": stamp,
                    },
                ],
                "nbPages": 2,
                "exhaustiveNbHits": False,
            },
        )

    fetcher = _fetcher(tmp_path, httpx.MockTransport(respond))
    result = Collector(
        fetcher, _identity(), SourceState(provider="hn", name="HN")
    ).collect()
    assert result.state == "partial"
    assert len(result.events) == 1
    assert result.observations[0].value == 1
    assert result.observations[1].value is None
    assert len(result.captures) == 2


def test_npm_adjacent_complete_windows(tmp_path: Path) -> None:
    """Daily adoption measurements retain their sixty-day window separately from
    today."""
    today = datetime.now(UTC).date()
    rows = [
        {"day": str(today - timedelta(days=index)), "downloads": index}
        for index in range(1, 61)
    ]
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(lambda _: httpx.Response(200, json={"downloads": rows})),
    )
    result = Collector(
        fetcher, _identity(), SourceState(provider="npm", name="npm")
    ).collect()
    assert [row.value for row in result.observations] == [
        sum(range(31, 61)),
        sum(range(1, 31)),
    ]
    previous, latest = result.observations
    assert previous.window and latest.window
    assert previous.window.end == latest.window.start
    assert latest.window.end < latest.collected_at


def test_unverified_accounts_skip_without_network(tmp_path: Path) -> None:
    """Name similarity cannot attach an external account."""
    handler = Mock(side_effect=AssertionError("Network must not run"))
    identity = _identity().model_copy(update={"official_links": ()})
    for provider in ("github", "npm", "hiring", "sec", "companies_house"):
        source = SourceState.model_validate({"provider": provider, "name": provider})
        result = Collector(
            _fetcher(tmp_path, httpx.MockTransport(handler)), identity, source
        ).collect()
        assert result.state == "skipped"
    handler.assert_not_called()


def _service(tmp_path: Path) -> V2Service:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            if request.url.path == "/sitemap.xml":
                return httpx.Response(404)
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b'<meta property="og:site_name" content="Example">'
                b"<p>Public company description. "
                + b"Product details. " * 30
                + b'</p><a href="https://github.com/example/product">Code</a>',
            )
        if request.url.host == "hn.algolia.com":
            return httpx.Response(
                200, json={"hits": [], "nbPages": 0, "exhaustiveNbHits": True}
            )
        return httpx.Response(503)

    service = V2Service(
        V2Store(tmp_path), Mock(spec=Executor), transport=httpx.MockTransport(respond)
    )
    service.quotas = Quotas(interval=0)
    return service


def test_standalone_api_confirmation_progress_and_independent_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Standalone research completes with fresh results despite independent
    provider failures."""
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_MAPPING_MODE", "rules")
    service = _service(tmp_path)
    app = create_app()
    app.dependency_overrides[get_v2_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/research-identities", json={"domain": "example.com"}
        )
        assert response.status_code == 202
        identifier = response.json()["identity_id"]
        assert (
            client.post(
                "/api/v2/research-jobs",
                json={"identity_id": identifier, "identity_confirmed": True},
            ).status_code
            == 409
        )
        service.run_discovery(identifier)
        assert (
            client.get(f"/api/v2/research-identities/{identifier}").json()[
                "company_name"
            ]
            == "Example"
        )
        request = {"identity_id": identifier, "identity_confirmed": True}
        queued = client.post("/api/v2/research-jobs", json=request).json()
        assert (
            client.post("/api/v2/research-jobs", json=request).json()["job_id"]
            == queued["job_id"]
        )
        service.run(queued["job_id"])
        finished = client.get(f"/api/v2/research-jobs/{queued['job_id']}").json()
        assert finished["state"] == "partial"
        assert [row["provider"] for row in finished["sources"]] == list(PROVIDERS)
        report = client.get(f"/api/v2/research-reports/{finished['report_id']}").json()
        assert report["identity"]["saved_context"] is None
        assert report["captures"] and report["evidence"]
        assert report["outlook"]["overall_outlook"] is None
        assert len(report["outlook"]["specialists"]) == 5
        assert len(report["outlook"]["forecasts"]) == 3
        assert client.get("/api/v1/health/live").status_code == 200


def test_queue_saturation_and_retry_after(tmp_path: Path) -> None:
    """Bounded admission rejects excess writes with a retry delay."""
    service = _service(tmp_path)
    for _ in range(10):
        service.discover(DiscoveryRequest(domain="example.com"))
    with pytest.raises(QueueFull):
        service.discover(DiscoveryRequest(domain="example.com"))
    app = create_app()
    app.dependency_overrides[get_v2_service] = lambda: service
    with TestClient(app) as client:
        result = client.post(
            "/api/v2/research-identities", json={"domain": "example.com"}
        )
        assert result.status_code == 429
        assert result.headers["retry-after"] == "30"


def test_identity_redirect_requires_destination_preview(tmp_path: Path) -> None:
    """Discovery never silently hides a different canonical destination."""
    service = _service(tmp_path)
    service.transport = httpx.MockTransport(
        lambda request: (
            httpx.Response(302, headers={"location": "https://destination.example/"})
            if request.url.host == "example.com"
            else httpx.Response(200, content=b"<title>Destination</title>")
        )
    )
    identity = service.discover(DiscoveryRequest(domain="example.com"))
    service.run_discovery(identity.identity_id)
    ready = service.store.identity(identity.identity_id)
    assert ready.canonical_domain == "destination.example"
    assert ready.conflicts


def test_disabled_capabilities_do_not_probe_vendors() -> None:
    """Unconfigured capabilities remain usable and make no collection claims."""
    with TestClient(create_app()) as client:
        result = client.get("/api/v2/research-capabilities")
        assert result.status_code == 200
        assert result.json()["worker_available"] is False
        assert result.json()["storage_available"] is False


def test_quotas_shared_across_jobs() -> None:
    """GitHub authentication limits and host backoff apply to every job using the
    gate."""
    quotas = Quotas(interval=0)
    quotas._github_requests = [time.monotonic()] * 60
    with pytest.raises(BudgetExceeded, match="github_hourly"):
        quotas.reserve("api.github.com", time.monotonic() + 1)
    quotas.reserve("api.github.com", time.monotonic() + 1, authenticated=True)
    quotas.defer("example.com", 60)
    with pytest.raises(BudgetExceeded, match="quota_deadline"):
        quotas.reserve("example.com", time.monotonic() + 1)


@pytest.mark.parametrize(
    "url,payload",
    [
        ("https://boards.greenhouse.io/example", {"jobs": [{"id": 1}, {"id": 2}]}),
        ("https://jobs.lever.co/example", [{"id": 1}, {"id": 2}]),
        ("https://jobs.ashbyhq.com/example", {"jobs": [{"id": 1}, {"id": 2}]}),
    ],
)
def test_verified_hiring_boards(tmp_path: Path, url: str, payload: object) -> None:
    """ATS counts refer to advertised positions on the explicitly linked board."""
    fetcher = _fetcher(
        tmp_path, httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    identity = _identity().model_copy(update={"official_links": (url,)})
    result = Collector(
        fetcher, identity, SourceState(provider="hiring", name="Hiring")
    ).collect()
    assert result.state == "completed"
    assert result.observations[0].value == 2
    assert "not headcount" in result.observations[0].definition


def test_github_stable_releases_and_zero_counts(tmp_path: Path) -> None:
    """Zero interest counts are valid and prerelease/draft records are excluded."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases"):
            return httpx.Response(
                200,
                json=[
                    {
                        "tag_name": "v1",
                        "html_url": "https://github.com/example/product/releases/v1",
                        "published_at": "2026-01-01T00:00:00Z",
                    },
                    {"tag_name": "draft", "draft": True},
                    {"tag_name": "prerelease", "prerelease": True},
                ],
            )
        return httpx.Response(200, json={"stargazers_count": 0, "open_issues_count": 0})

    result = Collector(
        _fetcher(tmp_path, httpx.MockTransport(respond)),
        _identity(),
        SourceState(provider="github", name="GitHub"),
    ).collect()
    assert [row.value for row in result.observations] == [0, 0]
    assert [row.title for row in result.events] == ["v1"]


def test_conflicting_npm_days_are_not_normalized(tmp_path: Path) -> None:
    """Conflicting daily records remain captured and never silently select a value."""
    day = str(datetime.now(UTC).date() - timedelta(days=1))
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "downloads": [
                    {"day": day, "downloads": 1},
                    {"day": day, "downloads": 2},
                ]
            },
        )
    )
    result = Collector(
        _fetcher(tmp_path, transport),
        _identity(),
        SourceState(provider="npm", name="npm"),
    ).collect()
    assert result.state == "partial"
    assert not result.observations
    assert result.captures
    assert "conflicting_or_negative_npm_daily_downloads" in result.reason_codes


def test_dns_revalidated_for_each_connection() -> None:
    """A later private DNS answer cannot reuse an earlier public validation."""
    public = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    private = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    with patch("socket.getaddrinfo", side_effect=[[public], [private]]):
        assert public_addresses("example.com") == ("8.8.8.8",)
        with pytest.raises(CollectionError):
            public_addresses("example.com")


def test_private_redirect_rejected_at_transport(tmp_path: Path) -> None:
    """Validate a redirect destination before opening another socket."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"location": "https://169.254.169.254/"})
        return PinnedTransport().handle_request(request)

    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]
    with (
        patch("socket.getaddrinfo", return_value=answers),
        patch("socket.create_connection") as connect,
    ):
        with pytest.raises(CollectionError, match="private_destination"):
            _fetcher(tmp_path, httpx.MockTransport(respond)).fetch(
                "https://example.com/"
            )
        connect.assert_not_called()


def test_browser_attempt_limit_includes_failures(tmp_path: Path) -> None:
    """Failed browser navigations still consume the three-attempt budget."""
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"<title>Sparse</title>")
        ),
    )
    capture, content = fetcher.fetch("https://example.com/")
    collector = Collector(
        fetcher, _identity(), SourceState(provider="website", name="Website"), True
    )
    with patch(
        "oxhack2026.research.browser.render",
        side_effect=CollectionError("browser_unavailable"),
    ) as renderer:
        for _ in range(3):
            with pytest.raises(CollectionError):
                collector._website_page(capture, content)
        collector._website_page(capture, content)
        assert renderer.call_count == 3


def test_potential_claim_conflicts_are_retained(tmp_path: Path) -> None:
    """A report links potentially conflicting claims and keeps both excerpts."""
    from oxhack2026.api.research_v2_schemas import Claim
    from oxhack2026.research.composition import compose

    service = _service(tmp_path)
    preview = service.discover(DiscoveryRequest(domain="example.com"))
    service.run_discovery(preview.identity_id)
    job = service.create(
        JobRequest(identity_id=preview.identity_id, identity_confirmed=True)
    )
    identity = service.store.identity(preview.identity_id)
    support = identity.evidence[0]
    claims = tuple(
        Claim(
            claim_id=identifier,
            text=text,
            category="ARR",
            attribution="company_reported",
            evidence_ids=(support.evidence_id,),
        )
        for identifier, text in (
            ("a", "ARR was $1 million"),
            ("b", "ARR was $2 million"),
        )
    )
    sources = (job.sources[0].model_copy(update={"claims": claims}), *job.sources[1:])
    report = compose(job.model_copy(update={"sources": sources}), identity)
    assert report.claims[0].conflicts_with == ("b",)
    assert report.claims[1].conflicts_with == ("a",)


@pytest.mark.parametrize("provider", ["sec", "companies_house"])
def test_reviewed_registry_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    """Exact reviewed identifiers gate registry facts and retain declared periods."""
    from unittest.mock import mock_open

    import orjson

    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS", "reviewed.json")
    monkeypatch.setenv("SEC_USER_AGENT", "Fixture contact research@example.invalid")
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "fixture-key")
    mapping = [
        {
            "domain": "example.com",
            "jurisdiction": "US" if provider == "sec" else "UK",
            "evidence_url": "https://example.com/legal",
            "reviewed": True,
            "cik": "123",
            "company_number": "01234567",
        }
    ]
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "cik": 123,
                    "name": "Example Legal",
                    "company_status": "active",
                    "accounts": {"period_end": "2025-12-31"},
                },
            )
        ),
    )
    source = SourceState.model_validate({"provider": provider, "name": provider})
    with patch(
        "oxhack2026.research.registry.open",
        mock_open(read_data=orjson.dumps(mapping)),
        create=True,
    ):
        result = Collector(fetcher, _identity(), source).collect()
    assert result.state == "partial"
    assert len(result.captures) == 3
    assert any("2025-12-31" in claim.text for claim in result.claims)
    assert all(claim.attribution == "registry" for claim in result.claims)


@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "foreign_page",
        "missing_page",
        "malformed_page",
        "oversized_manifest",
        "wrong_cik",
    ],
)
def test_sec_history_retains_pages_and_rejects_incomplete_model_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Pagination stays on the verified CIK and a failed page preserves other facts."""
    from unittest.mock import mock_open

    import orjson

    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS", "reviewed.json")
    monkeypatch.setenv("SEC_USER_AGENT", "Fixture research@example.invalid")
    mapping = [
        {
            "domain": "example.com",
            "jurisdiction": "US",
            "reviewed": True,
            "evidence_url": "https://example.com/legal",
            "cik": "123",
        }
    ]
    name = "CIK0000000123-submissions-001.json"
    references = [{"name": name}]
    if failure == "foreign_page":
        references = [{"name": "https://other.example/private.json"}]
    elif failure == "oversized_manifest":
        references = [
            {"name": f"CIK0000000123-submissions-{n:03}.json"} for n in range(9)
        ]
    recent = {
        "form": ["10-K"],
        "filingDate": ["2025-02-01"],
        "reportDate": ["2024-12-31"],
    }
    history = {
        "form": ["10-K"],
        "filingDate": ["2024-02-01"],
        "reportDate": ["2023-12-31"],
    }

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(200, text="Example legal identity")
        if request.url.path.endswith(f"/{name}"):
            if failure == "malformed_page":
                return httpx.Response(200, text="not JSON")
            return httpx.Response(
                503 if failure == "missing_page" else 200, json=history
            )
        if "companyfacts" in request.url.path:
            return httpx.Response(200, json={"cik": 123, "name": "Example Legal"})
        return httpx.Response(
            200,
            json={
                "cik": 124 if failure == "wrong_cik" else 123,
                "name": "Example Legal",
                "filings": {"recent": recent, "files": references},
            },
        )

    fetcher = _fetcher(tmp_path, httpx.MockTransport(respond))
    with patch(
        "oxhack2026.research.registry.open",
        mock_open(read_data=orjson.dumps(mapping)),
        create=True,
    ):
        result = Collector(
            fetcher, _identity(), SourceState(provider="sec", name="SEC")
        ).collect()
    assert result.state == "partial"
    assert not result.observations
    if failure == "none":
        assert "sec_annual_timing_inputs_validated" in result.reason_codes
        assert len(result.captures) == 4
    else:
        assert "sec_annual_timing_inputs_validated" not in result.reason_codes
    if failure == "wrong_cik":
        assert "sec_cik_mismatch" in result.reason_codes
        assert not result.claims
    else:
        assert any("Example Legal" in claim.text for claim in result.claims)
    assert all("other.example" not in capture.url for capture in result.captures)


@pytest.mark.parametrize("missing_cash_flow", [False, True])
def test_sec_research_inference_uses_original_financial_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_cash_flow: bool
) -> None:
    """A verified CIK yields an evidenced estimate; missing cash flow stays missing."""
    from unittest.mock import mock_open

    import orjson

    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS", "reviewed.json")
    monkeypatch.setenv("SEC_USER_AGENT", "Fixture research@example.invalid")
    accession = "0000000123-26-000001"
    mapping = [
        {
            "domain": "example.com",
            "jurisdiction": "US",
            "reviewed": True,
            "evidence_url": "https://example.com/legal",
            "cik": "123",
        }
    ]
    concepts = {
        "Revenues": 100_000_000,
        "Assets": 150_000_000,
        "NetCashProvidedByUsedInOperatingActivities": 10_000_000,
    }
    facts = {
        name: {
            "units": {
                "USD": [
                    {
                        "accn": accession,
                        "form": "10-K",
                        "filed": "2026-02-01",
                        "end": "2025-12-31",
                        "val": value,
                        **({"start": "2025-01-01"} if name != "Assets" else {}),
                    }
                ]
            }
        }
        for name, value in concepts.items()
        if not (
            missing_cash_flow and name == "NetCashProvidedByUsedInOperatingActivities"
        )
    }

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            assert request.headers["user-agent"] != "Fixture research@example.invalid"
            return httpx.Response(200, text="Example legal identity")
        if "companyfacts" in request.url.path:
            return httpx.Response(200, json={"cik": 123, "facts": {"us-gaap": facts}})
        return httpx.Response(
            200,
            json={
                "cik": 123,
                "name": "Example Legal",
                "filings": {
                    "recent": {
                        "form": ["10-K"],
                        "filingDate": ["2026-02-01"],
                        "reportDate": ["2025-12-31"],
                        "accessionNumber": [accession],
                    },
                    "files": [],
                },
            },
        )

    fetcher = _fetcher(tmp_path, httpx.MockTransport(respond))
    with patch(
        "oxhack2026.research.registry.open",
        mock_open(read_data=orjson.dumps(mapping)),
        create=True,
    ):
        result = Collector(
            fetcher, _identity(), SourceState(provider="sec", name="SEC")
        ).collect()
    estimate = result.cash_flow_research
    if missing_cash_flow:
        assert estimate is None
        assert (
            "sec_model_requires_origin_revenue_cash_flow_and_assets"
            in result.reason_codes
        )
    else:
        assert estimate is not None
        assert estimate.status == "research_estimate"
        assert estimate.accession_number == accession
        assert 0 <= estimate.probability <= 1
        assert len(estimate.evidence_ids) == 3
        assert set(estimate.evidence_ids) <= {
            item.evidence_id for item in result.evidence
        }
        assert "experimental_cash_flow_research_model_ran" in result.reason_codes
    assert len(result.captures) == 3


def test_xml_entity_declarations_blocked(tmp_path: Path) -> None:
    """XML cannot resolve external entities around the controlled network boundary."""
    body = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>'
    fetcher = _fetcher(
        tmp_path,
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=body, headers={"content-type": "application/xml"}
            )
        ),
    )
    capture, content = fetcher.fetch("https://example.com/sitemap.xml")
    with pytest.raises(CollectionError, match="xml_doctype"):
        parse_page(capture, content)
