"""Public release history, with repository identity and pagination completeness."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import httpx
import orjson
from pydantic import BaseModel, ConfigDict, Field, StrictBool, TypeAdapter

from oxhack2026.catalog.schemas import Repository, TimeWindow, UtcInstant
from oxhack2026.ingest.capture import CaptureRequest, HttpCapture, capture_get
from oxhack2026.storage.artifacts import FileArtifactStore


class GithubRelease(BaseModel):
    """Only fields needed for a stable public release-count definition."""

    model_config = ConfigDict(extra="ignore")
    id: Annotated[int, Field(gt=0, strict=True)]
    draft: StrictBool
    prerelease: StrictBool
    published_at: UtcInstant | None


@dataclass(frozen=True)
class ReleaseHistory:
    """Captured pages; truncation stays explicit instead of becoming a complete zero."""

    captures: tuple[HttpCapture, ...]
    releases: tuple[GithubRelease, ...]
    complete: bool

    def count(self, window: TimeWindow) -> int | None:
        """Count published stable releases in the window, or None when truncated."""
        if not self.complete:
            return None
        return sum(
            not row.draft
            and not row.prerelease
            and row.published_at is not None
            and window.start <= row.published_at < window.end
            for row in self.releases
        )


def collect_releases(
    repository: Repository,
    client: httpx.Client,
    root: Path,
    run_id: str,
    maximum_pages: int = 10,
) -> ReleaseHistory:
    """Read all bounded release pages and verify the frozen numeric repository ID.

    Args:
        repository: Reviewed stable ID and current owner/name.
        client: Injected HTTP transport.
        root: Raw artifact/checkpoint directory.
        run_id: Frozen refresh identity.
        maximum_pages: Request ceiling, between one and one hundred.
    Returns:
        Captures/releases and completeness; a page ceiling returns partial data.
    Raises:
        ValueError: For malformed responses, ID mismatch, duplicate pages or limits.
        RuntimeError: For rate/access limits; checkpoints permit an exact restart.
        httpx.HTTPError: For HTTP/transport failures.
        OSError: For raw storage failure.
    """
    if not 1 <= maximum_pages <= 100:
        message = "GitHub release page budget must be between 1 and 100"
        raise ValueError(message)
    url = f"https://api.github.com/repos/{repository.full_name}"
    identity = capture_get(CaptureRequest(url=url), client, root, run_id)
    store = FileArtifactStore(root)
    payload = orjson.loads(store.read(identity.artifact))
    if (
        not isinstance(payload, dict)
        or type(payload.get("id")) is not int
        or payload["id"] != repository.repository_id
    ):
        message = "GitHub response disagrees with frozen numeric repository identity"
        raise ValueError(message)
    captures = [identity]
    releases: dict[int, GithubRelease] = {}
    complete = False
    for page in range(1, maximum_pages + 1):
        capture = capture_get(
            CaptureRequest(url=f"{url}/releases", page=page), client, root, run_id
        )
        rows = TypeAdapter(tuple[GithubRelease, ...]).validate_json(
            store.read(capture.artifact)
        )
        for row in rows:
            if row.id in releases:
                message = "Duplicate release across pages; source pagination changed"
                raise ValueError(message)
            if row.published_at is not None and row.published_at > capture.collected_at:
                message = "Release publication follows source collection"
                raise ValueError(message)
            releases[row.id] = row
        captures.append(capture)
        if not capture.has_next_page:
            complete = True
            break
    return ReleaseHistory(tuple(captures), tuple(releases.values()), complete)
