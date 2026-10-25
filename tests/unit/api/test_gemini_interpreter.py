"""Provider configuration, structured output and bounded failure regressions."""

import time
from unittest.mock import Mock

import pytest
from google import genai
from google.genai import errors, types

from oxhack2026.explanations import config
from oxhack2026.explanations.gemini import GeminiInterpreter, MappingUnavailable


def test_gemma_structured_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit Gemma override requests native structured text without audio."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemma-4-31b-it")
    monkeypatch.setattr(GeminiInterpreter, "_reserve", lambda self, tokens: None)
    response = types.GenerateContentResponse(
        model_version="gemma-4-31b-it",
        candidates=[
            types.Candidate(
                content=types.Content(
                    parts=[
                        types.Part(text='{"proposals":[]}'),
                    ]
                )
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100,
            candidates_token_count=20,
            thoughts_token_count=5,
        ),
    )
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.models.generate_content.return_value = response
    constructor = Mock(return_value=client)
    monkeypatch.setattr(genai, "Client", constructor)

    interpreter = GeminiInterpreter(time.monotonic() + 5)
    result = interpreter.generate("bounded public source data")

    assert result == '{"proposals":[]}'
    assert interpreter.model == "gemma-4-31b-it"
    assert interpreter.model_version == "gemma-4-31b-it"
    assert (interpreter.input_tokens, interpreter.output_tokens) == (100, 25)
    request = client.models.generate_content.call_args.kwargs
    assert request["model"] == "gemma-4-31b-it"
    assert request["config"].response_mime_type == "application/json"
    assert request["config"].response_schema is not None
    assert (
        request["config"].thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    )
    assert request["config"].tools is None
    assert constructor.call_args.kwargs["http_options"].retry_options.attempts == 1


def test_explicit_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contributors can explicitly select a different structured-text model."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    assert GeminiInterpreter(0).model == "gemini-2.5-flash"


def test_gemini_live_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini Live is the default; an explicit rules override disables it."""
    monkeypatch.delenv("SIGNALSHIFT_RESEARCH_MAPPING_MODE", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert config.mapping_mode() == "rules_gemini"
    assert GeminiInterpreter(0).model == "gemini-3.8-live-extended-thinking"
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_MAPPING_MODE", "rules")
    assert config.mapping_mode() == "rules"


def test_provider_error_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider details, including credential-bearing messages, never reach reports."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(GeminiInterpreter, "_reserve", lambda self, tokens: None)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.models.generate_content.side_effect = errors.ClientError(
        429, {"error": {"message": "sensitive provider detail"}}
    )
    monkeypatch.setattr(genai, "Client", Mock(return_value=client))
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
