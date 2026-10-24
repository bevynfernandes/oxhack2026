"""Durable v2 acceptance; local services mocked unless live acceptance is opted in."""

import os
from concurrent.futures import Executor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import httpx
import orjson
import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.company_runtime import create_company_app
from oxhack2026.api.research_v2_schemas import DiscoveryRequest, JobRequest
from oxhack2026.research.browser import browser_available, render
from oxhack2026.research.network import Fetcher, Quotas
from oxhack2026.research.v2_service import V2Service
from oxhack2026.research.v2_store import V2Store
from oxhack2026.storage.artifacts import FileArtifactStore

pytestmark = pytest.mark.integration


def _service(root: Path) -> V2Service:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(
                200,
                content=b"<title>Example</title><p>Public company information.</p>"
                * 10,
            )
        if request.url.host == "hn.algolia.com":
            return httpx.Response(
                200, json={"hits": [], "nbPages": 0, "exhaustiveNbHits": True}
            )
        return httpx.Response(503)

    service = V2Service(
        V2Store(root), Mock(spec=Executor), transport=httpx.MockTransport(respond)
    )
    service.quotas = Quotas(interval=0)
    return service


def _confirmed(service: V2Service, domain: str = "example.com") -> JobRequest:
    preview = service.discover(DiscoveryRequest(domain=domain))
    service.run_discovery(preview.identity_id)
    ready = service.store.identity(preview.identity_id)
    assert ready.state == "ready"
    assert ready.canonical_domain == domain
    return JobRequest(identity_id=preview.identity_id, identity_confirmed=True)


def test_refresh_immutable_capture_integrity_and_disabled_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refresh publishes new bytes while the previous report and captures stay
    exact."""
    service = _service(tmp_path)
    request = _confirmed(service)
    first = service.create(request)
    service.run(first.job_id)
    report_id = service.store.job(first.job_id).report_id
    assert report_id
    report = service.store.report(report_id)
    previous_bytes = report.model_dump_json().encode()
    second = service.create(request)
    service.run(second.job_id)
    refreshed_id = service.store.job(second.job_id).report_id
    assert refreshed_id and refreshed_id != report_id
    refreshed = service.store.report(refreshed_id)
    assert refreshed.researched_at > report.researched_at
    assert service.store.report(report_id).model_dump_json().encode() == previous_bytes
    assert refreshed.captures[-1].collected_at > report.captures[-1].collected_at
    with pytest.raises(ValueError, match="immutable"):
        service.store.publish(
            report.model_copy(update={"limitations": ("replacement",)})
        )
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_ROOT", str(tmp_path))
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_ENABLED", "0")
    monkeypatch.delenv("SIGNALSHIFT_COMPANY_ROOT", raising=False)
    monkeypatch.delenv("SIGNALSHIFT_COMPANY_PUBLICATIONS", raising=False)
    with TestClient(create_company_app()) as client:
        assert client.get(f"/api/v2/research-reports/{report_id}").status_code == 200
        assert (
            client.get("/api/v2/research-capabilities").json()["collection_enabled"]
            is False
        )
        assert (
            client.post("/api/v2/research-jobs", json=request.model_dump()).status_code
            == 503
        )
    reference = report.captures[0].artifact
    (tmp_path / reference.path).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        service.store.report(report_id)


def test_recovery_preserves_completed_collectors(tmp_path: Path) -> None:
    """Recovery interrupts unfinished work while retaining useful completed
    checkpoints."""
    from oxhack2026.research.collectors import Collector

    service = _service(tmp_path)
    job = service.create(_confirmed(service))
    started = job.model_copy(
        update={"state": "running", "started_at": datetime.now(UTC)}
    )
    service.store.save_job(started)
    source = started.sources[0].model_copy(
        update={"state": "running", "started_at": datetime.now(UTC)}
    )
    completed = Collector(
        service._fetcher(), service.store.identity(job.identity_id), source
    ).collect()
    checkpoint = started.model_copy(
        update={"sources": (completed, *started.sources[1:])}
    )
    service.store.save_job(checkpoint)
    service.recover()
    recovered = service.store.job(job.job_id)
    assert recovered.state == "partial"
    assert recovered.sources[0] == completed
    assert all(row.state == "failed" for row in recovered.sources[1:])
    assert recovered.report_id
    assert service.store.report(recovered.report_id).evidence


def test_browser_renders_saved_javascript_fixture(tmp_path: Path) -> None:
    """Chromium renders a saved fixture while all requests use the controlled
    fetcher."""
    assert browser_available(), "Install Chromium before browser acceptance"
    fixture = Path("tests/fixtures/research/javascript.html").read_bytes()
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, content=fixture, headers={"content-type": "text/html"}
        )

    fetcher = Fetcher(
        FileArtifactStore(tmp_path), Quotas(interval=0), httpx.MockTransport(respond)
    )
    capture, content = render(fetcher, "https://fixture.example/")
    assert capture.rendered
    assert b"Public product content rendered by JavaScript." in content
    assert all("cookie" not in request.headers for request in requests)
    assert FileArtifactStore(tmp_path).read(capture.artifact) == content


@pytest.mark.skipif(
    os.environ.get("SIGNALSHIFT_LIVE_RESEARCH_ACCEPTANCE") != "1",
    reason="Explicit live research opt-in required",
)
def test_real_startup_acceptance() -> None:
    """Retain genuine captures for three standalone domains and an immutable refresh."""
    root = Path("tests/outputs") / datetime.now(UTC).strftime(
        "research-live-%Y%m%dT%H%M%S"
    )
    root.mkdir(parents=True)
    service = V2Service(V2Store(root), Mock(spec=Executor))
    rows: list[dict[str, object]] = []
    for domain in ("qdrant.tech", "posthog.com", "linear.app"):
        request = _confirmed(service, domain)
        job = service.create(request)
        service.run(job.job_id)
        finished = service.store.job(job.job_id)
        assert finished.report_id, f"No useful fresh evidence for {domain}"
        report = service.store.report(finished.report_id)
        assert report.identity.saved_context is None
        assert report.sources[0].evidence, f"No fresh website evidence for {domain}"
        assert all(
            source.state not in {"pending", "running"} for source in report.sources
        )
        rows.append(
            {
                "domain": domain,
                "job_id": job.job_id,
                "report_id": report.report_id,
                "state": finished.state,
                "captures": len(report.captures),
                "sources": [
                    {
                        "provider": source.provider,
                        "state": source.state,
                        "reasons": source.reason_codes,
                    }
                    for source in report.sources
                ],
            }
        )
        if domain == "linear.app":
            previous = report.model_dump_json().encode()
            refresh = service.create(request)
            service.run(refresh.job_id)
            refreshed_id = service.store.job(refresh.job_id).report_id
            assert refreshed_id and refreshed_id != report.report_id
            assert (
                service.store.report(refreshed_id).researched_at > report.researched_at
            )
            assert (
                service.store.report(report.report_id).model_dump_json().encode()
                == previous
            )
            rows.append(
                {"refresh_job_id": refresh.job_id, "refresh_report_id": refreshed_id}
            )
    (root / "acceptance.json").write_bytes(
        orjson.dumps(rows, option=orjson.OPT_INDENT_2)
    )
