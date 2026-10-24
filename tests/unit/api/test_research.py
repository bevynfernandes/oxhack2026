"""Research identity, provenance, bounded collection and real state transitions."""

from concurrent.futures import Executor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, create_autospec, patch

import httpx
import orjson
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from oxhack2026.api.app import create_app
from oxhack2026.api.company_repository import PublishedCompanyRepository
from oxhack2026.api.company_schemas import CompanyDetail
from oxhack2026.api.repository import RepositoryUnavailable, ResourceNotFound
from oxhack2026.api.research_schemas import (
    ResearchJob,
    ResearchReport,
    ResearchRequest,
    ResearchSourceState,
)
from oxhack2026.api.routes.research import get_research_service
from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.catalog.schemas import TimeWindow
from oxhack2026.ingest.capture import CaptureRequest, HttpCapture
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.research.attention import (
    AttentionCapture,
    AttentionQuery,
    collect_attention,
)
from oxhack2026.research.report import build_report
from oxhack2026.research.service import IdentityConfirmationRequired, ResearchService
from oxhack2026.research.store import LocalResearchStore
from oxhack2026.storage.company import CompanySourceReader
from oxhack2026.storage.company_assessments import (
    CompanyAssessmentManifest,
    CompanyAssessmentReader,
)
from oxhack2026.storage.contracts import ArtifactReference

NOW = datetime(2026, 10, 24, 17, tzinfo=UTC)
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/api/companies.json"
REQUEST = ResearchRequest(
    assessment_publication_id="synthetic-assessments-v1",
    company_id="alpha",
    domain="alpha.example",
    identity_confirmed=True,
)


@pytest.fixture
def context() -> tuple[CompanySourceSnapshot, CompanyDetail]:
    """Compose public context through real mapping with mocked storage readers."""
    payload = orjson.loads(FIXTURE.read_bytes())
    source = CompanySourceSnapshot.model_validate(payload["source"])
    sources = create_autospec(CompanySourceReader, instance=True)
    sources.snapshot.return_value = source
    models = create_autospec(CompanyAssessmentReader, instance=True)
    models.manifest.return_value = CompanyAssessmentManifest.model_validate(
        payload["publication"]
    )
    models.assessments.return_value = tuple(
        CompanyAssessment.model_validate(row) for row in payload["assessments"]
    )
    repository = PublishedCompanyRepository(
        sources, models, (REQUEST.assessment_publication_id,)
    )
    return source, repository.company(REQUEST.assessment_publication_id, "alpha")


def _job() -> ResearchJob:
    return ResearchJob(
        job_id="synthetic-job",
        request=REQUEST,
        state="queued",
        requested_at=NOW - timedelta(minutes=1),
        sources=(ResearchSourceState(state="pending"),),
    )


def _capture(payload: dict[str, object]) -> AttentionCapture:
    content = orjson.dumps(payload)
    reference = ArtifactReference(
        path="objects/aa/fixture",
        sha256="a" * 64,
        byte_size=len(content),
        media_type="application/octet-stream",
    )
    captured = HttpCapture(
        request=CaptureRequest(url="https://hn.algolia.com/api/v1/search_by_date"),
        collected_at=NOW,
        artifact=reference,
        has_next_page=False,
    )
    query = AttentionQuery(
        "alpha", "alpha.example", TimeWindow(start=NOW - timedelta(days=30), end=NOW)
    )
    with (
        patch("oxhack2026.research.attention.capture_get", return_value=captured),
        patch("oxhack2026.research.attention.FileArtifactStore") as artifacts,
        httpx.Client(transport=httpx.MockTransport(Mock())) as client,
    ):
        artifacts.return_value.read.return_value = content
        return collect_attention(query, client, Path("mock"), "synthetic-job")


def _service(saved: CompanyDetail) -> ResearchService:
    repository = Mock()
    repository.company.return_value = saved
    store = create_autospec(LocalResearchStore, instance=True)
    store.root = Path("mock")
    return ResearchService(
        repository,
        create_autospec(CompanySourceReader, instance=True),
        store,
        create_autospec(Executor, instance=True),
    )


@pytest.mark.parametrize("confirmation", [False, 1, "true", None])
def test_confirmation_is_explicit_boolean(confirmation: object) -> None:
    """Coercion cannot manufacture an identity confirmation."""
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(
            REQUEST.model_dump() | {"identity_confirmed": confirmation}
        )


@pytest.mark.parametrize("domain", ["https://alpha.example", "a/b", "ALPHA.example"])
def test_domains_are_bare_normalized_identities(domain: str) -> None:
    """Domains are confirmed identifiers rather than arbitrary fetch destinations."""
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(REQUEST.model_dump() | {"domain": domain})


def test_exact_domain_counts_exclude_lookalikes_and_outside_window() -> None:
    """Only exact-domain URL hosts within the measured interval count."""
    urls = [
        "https://alpha.example/a",
        "https://www.alpha.example/b",
        "https://alpha.example.attacker.test",
        "https://other.test/?url=alpha.example",
        "https://blog.alpha.example/a",
        "https://alpha.example/future",
    ]
    hits = [
        {
            "objectID": str(index),
            "url": url,
            "created_at_i": int(NOW.timestamp()) - 1
            if index < 5
            else int(NOW.timestamp()),
        }
        for index, url in enumerate(urls)
    ]

    captured = _capture({"hits": hits, "nbHits": 6, "nbPages": 1})

    assert captured.complete is True
    assert captured.observation.value == 2
    assert captured.observation.available_at == NOW
    assert captured.observation.window_end_exclusive is True
    assert captured.evidence.raw_artifact.sha256 == "a" * 64


@pytest.mark.parametrize(
    "metadata,expected",
    [
        ({"nbHits": 0, "nbPages": 0}, 0),
        ({"nbHits": 150, "nbPages": 2}, None),
        ({"nbHits": 0, "nbPages": 1, "exhaustiveNbHits": False}, None),
    ],
)
def test_incomplete_queries_are_missing_not_zero(
    metadata: dict[str, object], expected: int | None
) -> None:
    """Pagination/truncation cannot turn a lower bound into a complete count."""
    captured = _capture({"hits": [], **metadata})

    assert captured.observation.value == expected
    assert captured.complete == (expected is not None)
    assert captured.observation.state == (
        "observed" if expected is not None else "missing"
    )


def test_duplicate_provider_ids_fail() -> None:
    """Duplicate page records are rejected instead of silently changing counts."""
    hit = {"objectID": "same", "url": None, "created_at_i": 1}

    with pytest.raises(ValueError, match="duplicate"):
        _capture({"hits": [hit, hit], "nbHits": 2, "nbPages": 1})


def test_report_preserves_saved_bytes_and_resolves_new_inventory(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """Fresh evidence is separately scoped; all models remain explicitly null."""
    source, saved = context
    before = source.model_dump_json(), saved.model_dump_json()
    captured = _capture({"hits": [], "nbHits": 0, "nbPages": 0})

    report = build_report(_job(), saved, source, captured)

    assert (source.model_dump_json(), saved.model_dump_json()) == before
    assert report.source_publication_id == source.snapshot_id
    assert report.inventory.saved_context == saved
    assert report.outlook.source_snapshot_id == report.inventory.inventory_id
    assert report.outlook.source_snapshot_id != source.snapshot_id
    assert report.outlook.as_of == NOW
    assert report.inventory.synthetic is True
    assert report.outlook.overall_outlook is None
    assert len(report.outlook.specialists) == 5
    assert all(row.prediction is None for row in report.outlook.specialists)
    assert report.outlook.forecasts is not None
    assert [row.horizon_months for row in report.outlook.forecasts] == [24, 24, 12]
    assert all(row.prediction is None for row in report.outlook.forecasts)
    attention = report.outlook.specialists[1]
    assert attention.data_status == "available"
    assert attention.metric_observation_ids == (captured.observation.observation_id,)
    assert report.inventory.capture_sha256 == captured.evidence.raw_artifact.sha256
    assert ResearchReport.model_validate_json(report.model_dump_json()) == report
    assert "raw_artifact" not in report.model_dump_json()


def test_legacy_report_round_trip_preserves_original_payload(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """An immutable pre-forecast report remains byte-identical after validation."""
    source, saved = context
    report = build_report(
        _job(), saved, source, _capture({"hits": [], "nbHits": 0, "nbPages": 0})
    )
    original_bytes = report.model_dump_json(exclude={"outlook": {"forecasts"}})

    loaded = ResearchReport.model_validate_json(original_bytes)

    assert loaded.outlook.forecasts is None
    assert loaded.model_dump_json() == original_bytes


@pytest.mark.parametrize("company", ["observation", "evidence"])
def test_cross_company_fresh_capture_is_rejected(
    context: tuple[CompanySourceSnapshot, CompanyDetail], company: str
) -> None:
    """Fresh references may never be transplanted from a different company."""
    source, saved = context
    captured = _capture({"hits": [], "nbHits": 0, "nbPages": 0})
    observation = captured.observation
    evidence = captured.evidence
    if company == "observation":
        observation = observation.model_copy(update={"company_id": "beta"})
    else:
        evidence = evidence.model_copy(update={"company_id": "beta"})

    with pytest.raises(ValueError, match="identity"):
        build_report(
            _job(), saved, source, AttentionCapture(observation, evidence, True)
        )


def test_queue_does_no_collection_and_rejects_wrong_identity(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """A confirmed saved match queues once; unknown/mismatched identities do not."""
    _, saved = context
    service = _service(saved)

    queued = service.create(REQUEST)

    assert queued.state == "queued"
    service.executor.submit.assert_called_once_with(service.run, queued.job_id)  # type: ignore[attr-defined]
    service.sources.snapshot.assert_not_called()  # type: ignore[attr-defined]
    service.store.save_job.assert_called_once_with(queued)  # type: ignore[attr-defined]
    with pytest.raises(IdentityConfirmationRequired):
        service.create(REQUEST.model_copy(update={"domain": "wrong.example"}))
    service.repository.company.side_effect = ResourceNotFound  # type: ignore[attr-defined]
    with pytest.raises(IdentityConfirmationRequired):
        service.create(REQUEST)


@pytest.mark.parametrize("complete", [True, False])
def test_worker_records_actual_state_and_report(
    context: tuple[CompanySourceSnapshot, CompanyDetail], complete: bool
) -> None:
    """Worker records running then completed/partial only after durable publication."""
    source, saved = context
    service = _service(saved)
    service.store.job.return_value = _job()  # type: ignore[attr-defined]
    service.sources.snapshot.return_value = source  # type: ignore[attr-defined]
    captured = _capture(
        {"hits": [], "nbHits": 0 if complete else 200, "nbPages": 0 if complete else 2}
    )
    with (
        patch("oxhack2026.research.service.collect_attention", return_value=captured),
        patch("oxhack2026.research.service.datetime") as clock,
    ):
        clock.now.return_value = NOW
        service.run("synthetic-job")

    states = [call.args[0] for call in service.store.save_job.call_args_list]  # type: ignore[attr-defined]
    assert [row.state for row in states] == [
        "running",
        "completed" if complete else "partial",
    ]
    assert states[-1].report_id == "report-synthetic-job"
    service.store.publish.assert_called_once()  # type: ignore[attr-defined]


def test_worker_failure_is_durable_and_redacted(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provider exceptions become real failed state without exposing private values."""
    source, saved = context
    service = _service(saved)
    service.store.job.return_value = _job()  # type: ignore[attr-defined]
    service.sources.snapshot.return_value = source  # type: ignore[attr-defined]
    with patch(
        "oxhack2026.research.service.collect_attention",
        side_effect=RuntimeError("private-token"),
    ):
        service.run("synthetic-job")

    failed = service.store.save_job.call_args.args[0]  # type: ignore[attr-defined]
    assert failed.state == "failed"
    assert failed.report_id is None
    assert "private-token" not in caplog.text
    service.store.publish.assert_not_called()  # type: ignore[attr-defined]


def test_recovery_resumes_queued_and_marks_interrupted_running(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """Restart does not invent a report or re-run an interrupted collection."""
    service = _service(context[1])
    queued = _job()
    running = queued.model_copy(
        update={"job_id": "interrupted", "state": "running", "started_at": NOW}
    )
    service.store.jobs.return_value = (queued, running)  # type: ignore[attr-defined]

    service.recover()

    service.executor.submit.assert_called_once_with(service.run, queued.job_id)  # type: ignore[attr-defined]
    failed = service.store.save_job.call_args.args[0]  # type: ignore[attr-defined]
    assert failed.job_id == "interrupted"
    assert failed.state == "failed"
    assert failed.reason_codes == ("worker_interrupted",)


def test_routes_disabled_errors_and_no_implicit_work(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """Unconfigured workers and safe errors are explicit; reads never collect."""
    with TestClient(create_app()) as client:
        assert (
            client.post("/api/v1/research-jobs", json=REQUEST.model_dump()).status_code
            == 503
        )
    service = _service(context[1])
    app = create_app()
    app.dependency_overrides[get_research_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/research-jobs", json=REQUEST.model_dump())
        assert response.status_code == 202
        service.store.job.return_value = _job()  # type: ignore[attr-defined]
        assert client.get("/api/v1/research-jobs/synthetic-job").status_code == 200
        service.store.job.side_effect = KeyError("private-path")  # type: ignore[attr-defined]
        missing = client.get("/api/v1/research-jobs/unknown")
        assert missing.status_code == 404
        service.store.job.side_effect = ValueError("private-path")  # type: ignore[attr-defined]
        corrupt = client.get("/api/v1/research-jobs/synthetic-job")
        assert corrupt.status_code == 503
        assert "private-path" not in missing.text + corrupt.text
        mismatch = client.post(
            "/api/v1/research-jobs",
            json=REQUEST.model_dump() | {"domain": "wrong.example"},
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["code"] == "identity_confirmation_required"


def test_executor_rejection_records_failure(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """An unavailable local worker cannot leave an accepted job silently queued."""
    service = _service(context[1])
    service.executor.submit.side_effect = RuntimeError("closed")  # type: ignore[attr-defined]

    with pytest.raises(RepositoryUnavailable):
        service.create(REQUEST)

    assert service.store.save_job.call_args.args[0].state == "failed"  # type: ignore[attr-defined]


@pytest.mark.parametrize("state", ["running", "completed", "partial", "failed"])
def test_contradictory_job_state_is_rejected(state: str) -> None:
    """Queued timestamps and source metadata cannot masquerade as actual progress."""
    with pytest.raises(ValidationError):
        ResearchJob.model_validate(_job().model_dump() | {"state": state})


def test_structured_capture_queries_are_provider_scoped() -> None:
    """Structured parameters cannot fetch another host or store arbitrary secrets."""
    with pytest.raises(ValidationError):
        CaptureRequest(
            url="https://example.com",
            query_parameters=(("query", "alpha.example"),),
        )
    with pytest.raises(ValidationError):
        CaptureRequest.model_validate(
            {
                "url": "https://hn.algolia.com/api/v1/search_by_date",
                "query_parameters": (("api_key", "private-value"),),
            }
        )


def test_job_storage_has_bounded_reads_and_safe_identity() -> None:
    """Mocked filesystem reads reject absent, oversized and mismatched job data."""
    store = LocalResearchStore(Path("mock"))
    with (
        patch.object(Path, "open", side_effect=FileNotFoundError),
        pytest.raises(KeyError),
    ):
        store.job("missing")
    with patch.object(Path, "open") as opened:
        stream = opened.return_value.__enter__.return_value
        stream.read.return_value = b"x" * 65537
        with pytest.raises(ValueError, match="budget"):
            store.job("synthetic-job")
        stream.read.return_value = _job().model_dump_json().encode()
        with pytest.raises(ValueError, match="identity"):
            store.job("different-job")
    with pytest.raises(ValueError):
        store.job("../escape")


def test_job_storage_refuses_terminal_rewrites() -> None:
    """The atomic transition check rejects illegal progress before a write."""
    store = LocalResearchStore(Path("mock"))
    with (
        patch("oxhack2026.research.store.file_lock"),
        patch.object(LocalResearchStore, "job", return_value=_job()),
        patch("oxhack2026.research.store.atomic_write") as write,
        pytest.raises(ValueError, match="transition"),
    ):
        store.save_job(_job())
    write.assert_not_called()


def test_report_route_checks_raw_and_saved_source_integrity(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """A report with missing saved lineage is unavailable, not an unknown ID."""
    source, saved = context
    service = _service(saved)
    captured = _capture({"hits": [], "nbHits": 0, "nbPages": 0})
    report = build_report(_job(), saved, source, captured)
    service.store.report.return_value = report  # type: ignore[attr-defined]
    service.sources.snapshot.side_effect = KeyError("private-location")  # type: ignore[attr-defined]
    app = create_app()
    app.dependency_overrides[get_research_service] = lambda: service

    with TestClient(app) as client:
        response = client.get(f"/api/v1/research-reports/{report.report_id}")

    assert response.status_code == 503
    assert "private-location" not in response.text


def test_saved_measurements_are_rechecked_for_staleness_at_report_cutoff(
    context: tuple[CompanySourceSnapshot, CompanyDetail],
) -> None:
    """A refresh never makes saved old measurements fresh merely by copying them."""
    source, saved = context
    captured = _capture({"hits": [], "nbHits": 0, "nbPages": 0})
    with patch.dict(
        "oxhack2026.research.report._METRIC_GROUPS",
        {"sdk_downloads_30d_v1": "adoption_retention"},
    ):
        report = build_report(_job(), saved, source, captured)

    adoption = report.outlook.specialists[0]
    assert adoption.data_status == "insufficient_data"
    assert "stale" in adoption.reason_codes
    assert adoption.usable_metric_observation_ids == ()
    assert report.inventory.saved_context.metrics[0] == saved.metrics[0]


@pytest.mark.parametrize("review", ["restricted", "unreviewed"])
def test_fresh_capture_cannot_bypass_privacy_or_review(
    context: tuple[CompanySourceSnapshot, CompanyDetail], review: str
) -> None:
    """Fresh output rejects private/unreviewed evidence rather than promoting it."""
    source, saved = context
    captured = _capture({"hits": [], "nbHits": 0, "nbPages": 0})
    evidence = captured.evidence.model_copy(
        update={"access": "restricted", "url": None}
        if review == "restricted"
        else {"review_state": "unreviewed"}
    )

    with pytest.raises(ValueError, match="public verified"):
        build_report(
            _job(),
            saved,
            source,
            AttentionCapture(captured.observation, evidence, True),
        )
