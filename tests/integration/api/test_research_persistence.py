"""Durable API research with real storage, mocked HTTP and retained test outputs."""

from concurrent.futures import Executor
from pathlib import Path
from unittest.mock import create_autospec, patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.app import create_app
from oxhack2026.api.company_repository import PublishedCompanyRepository
from oxhack2026.api.routes.research import get_research_service
from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.research.service import ResearchService
from oxhack2026.research.store import LocalResearchStore
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore
from oxhack2026.storage.contracts import ArtifactStore

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("truncated", [False, True])
def test_research_api_persistence_raw_integrity_and_saved_links(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
    truncated: bool,
) -> None:
    """Real durable transitions survive reopen; raw corruption produces a safe 503."""
    source, artifacts = company_source
    root = Path("tests/outputs/research-api") / uuid4().hex
    sources = LocalCompanyStore(root)
    for evidence in source.evidence:
        reference = evidence.raw_artifact
        sources.artifacts.write(artifacts.read(reference), reference.media_type)
    sources.publish(source, None)
    models = LocalCompanyAssessmentStore(root)
    models.publish("research-context", company_assessments, None)
    repository = PublishedCompanyRepository(sources, models, ("research-context",))
    saved = repository.company("research-context", "alpha")
    before = saved.model_dump_json(), source.model_dump_json()
    store = LocalResearchStore(root)
    service = ResearchService(
        repository, sources, store, create_autospec(Executor, instance=True)
    )
    app = create_app(company_repository=repository)
    app.dependency_overrides[get_research_service] = lambda: service
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "hn.algolia.com"
        assert request.url.params["query"] == "alpha.example"
        assert request.url.params["hitsPerPage"] == "100"
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "hits": [],
                "nbHits": 150 if truncated else 0,
                "nbPages": 2 if truncated else 0,
            },
        )

    with TestClient(app) as client:
        queued = client.post(
            "/api/v1/research-jobs",
            json={
                "assessment_publication_id": "research-context",
                "company_id": "alpha",
                "domain": "alpha.example",
                "identity_confirmed": True,
            },
        )
        assert queued.status_code == 202
        assert queued.json()["state"] == "queued"
        job_id = queued.json()["job_id"]
        provider = httpx.Client(transport=httpx.MockTransport(respond))
        with patch("oxhack2026.research.service.httpx.Client", return_value=provider):
            service.run(job_id)
        finished = client.get(f"/api/v1/research-jobs/{job_id}").json()
        assert finished["state"] == ("partial" if truncated else "completed")
        report_id = finished["report_id"]
        response = client.get(f"/api/v1/research-reports/{report_id}")
        assert response.status_code == 200
        report_bytes = response.content
        payload = response.json()
        assert payload["inventory"]["observations"][0]["value"] == (
            None if truncated else 0
        )
        assert payload["outlook"]["overall_outlook"] is None
        assert len(payload["outlook"]["specialists"]) == 5
        assert len(requests) == 1
        assert (
            client.get(
                "/api/v1/company-snapshots/research-context/companies/alpha"
            ).status_code
            == 200
        )
    reopened = LocalResearchStore(root)
    assert reopened.job(job_id).state == finished["state"]
    assert reopened.report(report_id).model_dump_json().encode() == report_bytes
    assert (
        repository.company("research-context", "alpha").model_dump_json(),
        sources.snapshot(source.snapshot_id).model_dump_json(),
    ) == before
    with pytest.raises(ValueError, match="transition"):
        reopened.save_job(reopened.job(job_id))
    digest = payload["inventory"]["capture_sha256"]
    (root / "objects" / digest[:2] / digest).write_bytes(b"corrupt source")
    with TestClient(app) as client:
        corrupt = client.get(f"/api/v1/research-reports/{report_id}")
    assert corrupt.status_code == 503
    assert str(root) not in corrupt.text
