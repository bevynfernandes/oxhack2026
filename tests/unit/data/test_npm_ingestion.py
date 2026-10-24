"""Mocked npm range extraction, immutable resume, and failure boundaries."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from itertools import pairwise
from unittest.mock import patch

import httpx
import orjson
import pytest
from pydantic import ValidationError

from oxhack2026.catalog.schemas import Package, TimeWindow
from oxhack2026.ingest.npm import (
    NPM_POLICY,
    NpmCheckpoint,
    NpmRequest,
    fetch_range,
    normalize_range,
    request_windows,
)
from oxhack2026.storage.contracts import ArtifactReference, validate_observation_policy


class MemoryArtifacts:
    """In-memory fake implementing ArtifactStore without filesystem dependencies."""

    def __init__(self) -> None:
        self.content: dict[str, bytes] = {}

    def write(self, content: bytes, media_type: str) -> ArtifactReference:
        """Save bytes in memory and return a hashed C1 reference."""
        digest = sha256(content).hexdigest()
        self.content[digest] = content
        return ArtifactReference.model_validate(
            {
                "path": f"objects/{digest}",
                "sha256": digest,
                "byte_size": len(content),
                "media_type": media_type,
            }
        )

    def read(self, reference: ArtifactReference) -> bytes:
        """Return the referenced fake bytes; unknown hashes raise KeyError."""
        return self.content[reference.sha256]


def _request() -> NpmRequest:
    return NpmRequest(
        package=Package(
            package_id="synthetic-scoped", ecosystem="npm", canonical_name="@demo/pkg"
        ),
        catalog_version="synthetic-v1",
        window=TimeWindow(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 4, tzinfo=UTC),
        ),
    )


def _payload() -> dict[str, object]:
    return {
        "package": "@demo/pkg",
        "start": "2024-01-01",
        "end": "2024-01-03",
        "downloads": [
            {"day": "2024-01-01", "downloads": 0},
            {"day": "2024-01-03", "downloads": 120},
        ],
    }


def _checkpoint(content: bytes) -> NpmCheckpoint:
    return NpmCheckpoint(
        request=_request(),
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        raw_artifact=MemoryArtifacts().write(content, "application/json"),
    )


def test_daily_missingness_and_assumed_availability() -> None:
    """Zeros remain counts, gaps remain null, and lag never rewrites collection."""
    content = orjson.dumps(_payload())
    checkpoint = _checkpoint(content)

    result = normalize_range(checkpoint, content)

    assert [row.value for row in result.observations] == [0, None, 120]
    assert result.coverage.complete_days == 2
    assert result.coverage.missing_days == 1
    assert result.coverage.status == result.manifest.status == "partial"
    for row in result.observations:
        assert row.first_collected_at == checkpoint.retrieved_at
        assert row.published_at is None
        assert row.available_at == row.window.end + timedelta(hours=48)
        validate_observation_policy(row, NPM_POLICY)


def test_resume_has_identical_identity_without_http() -> None:
    """A pinned checkpoint returns its exact vintage even if upstream changes."""
    artifacts = MemoryArtifacts()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=orjson.dumps(_payload()))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = fetch_range(_request(), client, artifacts)
        resumed = fetch_range(_request(), client, artifacts, first.checkpoint)

    assert len(calls) == 1
    assert calls[0].url.raw_path.endswith(b"2024-01-01:2024-01-03/@demo%2Fpkg")
    assert resumed == first
    later = NpmCheckpoint.model_validate(
        first.checkpoint.model_dump()
        | {"retrieved_at": first.checkpoint.retrieved_at + timedelta(seconds=1)}
    )
    revised = normalize_range(later, orjson.dumps(_payload()))
    assert revised.series == first.series
    assert revised.observations[0].revision_id != first.observations[0].revision_id


@pytest.mark.parametrize(
    "change",
    [
        {"package": "wrong"},
        {"end": "2024-01-04"},
        {"downloads": [{"day": "2024-01-04", "downloads": 1}]},
        {"downloads": [{"day": "2024-01-01", "downloads": 1}] * 2},
        {"downloads": [{"day": "2024-01-01", "downloads": -1}]},
        {"downloads": [{"day": "2024-01-01", "downloads": True}]},
        {"downloads": [{"day": "2024-01-01", "downloads": 1.5}]},
    ],
)
def test_malformed_source_rejected(change: dict[str, object]) -> None:
    """A valid hash cannot make mismatched or malformed source facts valid."""
    content = orjson.dumps(_payload() | change)
    with pytest.raises(ValueError):
        normalize_range(_checkpoint(content), content)


def test_corruption_and_early_checkpoint_rejected() -> None:
    """Replay verifies raw bytes and forbids a retrieval before measured days end."""
    content = orjson.dumps(_payload())
    checkpoint = _checkpoint(content)
    with pytest.raises(ValueError, match="hash and size"):
        normalize_range(checkpoint, content + b" ")
    with pytest.raises(ValidationError, match="retrieval must follow"):
        NpmCheckpoint.model_validate(
            checkpoint.model_dump() | {"retrieved_at": _request().window.start}
        )


def test_chunks_cover_leap_year_without_overlap() -> None:
    """Each inclusive API request can cover at most 365 UTC days."""
    window = TimeWindow(
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, tzinfo=UTC),
    )
    chunks = request_windows(window)
    assert [part.end - part.start for part in chunks] == [
        timedelta(days=365),
        timedelta(days=365),
        timedelta(days=1),
    ]
    assert chunks[0].start == window.start and chunks[-1].end == window.end
    assert all(a.end == b.start for a, b in pairwise(chunks))
    with pytest.raises(ValueError, match="365"):
        NpmRequest.model_validate(_request().model_dump() | {"window": window})


@pytest.mark.parametrize("status", [429, 500, 503])
def test_bounded_retry_then_success(status: int) -> None:
    """Transient responses back off without sleeping in tests or changing dates."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(status, headers={"Retry-After": "3"})
        return httpx.Response(200, content=orjson.dumps(_payload()))

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        patch("oxhack2026.ingest.npm.time.sleep") as sleep,
    ):
        fetch_range(_request(), client, MemoryArtifacts())
    assert len(calls) == 3
    assert [call.args[0] for call in sleep.call_args_list] == [3, 3]


@pytest.mark.parametrize("status, expected_attempts", [(404, 1), (429, 3), (503, 3)])
def test_http_failures_are_bounded(status: int, expected_attempts: int) -> None:
    """Permanent errors fail immediately and transient errors stop after 3 attempts."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        patch("oxhack2026.ingest.npm.time.sleep"),
        pytest.raises(httpx.HTTPStatusError),
    ):
        fetch_range(_request(), client, MemoryArtifacts())
    assert len(calls) == expected_attempts


def test_long_retry_after_defers_without_sleeping() -> None:
    """An excessive server wait does not trigger an early retry or an unbounded job."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, headers={"Retry-After": "120"})
    )
    with (
        httpx.Client(transport=transport) as client,
        patch("oxhack2026.ingest.npm.time.sleep") as sleep,
        pytest.raises(RuntimeError, match="Retry-After"),
    ):
        fetch_range(_request(), client, MemoryArtifacts())
    sleep.assert_not_called()


def test_response_size_cap() -> None:
    """A successful HTTP response still cannot exceed the raw extraction limit."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * 17)
    )
    with (
        httpx.Client(transport=transport) as client,
        patch("oxhack2026.ingest.npm.MAXIMUM_RESPONSE_BYTES", 16),
        pytest.raises(ValueError, match="bounded extraction"),
    ):
        fetch_range(_request(), client, MemoryArtifacts())


@pytest.mark.parametrize(
    "header", ["invalid", "nan", "inf", "Wed, 01 Jan 2020 00:00:00 GMT"]
)
def test_invalid_or_past_retry_after_uses_backoff(header: str) -> None:
    """Malformed, nonfinite and expired delay headers cannot defeat bounded retries."""
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": header}),
            httpx.Response(200, content=orjson.dumps(_payload())),
        ]
    )
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda request: next(responses))
        ) as client,
        patch("oxhack2026.ingest.npm.time.sleep") as sleep,
    ):
        fetch_range(_request(), client, MemoryArtifacts())
    assert 1 <= sleep.call_args.args[0] < 2
    sleep.assert_called_once()


def test_transport_failure_stops_after_three_attempts() -> None:
    """Network timeouts use the same bounded retry policy as transient statuses."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        message = "synthetic timeout"
        raise httpx.ReadTimeout(message, request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        patch("oxhack2026.ingest.npm.time.sleep") as sleep,
        pytest.raises(httpx.ReadTimeout),
    ):
        fetch_range(_request(), client, MemoryArtifacts())
    assert len(calls) == 3 and sleep.call_count == 2


def test_wrong_resume_and_future_window_do_not_fetch() -> None:
    """Checkpoint identity and closed measurement windows are validated before HTTP."""
    content = orjson.dumps(_payload())
    checkpoint = _checkpoint(content)
    different = NpmRequest.model_validate(
        _request().model_dump() | {"catalog_version": "different"}
    )
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    future = NpmRequest.model_validate(
        _request().model_dump()
        | {"window": TimeWindow(start=start, end=start + timedelta(days=1))}
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: pytest.fail())
    ) as client:
        with pytest.raises(ValueError, match="Resume checkpoint"):
            fetch_range(different, client, MemoryArtifacts(), checkpoint)
        with pytest.raises(ValueError, match="completed UTC"):
            fetch_range(future, client, MemoryArtifacts())


def test_empty_response_marks_all_days_missing() -> None:
    """An empty returned range is explicit missing coverage, never all-zero counts."""
    content = orjson.dumps(_payload() | {"downloads": []})
    result = normalize_range(_checkpoint(content), content)
    assert result.coverage.status == "missing"
    assert result.coverage.missing_days == 3
    assert all(row.value is None for row in result.observations)
