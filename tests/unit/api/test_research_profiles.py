"""Research profiles, configuration snapshots and continuation safety."""

from concurrent.futures import Executor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from oxhack2026.api.research_configuration import (
    ContinueRequest,
    CrawlTarget,
    ResearchProfile,
    SourceDetails,
    profile_settings,
)
from oxhack2026.api.research_v2_schemas import DiscoveryRequest, Identity, JobRequest
from oxhack2026.research.v2_service import V2Service
from oxhack2026.research.v2_store import V2Store


@pytest.mark.parametrize(
    "profile,seconds,pages",
    [
        ("fast", 300, 20),
        ("thorough", 600, 60),
        ("deep", 1200, 120),
    ],
)
def test_profile_limits(profile: ResearchProfile, seconds: int, pages: int) -> None:
    """Profiles expose bounded and independent budgets."""
    settings = profile_settings(profile)
    assert settings.deadline_seconds == seconds
    assert settings.company_pages == pages
    assert settings.model_requests <= 24
    assert profile_settings(profile) is not settings


def test_snapshot_and_depth_aware_coalescing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same active operation coalesces; a new depth or model stays independent."""
    store = V2Store(tmp_path)
    identity = Identity(
        identity_id="identity",
        request=DiscoveryRequest(domain="example.com"),
        state="queued",
        requested_at=datetime.now(UTC),
        requested_domain="example.com",
        canonical_domain="example.com",
        company_name="Example",
    )
    store.save_identity(identity)
    store.save_identity(identity.model_copy(update={"state": "running"}))
    store.save_identity(
        identity.model_copy(update={"state": "ready", "finished_at": datetime.now(UTC)})
    )
    executor = Mock(spec=Executor)
    service = V2Service(store, executor)
    request = JobRequest(identity_id="identity", identity_confirmed=True)
    first = service.create(request)
    assert service.create(request).job_id == first.job_id
    deep = service.create(request.model_copy(update={"profile": "deep"}))
    assert deep.job_id != first.job_id
    monkeypatch.setenv("GEMINI_MODEL", "different-model")
    assert store.job(first.job_id).settings == first.settings
    assert service.create(request).job_id != first.job_id
    with pytest.raises(ValueError, match="terminal"):
        service.continue_job(first.job_id, ContinueRequest())


def test_continuation_keeps_prior_sources(tmp_path: Path) -> None:
    """Pending frontiers reset execution without losing stored source data."""
    from oxhack2026.api.research_v2_schemas import PROVIDERS, Job, SourceState

    details = SourceDetails(
        execution="completed",
        scope="planned_sample",
        coverage="limited",
        frontier=(CrawlTarget(url="https://example.com/about", depth=1),),
    )
    job = Job(
        job_id="job",
        identity_id="identity",
        requested_at=datetime.now(UTC),
        sources=tuple(
            SourceState(
                provider=provider,
                name=provider,
                state="partial",
                details=details if provider == "website" else None,
            )
            for provider in PROVIDERS
        ),
    )
    states = V2Service(V2Store(tmp_path))._resume_sources(job)
    assert states[0].state == "pending"
    assert states[0].details == details.model_copy(update={"execution": "pending"})
    assert states[1] == job.sources[1]
    assert job.sources[0].state == "partial"


def test_invalid_profile() -> None:
    """Unsupported depth fails before any provider work."""
    with pytest.raises(ValidationError):
        ContinueRequest.model_validate({"profile": "unlimited"})


@pytest.mark.parametrize("executor_failure", [False, True])
def test_queued_continuation_failure_preserves_terminal_sources(
    tmp_path: Path, executor_failure: bool
) -> None:
    """Disabled recovery and executor rejection preserve retained terminal sources."""
    from oxhack2026.api.repository import RepositoryUnavailable
    from oxhack2026.api.research_v2_schemas import PROVIDERS, Job, SourceState

    store = V2Store(tmp_path)
    now = datetime.now(UTC)
    identity = Identity(
        identity_id="identity",
        request=DiscoveryRequest(domain="example.com"),
        state="queued",
        requested_at=now,
        requested_domain="example.com",
        canonical_domain="example.com",
        company_name="Example",
    )
    store.save_identity(identity)
    store.save_identity(identity.model_copy(update={"state": "ready"}))
    states = (
        "pending",
        "completed",
        "skipped",
        "partial",
        "failed",
        "completed",
        "skipped",
        "completed",
    )
    previous = Job(
        job_id="continuation",
        identity_id=identity.identity_id,
        requested_at=now,
        derived_from_report_id="original",
        sources=tuple(
            SourceState.model_validate(
                {
                    "provider": provider,
                    "name": provider,
                    "state": state,
                    "finished_at": now if state != "pending" else None,
                    "reason_codes": ("retained_reason",) if state != "pending" else (),
                    "details": SourceDetails(
                        execution="pending", scope="planned_sample", coverage="unknown"
                    )
                    if state == "pending"
                    else None,
                }
            )
            for provider, state in zip(PROVIDERS, states, strict=True)
        ),
    )
    executor = Mock(spec=Executor)
    expected = previous.sources
    if executor_failure:
        executor.submit.side_effect = RuntimeError("executor closed")
        service = V2Service(store, executor)
        expected = service._resume_sources(previous)
        with pytest.raises(RepositoryUnavailable):
            service.create(
                JobRequest(identity_id="identity", identity_confirmed=True), previous
            )
        result = store.jobs()[0]
    else:
        store.save_job(previous)
        V2Service(store, executor, collection_enabled=False).recover()
        result = store.job(previous.job_id)
        executor.submit.assert_not_called()
    assert result.state == "failed"
    assert result.sources[0].state == "failed"
    for source, retained in zip(result.sources, expected, strict=True):
        if retained.state in {"pending", "running"}:
            assert source.state == "failed"
            if source.details:
                assert source.details.execution == "failed"
                assert source.details.coverage == "limited"
                assert source.details.issues[-1].code == result.reason_codes[-1]
        else:
            assert source == retained


@pytest.mark.parametrize("retry_failed", [False, True])
def test_continuation_uses_only_a_report_from_the_same_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retry_failed: bool
) -> None:
    """A re-mapped report may continue its own job while cross-job links fail closed."""
    from oxhack2026.api.evidence_mapping_schemas import MappingProgress
    from oxhack2026.api.research_v2_schemas import PROVIDERS, Job, SourceState
    from oxhack2026.research.composition import compose
    from oxhack2026.research.evidence_mapping import MappingEngine

    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_MAPPING_MODE", "rules")
    now = datetime.now(UTC)
    identity = Identity(
        identity_id="identity",
        request=DiscoveryRequest(domain="example.com"),
        state="ready",
        requested_at=now,
        finished_at=now,
        requested_domain="example.com",
        canonical_domain="example.com",
        company_name="Example",
    )
    previous = Job(
        job_id="job",
        identity_id="identity",
        requested_at=now,
        started_at=now,
        finished_at=now,
        state="completed",
        report_id="original",
        sources=tuple(
            SourceState(
                provider=provider,
                name=provider,
                state="failed"
                if retry_failed and provider == "github"
                else "completed",
                finished_at=now,
            )
            for provider in PROVIDERS
        ),
        mapping=MappingProgress(state="completed", finished_at=now),
    )
    report = MappingEngine(tmp_path).map(compose(previous, identity))
    assert report.mapping
    report = report.model_copy(
        update={
            "report_id": "remapped",
            "mapping": report.mapping.model_copy(
                update={"state": "completed" if retry_failed else "partial"}
            ),
        }
    )
    store = Mock(spec=V2Store)
    store.job.return_value = previous
    store.report.return_value = report
    service = V2Service(store)
    create = Mock(return_value=previous)
    monkeypatch.setattr(service, "create", create)
    service.continue_job("job", ContinueRequest(source_report_id="remapped"))
    resumed = create.call_args.args[1]
    assert resumed.report_id == "remapped"
    assert previous.report_id == "original"
    assert report.mapping
    assert resumed.mapping.finished_at == report.mapping.mapped_at
    store.report.return_value = report.model_copy(update={"job_id": "unrelated"})
    with pytest.raises(ValueError, match="must belong"):
        service.continue_job("job", ContinueRequest(source_report_id="remapped"))
