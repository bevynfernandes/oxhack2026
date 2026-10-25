"""Native streaming boundaries, public output isolation and resource cleanup."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import orjson
import pytest
from google import genai
from google.genai import types

from oxhack2026.explanations.gemini_text import (
    MAX_RESPONSE_BYTES,
    TextProtocolError,
    stream_text,
)


def _sdk(
    monkeypatch: pytest.MonkeyPatch,
    chunks: list[types.GenerateContentResponse],
    delay: float = 0,
) -> tuple[Mock, list[bool]]:
    closed: list[bool] = []

    async def responses() -> AsyncGenerator[types.GenerateContentResponse]:
        try:
            for chunk in chunks:
                await asyncio.sleep(delay)
                yield chunk
        finally:
            closed.append(True)

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.models.generate_content_stream = AsyncMock(return_value=responses())
    constructor = Mock()
    constructor.return_value.aio = client
    monkeypatch.setattr(genai, "Client", constructor)
    return constructor, closed


def _chunk(text: str, *, finish: str | None = "STOP") -> types.GenerateContentResponse:
    return types.GenerateContentResponse.model_validate(
        {
            "model_version": "gemma-4-31b-it",
            "candidates": [
                {"content": {"parts": [{"text": text}]}, "finish_reason": finish}
            ],
        }
    )


def test_stream_assembly_and_private_thought_exclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only public fragments are assembled; cumulative usage is counted once."""
    first = _chunk('{"pro', finish=None)
    assert first.candidates and first.candidates[0].content
    first.candidates[0].content.parts = [
        types.Part(text="private reasoning", thought=True),
        types.Part(text='{"pro'),
    ]
    last = _chunk('posals":[]}')
    last.usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=100,
        candidates_token_count=20,
        thoughts_token_count=5,
    )
    constructor, closed = _sdk(monkeypatch, [first, last])

    result = asyncio.run(
        stream_text(
            "test-key",
            "gemma-4-31b-it",
            "public text",
            types.GenerateContentConfig(response_mime_type="application/json"),
            1,
        )
    )

    assert orjson.loads(result.response) == {"proposals": []}
    assert "private reasoning" not in repr(result)
    assert (result.input_tokens, result.output_tokens) == (100, 25)
    assert closed == [True]
    constructor.return_value.aio.__aexit__.assert_awaited_once()
    assert constructor.call_args.kwargs["http_options"].retry_options.attempts == 1


@pytest.mark.parametrize("finish", [None, "MAX_TOKENS", "SAFETY"])
def test_incomplete_stream_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    finish: str | None,
) -> None:
    """Valid-looking JSON cannot conceal a truncated or blocked generation."""
    _, closed = _sdk(monkeypatch, [_chunk('{"proposals":[]}', finish=finish)])
    with pytest.raises(TextProtocolError, match="gemini_incomplete_response"):
        asyncio.run(
            stream_text(
                "test-key",
                "gemma-4-31b-it",
                "public",
                types.GenerateContentConfig(),
                1,
            )
        )
    assert closed == [True]


def test_silent_stream_absolute_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream that has not produced its first chunk still obeys the deadline."""
    constructor, closed = _sdk(monkeypatch, [_chunk("{}")], delay=0.1)
    with pytest.raises(TimeoutError):
        asyncio.run(
            stream_text(
                "test-key",
                "gemma-4-31b-it",
                "public",
                types.GenerateContentConfig(),
                0.005,
            )
        )
    assert closed == [True]
    constructor.return_value.aio.__aexit__.assert_awaited_once()


def test_response_byte_limit_closes_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Oversized UTF-8 output is rejected before interpretation or persistence."""
    _, closed = _sdk(monkeypatch, [_chunk("x" * (MAX_RESPONSE_BYTES + 1))])
    with pytest.raises(TextProtocolError, match="gemini_response_limit"):
        asyncio.run(
            stream_text(
                "test-key",
                "gemma-4-31b-it",
                "public",
                types.GenerateContentConfig(),
                1,
            )
        )
    assert closed == [True]
