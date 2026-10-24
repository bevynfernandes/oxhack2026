"""Bounded HTTP captures with durable checkpoints and explicit request identity."""

import logging
import os
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

import httpx
import orjson
from pydantic import Field, model_validator

from oxhack2026.catalog.schemas import Contract, Identifier, PublicUrl, UtcInstant
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock

logger = logging.getLogger(__name__)
MAXIMUM_BYTES = 4 * 1024 * 1024


class CaptureRequest(Contract):
    """Public source URL and optional bounded GitHub page; secrets are never stored."""

    url: PublicUrl
    page: Annotated[int, Field(gt=0, le=100, strict=True)] | None = None
    query_parameters: tuple[
        tuple[
            Literal[
                "query",
                "tags",
                "restrictSearchableAttributes",
                "numericFilters",
                "hitsPerPage",
                "page",
            ],
            Annotated[str, Field(max_length=512)],
        ],
        ...,
    ] = ()

    @model_validator(mode="after")
    def validate_query_parameters(self) -> Self:
        """Allow bounded non-secret search parameters only on the fixed HN API."""
        if self.query_parameters and (
            self.url != "https://hn.algolia.com/api/v1/search_by_date"
            or self.page is not None
            or len({key for key, _ in self.query_parameters})
            != len(self.query_parameters)
        ):
            message = "Structured queries require the fixed HN endpoint and unique keys"
            raise ValueError(message)
        return self


class HttpCapture(Contract):
    """Exact response bytes with actual collection time and pagination metadata."""

    request: CaptureRequest
    collected_at: UtcInstant
    artifact: ArtifactReference
    has_next_page: bool


class CaptureRun(Contract):
    """Filesystem-safe identity for an intentional refresh or exact restart."""

    run_id: Identifier


def _download(request: CaptureRequest, client: httpx.Client) -> tuple[bytes, bool]:
    headers = {"User-Agent": "SignalShift-research/1.0"}
    if urlsplit(request.url).hostname == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    params: dict[str, str] | None = (
        {"per_page": "100", "page": str(request.page)}
        if request.page
        else dict(request.query_parameters) or None
    )
    for attempt in range(3):
        try:
            with client.stream(
                "GET",
                request.url,
                params=params,
                headers=headers,
                timeout=25,
                follow_redirects=False,
            ) as response:
                if response.status_code in (403, 429):
                    message = (
                        "Source access/rate budget unavailable; "
                        "resume later without bypassing limits"
                    )
                    raise RuntimeError(message)
                if response.status_code >= 500 and attempt < 2:
                    logger.warning(
                        "Transient source failure; bounded retry %s", attempt + 1
                    )
                else:
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        content.extend(chunk)
                        if len(content) > MAXIMUM_BYTES:
                            message = "Source response exceeds capture size budget"
                            raise ValueError(message)
                    return bytes(content), "next" in response.links
        except httpx.TransportError:
            if attempt == 2:
                raise
            logger.warning("Source transport failure; bounded retry %s", attempt + 1)
        time.sleep(2**attempt)
    message = "Source capture attempts exhausted"
    raise RuntimeError(message)


def capture_get(
    request: CaptureRequest, client: httpx.Client, root: Path, run_id: str
) -> HttpCapture:
    """Fetch once per frozen request/run, retaining raw bytes and actual timestamps.

    Args:
        request: Public URL and optional GitHub pagination parameters.
        client: Injected HTTP transport; headers are scoped per request.
        root: Application-controlled artifact/checkpoint directory.
        run_id: Safe run identity; new ID deliberately refreshes source evidence.
    Returns:
        Exact captured response metadata, replayed without HTTP on restart.
    Raises:
        ValueError: For bad identities, oversized/corrupt response or checkpoint.
        RuntimeError: If access/rate limits require operator follow-up.
        httpx.HTTPError: For permanent HTTP/transport failure.
        OSError: For checkpoint/artifact persistence failure.
    """
    run = CaptureRun(run_id=run_id)
    request_bytes = request.model_dump_json(
        exclude={"query_parameters"} if not request.query_parameters else None
    ).encode()
    digest = sha256(request_bytes).hexdigest()
    directory = root / "captures" / run.run_id
    path = directory / f"{digest}.json"
    store = FileArtifactStore(root)
    with file_lock(directory / f"{digest}.lock"):
        if path.exists():
            saved = HttpCapture.model_validate_json(path.read_bytes())
            if saved.request != request:
                message = "Checkpoint request identity disagrees with requested capture"
                raise ValueError(message)
            store.read(saved.artifact)
            return saved
        content, has_next = _download(request, client)
        capture = HttpCapture(
            request=request,
            collected_at=datetime.now(UTC),
            artifact=store.write(content, "application/octet-stream"),
            has_next_page=has_next,
        )
        atomic_write(path, capture.model_dump_json().encode())
        return capture


def freeze_run(root: Path, run_id: str, configuration: bytes) -> None:
    """Pin exact canonical configuration for a run; reject changed restart settings.

    Args:
        root: Application-controlled artifact directory.
        run_id: Safe run identifier.
        configuration: Deterministic serialized configuration, excluding secrets.
    Raises:
        ValueError: If the run ID is reused with changed configuration.
        OSError: If durable pinning fails.
    """
    run = CaptureRun(run_id=run_id)
    path = root / "captures" / run.run_id / "configuration.json"
    with file_lock(path.with_suffix(".lock")):
        if path.exists():
            if path.read_bytes() != configuration:
                message = "Capture run identity is frozen to a different configuration"
                raise ValueError(message)
        else:
            orjson.loads(configuration)
            atomic_write(path, configuration)
