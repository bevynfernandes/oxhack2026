"""Isolated wire-contract tests for asynchronous Live evidence interpretation."""

import asyncio
from typing import Self
from unittest.mock import Mock

import orjson
import pytest
from websockets.exceptions import ConnectionClosedError

from oxhack2026.explanations import gemini_live
from oxhack2026.explanations.config import DEFAULT_MODEL
from oxhack2026.explanations.gemini import proposal_schema


class FakeSocket:
    """Async socket fixture with explicit server completion frames."""

    def __init__(self, frames: list[dict[str, object]]) -> None:
        self.frames = iter(frames)
        self.sent: list[dict[str, object]] = []

    async def __aenter__(self) -> Self:
        """Open the isolated fixture."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Release the fixture without real network resources."""

    async def recv(self) -> bytes:
        """Return the next saved server frame."""
        return orjson.dumps(next(self.frames))

    async def send(self, value: str) -> None:
        """Retain client messages for protocol assertions."""
        self.sent.append(orjson.loads(value))


def test_live_waits_for_idle_and_discards_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither turnComplete nor an empty proposal set truncates background work."""
    socket = FakeSocket(
        [
            {"setupComplete": {}},
            {
                "serverContent": {"turnComplete": True},
                "interactionStatus": "IN_PROGRESS",
            },
            {
                "toolCall": {
                    "functionCalls": [
                        {
                            "id": "call",
                            "name": "submit_evidence",
                            "args": {"proposals": []},
                        }
                    ]
                }
            },
            {
                "serverContent": {
                    "modelTurn": {
                        "parts": [
                            {
                                "inlineData": {"mimeType": "audio/pcm", "data": "AAAA"},
                            }
                        ]
                    }
                },
                "interactionStatus": "IN_PROGRESS",
            },
            {
                "interactionStatus": "IDLE",
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "responseTokenCount": 20,
                    "thoughtsTokenCount": 10,
                },
            },
        ]
    )
    connector = Mock(return_value=socket)
    monkeypatch.setattr(gemini_live, "connect", connector)
    result = asyncio.run(
        gemini_live.generate_live(
            "test-key",
            DEFAULT_MODEL,
            "source blocks",
            proposal_schema(),
            2,
        )
    )
    assert result.response == '{"proposals":[]}'
    assert (result.input_tokens, result.output_tokens) == (100, 30)
    setup = socket.sent[0]["setup"]
    assert isinstance(setup, dict)
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert "outputAudioTranscription" in setup
    assert "toolResponse" in socket.sent[-1]
    assert "test-key" not in connector.call_args.args[0]


def test_live_answer_text_excludes_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A text answer is available without persisting audio or internal thoughts."""
    socket = FakeSocket(
        [
            {"setupComplete": {}},
            {
                "serverContent": {
                    "modelTurn": {
                        "parts": [
                            {"text": "internal reasoning", "thought": True},
                            {"text": '{"proposals":[]}'},
                        ]
                    },
                    "interaction_status": "IDLE",
                }
            },
        ]
    )
    monkeypatch.setattr(gemini_live, "connect", Mock(return_value=socket))
    result = asyncio.run(
        gemini_live.generate_live(
            "test-key",
            DEFAULT_MODEL,
            "source blocks",
            proposal_schema(),
            2,
        )
    )
    assert result.response == '{"proposals":[]}'


def test_live_unexpected_tool_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Untrusted source instructions cannot invoke arbitrary functions."""
    socket = FakeSocket(
        [
            {"setupComplete": {}},
            {"toolCall": {"functionCalls": [{"name": "browse", "args": {}}]}},
        ]
    )
    monkeypatch.setattr(gemini_live, "connect", Mock(return_value=socket))
    with pytest.raises(gemini_live.LiveProtocolError, match="unexpected_tool"):
        asyncio.run(
            gemini_live.generate_live(
                "test-key",
                DEFAULT_MODEL,
                "source blocks",
                proposal_schema(),
                2,
            )
        )


def test_provider_schema_has_no_unsupported_metadata() -> None:
    """The provider receives inline Schema; local Pydantic validation stays strict."""
    schema = orjson.dumps(proposal_schema())
    assert b"$ref" not in schema
    assert b"additionalProperties" not in schema
    assert b"qualifier" in schema


def test_live_preserves_submission_if_background_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain received results with explicit partiality if background work stalls."""
    socket = FakeSocket(
        [
            {"setupComplete": {}},
            {
                "toolCall": {
                    "functionCalls": [
                        {
                            "id": "call",
                            "name": "submit_evidence",
                            "args": {"proposals": []},
                        }
                    ]
                }
            },
        ]
    )
    original = socket.recv
    calls = 0

    async def receive() -> bytes:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise TimeoutError
        return await original()

    monkeypatch.setattr(socket, "recv", receive)
    monkeypatch.setattr(gemini_live, "connect", Mock(return_value=socket))
    result = asyncio.run(
        gemini_live.generate_live(
            "test-key",
            DEFAULT_MODEL,
            "source blocks",
            proposal_schema(),
            2,
        )
    )
    assert result.response == '{"proposals":[]}'
    assert result.reason_code == "gemini_live_background_incomplete"


@pytest.mark.parametrize("submitted", [False, True])
def test_live_connection_loss_retains_only_received_submissions(
    monkeypatch: pytest.MonkeyPatch, submitted: bool
) -> None:
    """A transport failure must preserve received results and expose partiality."""
    frames: list[dict[str, object]] = [{"setupComplete": {}}]
    if submitted:
        frames.append(
            {
                "toolCall": {
                    "functionCalls": [
                        {
                            "id": "call",
                            "name": "submit_evidence",
                            "args": {"proposals": []},
                        }
                    ]
                }
            }
        )
    socket = FakeSocket(frames)
    calls = 0
    original = socket.recv

    async def receive() -> bytes:
        nonlocal calls
        calls += 1
        if calls > len(frames):
            raise ConnectionClosedError(None, None)
        return await original()

    monkeypatch.setattr(socket, "recv", receive)
    monkeypatch.setattr(gemini_live, "connect", Mock(return_value=socket))
    request = gemini_live.generate_live(
        "test-key", DEFAULT_MODEL, "source blocks", proposal_schema(), 2
    )
    if not submitted:
        with pytest.raises(ConnectionClosedError):
            asyncio.run(request)
        return

    result = asyncio.run(request)

    assert result.response == '{"proposals":[]}'
    assert result.reason_code == "gemini_live_background_interrupted"


def test_reuses_live_connection_for_independent_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple bounded turns share setup and wait for a separate IDLE each time."""
    from oxhack2026.explanations.gemini_live import LiveSession

    socket = FakeSocket(
        [
            {"setupComplete": {}},
            {
                "serverContent": {
                    "modelTurn": {"parts": [{"text": '{"proposals":[]}'}]},
                    "interactionStatus": "IDLE",
                }
            },
            {
                "serverContent": {
                    "modelTurn": {"parts": [{"text": '{"proposals":[]}'}]},
                    "interactionStatus": "IDLE",
                }
            },
        ]
    )
    connector = Mock(return_value=socket)
    monkeypatch.setattr(gemini_live, "connect", connector)

    async def run() -> None:
        session = LiveSession("test-key", DEFAULT_MODEL)
        try:
            await session.generate("first source", proposal_schema(), 2)
            await session.generate("second source", proposal_schema(), 2)
        finally:
            await session.close()

    asyncio.run(run())
    assert connector.call_count == 1
    assert sum("setup" in value for value in socket.sent) == 1
    assert sum("clientContent" in value for value in socket.sent) == 2
