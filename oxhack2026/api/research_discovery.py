"""Public, bounded Google Search discovery provenance and continuation states."""

from typing import Literal

from pydantic import Field

from oxhack2026.api.schemas import DTO, Identifier, PublicURL, UTCDateTime
from oxhack2026.storage.contracts import ArtifactReference


class SearchCandidate(DTO):
    """A discovery link; only matched captured pages can support findings."""

    url: PublicURL
    title: str = Field(default="", max_length=2000)
    state: Literal[
        "pending", "matched", "unmatched", "blocked", "already_collected"
    ] = "pending"
    final_url: PublicURL | None = None
    capture_id: Identifier | None = None
    reason: str | None = None


class SearchDiscovery(DTO):
    """Provider metadata, distinct from evidence extracted from original pages."""

    run_id: Identifier
    model: str
    model_version: str | None = None
    collected_at: UTCDateTime
    requests: int = Field(default=0, ge=0)
    reserved_input: int = Field(default=0, ge=0)
    input_tokens: int | None = None
    output_tokens: int | None = None
    queries: tuple[str, ...] = Field(default=(), max_length=64)
    candidates: tuple[SearchCandidate, ...] = Field(default=(), max_length=100)
    search_suggestions: str | None = Field(default=None, max_length=32768)
    artifact: ArtifactReference | None = None
