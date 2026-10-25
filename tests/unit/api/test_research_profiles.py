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
    assert states[0].details == details
    assert states[1] == job.sources[1]
    assert job.sources[0].state == "partial"


def test_invalid_profile() -> None:
    """Unsupported depth fails before any provider work."""
    with pytest.raises(ValidationError):
        ContinueRequest.model_validate({"profile": "unlimited"})
