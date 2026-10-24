"""Bounded public captures and source normalization, with all external I/O mocked."""

from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx
import orjson
import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.catalog.schemas import Repository, TimeWindow
from oxhack2026.ingest.capture import CaptureRequest, HttpCapture, capture_get
from oxhack2026.ingest.company_pipeline import (
    CompanyBuildSettings,
    FundingSeed,
    _company,
)
from oxhack2026.ingest.github_releases import collect_releases
from oxhack2026.storage.contracts import ArtifactStore
from oxhack2026.storage.datasets import DatasetBundle


@pytest.mark.parametrize("status", [403, 429])
def test_capture_defers_budget_failures(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore], status: int
) -> None:
    """Denied/rate-limited calls do not retry immediately or persist a fake result."""
    _, artifacts = company_source
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status)

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        patch("oxhack2026.ingest.capture.file_lock", return_value=nullcontext()),
        patch.object(Path, "exists", return_value=False),
        patch("oxhack2026.ingest.capture.FileArtifactStore", return_value=artifacts),
        patch("oxhack2026.ingest.capture.atomic_write") as write,
        pytest.raises(RuntimeError, match="budget"),
    ):
        capture_get(
            CaptureRequest(url="https://api.github.com/repos/a/b"),
            client,
            Path("mock"),
            "run",
        )
    assert len(calls) == 1
    write.assert_not_called()


def test_capture_auth_scope_and_size_budget(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """GitHub credentials stay on GitHub; oversized bytes never become artifacts."""
    _, artifacts = company_source
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"12345")

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        patch.dict("os.environ", {"GITHUB_TOKEN": "synthetic-token"}),
        patch("oxhack2026.ingest.capture.file_lock", return_value=nullcontext()),
        patch.object(Path, "exists", return_value=False),
        patch("oxhack2026.ingest.capture.FileArtifactStore", return_value=artifacts),
        patch("oxhack2026.ingest.capture.atomic_write"),
        patch("oxhack2026.ingest.capture.MAXIMUM_BYTES", 4),
    ):
        for host in ("api.github.com", "company.example"):
            with pytest.raises(ValueError, match="size budget"):
                capture_get(
                    CaptureRequest(url=f"https://{host}/source"),
                    client,
                    Path("mock"),
                    "run",
                )
    assert requests[0].headers["Authorization"] == "Bearer synthetic-token"
    assert "Authorization" not in requests[1].headers


@pytest.mark.parametrize("maximum,expected", [(1, None), (2, 1)])
def test_release_pagination_and_filters(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    maximum: int,
    expected: int | None,
) -> None:
    """Complete enumeration and stable-release/window filters determine counts."""
    _, artifacts = company_source
    timestamp = datetime(2025, 2, 1, tzinfo=UTC)

    def capture(
        request: CaptureRequest, client: httpx.Client, root: Path, run_id: str
    ) -> HttpCapture:
        payload: object = {"id": 123}
        if request.page:
            payload = [
                {
                    "id": request.page,
                    "draft": False,
                    "prerelease": request.page == 2,
                    "published_at": "2025-01-15T00:00:00Z",
                }
            ]
        return HttpCapture(
            request=request,
            collected_at=timestamp,
            artifact=artifacts.write(orjson.dumps(payload), "application/octet-stream"),
            has_next_page=request.page == 1,
        )

    with (
        httpx.Client() as client,
        patch("oxhack2026.ingest.github_releases.capture_get", side_effect=capture),
        patch(
            "oxhack2026.ingest.github_releases.FileArtifactStore",
            return_value=artifacts,
        ),
    ):
        history = collect_releases(
            Repository(repository_id=123, full_name="a/b"),
            client,
            Path("mock"),
            "run",
            maximum,
        )
    assert (
        history.count(TimeWindow(start=datetime(2025, 1, 1, tzinfo=UTC), end=timestamp))
        == expected
    )


def test_release_identity_mismatch(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """A redirected/reused repository name cannot silently change numeric identity."""
    _, artifacts = company_source
    capture = HttpCapture(
        request=CaptureRequest(url="https://api.github.com/repos/a/b"),
        collected_at=datetime(2025, 2, 1, tzinfo=UTC),
        artifact=artifacts.write(b'{"id":456}', "application/octet-stream"),
        has_next_page=False,
    )
    with (
        httpx.Client() as client,
        patch("oxhack2026.ingest.github_releases.capture_get", return_value=capture),
        patch(
            "oxhack2026.ingest.github_releases.FileArtifactStore",
            return_value=artifacts,
        ),
        pytest.raises(ValueError, match="numeric repository"),
    ):
        collect_releases(
            Repository(repository_id=123, full_name="a/b"),
            client,
            Path("mock"),
            "run",
        )


def test_company_normalization_retains_missing_financials(
    synthetic_bundle: tuple[DatasetBundle, ArtifactStore],
) -> None:
    """Announcement, SDK rows and releases compose with financial unknowns."""
    bundle, artifacts = synthetic_bundle
    seed = FundingSeed(
        company_id="synthetic-org",
        url="https://example.com/funding",
        announcement_date=datetime(2024, 1, 1).date(),
        amount_usd="50000000",
        required_text=("Synthetic raised $50M",),
        description="Synthetic financing claim.",
    )
    settings = CompanyBuildSettings(
        run_id="synthetic-run",
        snapshot_id="synthetic-source",
        npm_dataset_version=bundle.manifest.dataset_version,
        code_revision="test-code",
        cohort_version="test-cohort",
        measurement_end=datetime(2025, 1, 4, tzinfo=UTC),
        companies=(seed,),
    )

    def capture(
        request: CaptureRequest, client: httpx.Client, root: Path, run_id: str
    ) -> HttpCapture:
        raw = b"<p>Synthetic raised $50M</p>"
        if "api.github.com" in request.url:
            raw = b"[]" if request.page else b'{"id":123456}'
        return HttpCapture(
            request=request,
            collected_at=datetime(2026, 10, 24, 16, tzinfo=UTC),
            artifact=artifacts.write(raw, "application/octet-stream"),
            has_next_page=False,
        )

    with (
        patch("oxhack2026.ingest.company_pipeline.capture_get", side_effect=capture),
        patch("oxhack2026.ingest.github_releases.capture_get", side_effect=capture),
        patch(
            "oxhack2026.ingest.company_pipeline.FileArtifactStore",
            return_value=artifacts,
        ),
        patch(
            "oxhack2026.ingest.github_releases.FileArtifactStore",
            return_value=artifacts,
        ),
    ):
        profile, relations, evidence, metrics, event = _company(
            seed, bundle, settings, Path("mock"), Path("mock-npm")
        )
    assert profile.company_id == "synthetic-org"
    assert event.stage == "announced"
    assert all(
        row.state == "missing"
        for row in metrics
        if row.metric_id
        in (
            "revenue_12m_usd_v1",
            "operating_cashflow_12m_usd_v1",
            "active_paying_customers_v1",
        )
    )
    assert all(row.subject_kind != "family" for row in relations)
    assert len(evidence) >= 4
