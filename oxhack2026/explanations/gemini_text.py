"""Bounded native text streaming, without retaining private thinking content."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import orjson
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from google.genai import types

MAX_RESPONSE_BYTES = 128 * 1024


class GroundingWeb(BaseModel):
    """Public source location supplied by the grounding provider."""

    uri: str = Field(max_length=8192)
    title: str = Field(default="", max_length=2000)


class GroundingChunk(BaseModel):
    """A web citation; non-web grounding fields are intentionally ignored."""

    web: GroundingWeb | None = None


class SearchEntryPoint(BaseModel):
    """Provider attribution, displayed only in an isolated document."""

    rendered_content: str = Field(default="", max_length=32768)


class GroundingSnapshot(BaseModel):
    """Public discovery metadata, excluding generated assertions and thoughts."""

    web_search_queries: list[str] = Field(default_factory=list, max_length=64)
    grounding_chunks: list[GroundingChunk] = Field(default_factory=list, max_length=100)
    search_entry_point: SearchEntryPoint | None = None


@dataclass(frozen=True)
class TextResult:
    """A complete response and provider-reported usage, never estimated usage."""

    response: str
    model_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    grounding: tuple[GroundingSnapshot, ...]


class TextProtocolError(Exception):
    """The text stream cannot be accepted as a complete bounded response."""


async def stream_text(
    key: str,
    model: str,
    prompt: str,
    configuration: "types.GenerateContentConfig",
    timeout: float,
) -> TextResult:
    """Read one native stream with an absolute deadline and bounded public output.

    Args:
        key: Credential passed only to the SDK's authentication configuration.
        model: Explicit model identifier; no automatic fallback is permitted.
        prompt: Bounded public input and trusted task instructions.
        configuration: Structured extraction or separate grounding configuration.
        timeout: Maximum total elapsed seconds, including silent stream periods.
    Returns:
        Completed public text, grounding metadata and available usage counters.
    Raises:
        TimeoutError: The absolute request deadline expired.
        TextProtocolError: Output exceeded limits or the stream did not finish.
    """
    from google import genai
    from google.genai import types

    parts: list[str] = []
    grounding: dict[bytes, GroundingSnapshot] = {}
    size = 0
    finish = None
    model_version = None
    usage = None
    async with asyncio.timeout(timeout):
        async with genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=max(1, int(timeout * 1000)),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ).aio as client:
            stream = await client.models.generate_content_stream(
                model=model, contents=prompt, config=configuration
            )
            try:
                async for chunk in stream:
                    model_version = chunk.model_version or model_version
                    usage = chunk.usage_metadata or usage
                    for candidate in chunk.candidates or []:
                        finish = candidate.finish_reason or finish
                        text = "".join(
                            part.text
                            for part in (
                                candidate.content.parts or []
                                if candidate.content
                                else []
                            )
                            if part.text and not part.thought
                        )
                        if text:
                            parts.append(text)
                            size += len(text.encode())
                        if candidate.grounding_metadata:
                            snapshot = GroundingSnapshot.model_validate(
                                candidate.grounding_metadata.model_dump(
                                    mode="json", exclude_none=True
                                )
                            )
                            serialized = orjson.dumps(snapshot.model_dump())
                            if serialized not in grounding:
                                grounding[serialized] = snapshot
                                size += len(serialized)
                    if size > MAX_RESPONSE_BYTES:
                        raise TextProtocolError("gemini_response_limit")
            finally:
                if isinstance(stream, AsyncGenerator):
                    await stream.aclose()
    if finish != types.FinishReason.STOP:
        raise TextProtocolError("gemini_incomplete_response")
    input_tokens = usage.prompt_token_count if usage else None
    output_tokens = None
    if usage and usage.candidates_token_count is not None:
        output_tokens = usage.candidates_token_count + (usage.thoughts_token_count or 0)
    return TextResult(
        "".join(parts),
        model_version,
        input_tokens,
        output_tokens,
        tuple(grounding.values()),
    )
