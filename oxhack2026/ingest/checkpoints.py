"""Durable idempotent npm extraction jobs using request-specific filesystem locks."""

from hashlib import sha256
from pathlib import Path

import httpx
import orjson
from pydantic import TypeAdapter

from oxhack2026.catalog.schemas import Identifier
from oxhack2026.ingest.npm import NpmCheckpoint, NpmExtraction, NpmRequest, fetch_range
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.local import atomic_write, file_lock


def checkpointed_fetch(
    request: NpmRequest, client: httpx.Client, root: Path, run_id: str
) -> NpmExtraction:
    """Resume one request in a named run; a new run intentionally collects a vintage.

    Args:
        request: Exact package/catalogue/measurement request.
        client: Caller-owned bounded HTTP client.
        root: Application-controlled bundle root, shared by all jobs in this run.
        run_id: Stable retry identity; change it only for an intentional refresh.
    Returns:
        Same revisions for retries, including across process restarts.
    Raises:
        ValueError: For invalid identity, payload or checkpoint corruption.
        OSError: For local persistence failure.
        httpx.HTTPError: For exhausted source requests.
        RuntimeError: When the source requires a deferred retry.
    """
    TypeAdapter(Identifier).validate_python(run_id)
    configuration = orjson.dumps(
        request.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
    )
    request_id = sha256(configuration).hexdigest()
    folder = root / "checkpoints" / run_id
    checkpoint_path = folder / f"{request_id}.json"
    with file_lock(folder / f"{request_id}.lock"):
        try:
            checkpoint = NpmCheckpoint.model_validate_json(checkpoint_path.read_bytes())
        except FileNotFoundError:
            checkpoint = None
        result = fetch_range(request, client, FileArtifactStore(root), checkpoint)
        if checkpoint is None:
            atomic_write(checkpoint_path, result.checkpoint.model_dump_json().encode())
        return result
