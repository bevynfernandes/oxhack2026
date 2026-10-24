"""Bounded npm daily extraction with explicit intervals and resumable raw snapshots."""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
from math import isfinite
from secrets import randbelow
from typing import Self
from urllib.parse import quote

import httpx
import orjson
from pydantic import model_validator

from oxhack2026.catalog.schemas import (
    Contract,
    Count,
    Identifier,
    Package,
    TimeWindow,
    UtcInstant,
)
from oxhack2026.storage.contracts import (
    ArtifactReference,
    ArtifactStore,
    AvailabilityPolicy,
    ExtractionManifest,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)

MAXIMUM_RESPONSE_BYTES = 2 * 1024 * 1024
logger = logging.getLogger(__name__)
NPM_POLICY = AvailabilityPolicy(
    policy_version="npm-lag48-v1",
    source="npm",
    basis="assumed_lag",
    assumed_lag_hours=48,
    description="Project availability assumption, not a vendor publication timestamp.",
)


class NpmRequest(Contract):
    """One verified package and explicit half-open request of at most 365 days."""

    package: Package
    catalog_version: Identifier
    window: TimeWindow

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Return this request; raise ValueError for unsupported scope or bounds."""
        if self.package.ecosystem != "npm":
            message = "The npm adapter requires an npm package"
            raise ValueError(message)
        for boundary in (self.window.start, self.window.end):
            if any(
                (boundary.hour, boundary.minute, boundary.second, boundary.microsecond)
            ):
                message = "npm request bounds must be UTC midnights"
                raise ValueError(message)
        if self.window.end - self.window.start > timedelta(days=365):
            message = "Split npm history into requests of at most 365 days"
            raise ValueError(message)
        return self


class NpmCheckpoint(Contract):
    """Persist this raw snapshot to resume without a new HTTP request or vintage."""

    request: NpmRequest
    retrieved_at: UtcInstant
    raw_artifact: ArtifactReference

    @model_validator(mode="after")
    def validate_checkpoint(self) -> Self:
        """Return a closed-range JSON checkpoint; reject inconsistent provenance."""
        if self.retrieved_at < self.request.window.end:
            message = "Checkpoint retrieval must follow the complete request interval"
            raise ValueError(message)
        if self.raw_artifact.media_type != "application/json":
            message = "npm checkpoints require a JSON raw artifact"
            raise ValueError(message)
        return self


@dataclass(frozen=True)
class NpmExtraction:
    """One normalized extraction plus its reusable raw checkpoint and provenance."""

    checkpoint: NpmCheckpoint
    series: ObservationSeries
    observations: tuple[ObservationRevision, ...]
    coverage: SourceCoverage
    manifest: ExtractionManifest


class _DownloadDay(Contract):
    """Strict source record, preserving a returned zero download count."""

    day: date
    downloads: Count


class _Payload(Contract):
    """Single-package npm range response."""

    package: str
    start: date
    end: date
    downloads: tuple[_DownloadDay, ...]


def request_windows(window: TimeWindow) -> tuple[TimeWindow, ...]:
    """Split an explicit half-open range into contiguous requests of <=365 days.

    Args:
        window: Requested UTC measurement range.
    Returns:
        Nonoverlapping windows covering exactly the requested interval.
    Raises:
        ValueError: If either boundary is not UTC midnight.
    """
    for boundary in (window.start, window.end):
        if any((boundary.hour, boundary.minute, boundary.second, boundary.microsecond)):
            message = "Daily extraction requires UTC midnight bounds"
            raise ValueError(message)
    chunks: list[TimeWindow] = []
    start = window.start
    while start < window.end:
        end = min(start + timedelta(days=365), window.end)
        chunks.append(TimeWindow(start=start, end=end))
        start = end
    return tuple(chunks)


def _retry_delay(value: str | None, attempt: int) -> float:
    delay: float = 2.0**attempt + randbelow(1000) / 1000
    if value is not None:
        try:
            requested = float(value)
        except ValueError:
            try:
                timestamp = parsedate_to_datetime(value)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                requested = (timestamp - datetime.now(UTC)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                logger.warning("Invalid npm Retry-After; using bounded backoff")
                return delay
        if not isfinite(requested):
            logger.warning("Nonfinite npm Retry-After; using bounded backoff")
            return delay
        delay = max(delay, requested)
    if delay > 60:
        message = "npm requests a longer Retry-After; resume this checkpoint later"
        raise RuntimeError(message)
    return delay


def _download(request: NpmRequest, client: httpx.Client) -> bytes:
    start = request.window.start.date().isoformat()
    end = (request.window.end - timedelta(days=1)).date().isoformat()
    package = quote(request.package.canonical_name, safe="@")
    url = f"https://api.npmjs.org/downloads/range/{start}:{end}/{package}"
    for attempt in range(3):
        try:
            with client.stream(
                "GET", url, timeout=20, follow_redirects=False
            ) as response:
                retryable = response.status_code == 429 or response.status_code >= 500
                if retryable and attempt < 2:
                    delay = _retry_delay(response.headers.get("Retry-After"), attempt)
                else:
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        content.extend(chunk)
                        if len(content) > MAXIMUM_RESPONSE_BYTES:
                            message = (
                                "npm response exceeds the bounded extraction limit"
                            )
                            raise ValueError(message)
                    return bytes(content)
        except httpx.TransportError:
            if attempt == 2:
                raise
            delay = _retry_delay(None, attempt)
        time.sleep(delay)
    message = "npm extraction exhausted its bounded retry attempts"
    raise RuntimeError(message)


def normalize_range(checkpoint: NpmCheckpoint, content: bytes) -> NpmExtraction:
    """Validate saved source bytes and construct C1 observations without network I/O.

    Args:
        checkpoint: Exact request, actual retrieval time and expected raw artifact.
        content: Saved raw npm response bytes.
    Returns:
        Explicit counts/gaps, coverage and immutable extraction provenance.
    Raises:
        ValueError: For corruption, mismatched identities/bounds or malformed records.
    """
    reference = checkpoint.raw_artifact
    if (
        len(content) != reference.byte_size
        or sha256(content).hexdigest() != reference.sha256
    ):
        message = "Raw npm response does not match the checkpoint hash and size"
        raise ValueError(message)
    payload = _Payload.model_validate(orjson.loads(content))
    request = checkpoint.request
    if (
        payload.package != request.package.canonical_name
        or payload.start != request.window.start.date()
        or payload.end != (request.window.end - timedelta(days=1)).date()
    ):
        message = "npm response package or inclusive bounds differ from the request"
        raise ValueError(message)
    days: dict[date, int] = {}
    for row in payload.downloads:
        if row.day in days or not payload.start <= row.day <= payload.end:
            message = "npm returned a duplicate or out-of-range observation day"
            raise ValueError(message)
        days[row.day] = row.downloads
    series = ObservationSeries(
        series_id="npm-" + sha256(request.package.canonical_name.encode()).hexdigest(),
        source="npm",
        entity_kind="package",
        entity_id=request.package.package_id,
        ecosystem="npm",
        metric="daily_downloads",
        unit="downloads",
    )
    configuration = orjson.dumps(
        request.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
    )
    extraction_id = (
        "npm-"
        + sha256(
            configuration
            + reference.sha256.encode()
            + checkpoint.retrieved_at.isoformat().encode()
        ).hexdigest()
    )
    observations: list[ObservationRevision] = []
    start = request.window.start
    while start < request.window.end:
        end = start + timedelta(days=1)
        value = days.get(start.date())
        available = end + timedelta(hours=48)
        revision_id = (
            "npm-" + sha256(f"{extraction_id}:{start.date()}".encode()).hexdigest()
        )
        observations.append(
            ObservationRevision(
                revision_id=revision_id,
                series_id=series.series_id,
                window=TimeWindow(start=start, end=end),
                value=value,
                completeness="missing" if value is None else "complete",
                published_at=None,
                assumed_available_at=available,
                available_at=available,
                availability_basis="assumed_lag",
                availability_policy_version=NPM_POLICY.policy_version,
                first_collected_at=checkpoint.retrieved_at,
                retrieved_at=checkpoint.retrieved_at,
                extraction_id=extraction_id,
                extraction_version="npm-daily-v1",
                filter_version="npm-unfiltered-v1",
                source_revision_id=None,
                supersedes_revision_id=None,
                raw_artifact_sha256=reference.sha256,
            )
        )
        start = end
    missing = len(observations) - len(days)
    coverage = SourceCoverage(
        series_id=series.series_id,
        window=request.window,
        expected_days=len(observations),
        complete_days=len(days),
        partial_days=0,
        missing_days=missing,
        status="complete" if not missing else "missing" if not days else "partial",
        last_success_at=checkpoint.retrieved_at,
        reasons=("missing_npm_days",) if missing else (),
    )
    manifest = ExtractionManifest(
        extraction_id=extraction_id,
        source="npm",
        catalog_version=request.catalog_version,
        requested_window=request.window,
        retrieved_at=checkpoint.retrieved_at,
        extraction_version="npm-daily-v1",
        filter_version="npm-unfiltered-v1",
        configuration_sha256=sha256(configuration).hexdigest(),
        raw_artifacts=(reference,),
        status="partial" if missing else "complete",
        limitations=(
            "Historical counts retrieved later; "
            "availability uses an assumed 48-hour lag.",
        ),
    )
    return NpmExtraction(checkpoint, series, tuple(observations), coverage, manifest)


def fetch_range(
    request: NpmRequest,
    client: httpx.Client,
    artifacts: ArtifactStore,
    checkpoint: NpmCheckpoint | None = None,
) -> NpmExtraction:
    """Fetch one range or resume an identical saved raw snapshot without HTTP calls.

    Args:
        request: Package, catalogue version and explicit bounded daily interval.
        client: Caller-owned HTTP client; redirects are disabled per request.
        artifacts: Content-addressed raw artifact store.
        checkpoint: Optional previously persisted request/raw retrieval identity.
    Returns:
        Validated C1 rows and a checkpoint the caller must persist for resumption.
    Raises:
        ValueError: For future intervals, invalid payloads or mismatched checkpoints.
        httpx.HTTPError: For nonretryable responses or three exhausted attempts.
        RuntimeError: If Retry-After requires deferring the job beyond 60 seconds.
        OSError: If raw artifact persistence fails.
    """
    if checkpoint is not None:
        if checkpoint.request != request:
            message = "Resume checkpoint must match the exact package/catalogue/window"
            raise ValueError(message)
        return normalize_range(checkpoint, artifacts.read(checkpoint.raw_artifact))
    if request.window.end > datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ):
        message = "npm extraction only accepts completed UTC days"
        raise ValueError(message)
    content = _download(request, client)
    retrieved = datetime.now(UTC)
    checkpoint = NpmCheckpoint(
        request=request,
        retrieved_at=retrieved,
        raw_artifact=artifacts.write(content, "application/json"),
    )
    return normalize_range(checkpoint, content)
