"""Provider configuration, structured output and bounded failure regressions."""

import time
from unittest.mock import AsyncMock

import pytest
from google.genai import errors, types
from pydantic import BaseModel

from oxhack2026.explanations import config, gemini_text
from oxhack2026.explanations.gemini import (
    GeminiInterpreter,
    MappingUnavailable,
    proposal_schema,
)
from oxhack2026.explanations.gemini_text import TextResult
from oxhack2026.research.analysis import AnalysisBatch


@pytest.mark.parametrize("schema", [None, AnalysisBatch])
def test_gemma_structured_text_and_usage(
    monkeypatch: pytest.MonkeyPatch, schema: type[BaseModel] | None
) -> None:
    """An explicit Gemma override requests native structured text without audio."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemma-4-31b-it")
    monkeypatch.setattr(GeminiInterpreter, "_reserve", lambda self, tokens: None)
    request = AsyncMock(
        return_value=TextResult(
            response='{"proposals":[]}',
            model_version="gemma-4-31b-it",
            input_tokens=100,
            output_tokens=25,
            grounding=(),
        )
    )
    monkeypatch.setattr(gemini_text, "stream_text", request)

    interpreter = GeminiInterpreter(time.monotonic() + 5)
    result = interpreter.generate("bounded public source data", schema)

    assert result == '{"proposals":[]}'
    assert interpreter.model == "gemma-4-31b-it"
    assert interpreter.model_version == "gemma-4-31b-it"
    assert (interpreter.input_tokens, interpreter.output_tokens) == (100, 25)
    assert request.await_args is not None
    key, model, prompt, configuration, timeout = request.await_args.args
    assert key == "test-key"
    assert model == "gemma-4-31b-it"
    assert prompt == "bounded public source data"
    assert configuration.response_mime_type == "application/json"
    assert configuration.response_schema == proposal_schema(compact=True, output=schema)
    assert configuration.thinking_config.thinking_level == types.ThinkingLevel.HIGH
    assert configuration.tools is None
    assert 0 < timeout <= 5


def test_explicit_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contributors can explicitly select a different structured-text model."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    assert GeminiInterpreter(0).model == "gemini-2.5-flash"


def test_gemma_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemma is the default; an explicit rules override disables it."""
    monkeypatch.delenv("SIGNALSHIFT_RESEARCH_MAPPING_MODE", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert config.mapping_mode() == "rules_gemini"
    assert GeminiInterpreter(0).model == "gemma-4-31b-it"
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_MAPPING_MODE", "rules")
    assert config.mapping_mode() == "rules"


def test_provider_error_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider details, including credential-bearing messages, never reach reports."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(GeminiInterpreter, "_reserve", lambda self, tokens: None)
    request = AsyncMock(
        side_effect=errors.ClientError(
            429, {"error": {"message": "sensitive provider detail"}}
        )
    )
    monkeypatch.setattr(gemini_text, "stream_text", request)
    with pytest.raises(MappingUnavailable, match=r"^gemini_rate_limited$"):
        GeminiInterpreter(time.monotonic() + 3, model="gemma-4-31b-it").generate(
            "source data"
        )


def test_shared_key_override_without_process_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A personal key, including blank, overrides the private team's shared default."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        config, "dotenv_values", lambda path: {"GEMINI_API_KEY": "shared"}
    )
    assert config.gemini_api_key() == "shared"
    monkeypatch.setenv("GEMINI_API_KEY", "personal")
    assert config.gemini_api_key() == "personal"
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert config.gemini_api_key() == ""


@pytest.mark.parametrize(
    "error,reason",
    [
        (errors.ServerError(500, {}), "gemini_provider_internal_error"),
        (errors.ServerError(502, {}), "gemini_provider_bad_gateway"),
        (errors.ServerError(503, {}), "gemini_provider_overloaded"),
        (errors.ServerError(504, {}), "gemini_provider_timeout"),
        (TimeoutError("sensitive detail"), "gemini_request_timeout"),
    ],
)
def test_precise_safe_provider_failure(
    monkeypatch: pytest.MonkeyPatch, error: Exception, reason: str
) -> None:
    """Retain actionable status codes without copying provider messages."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(GeminiInterpreter, "_reserve", lambda self, tokens: None)
    monkeypatch.setattr(gemini_text, "stream_text", AsyncMock(side_effect=error))
    with pytest.raises(MappingUnavailable, match=f"^{reason}$"):
        GeminiInterpreter(time.monotonic() + 3).generate("public source")
