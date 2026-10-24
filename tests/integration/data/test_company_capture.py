"""Opt-in durable public capture replay with mocked HTTP and retained files."""

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from oxhack2026.ingest.capture import CaptureRequest, capture_get, freeze_run

pytestmark = pytest.mark.integration


def test_capture_restart_and_frozen_configuration() -> None:
    """Identical restart never refetches; a new run is a new vintage."""
    root = Path("tests/outputs/company-capture") / uuid4().hex
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"value": len(calls)})

    request = CaptureRequest(url="https://example.com/source")
    freeze_run(root, "first", b'{"version":1}')
    freeze_run(root, "first", b'{"version":1}')
    with pytest.raises(ValueError, match="frozen"):
        freeze_run(root, "first", b'{"version":2}')
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        first = capture_get(request, client, root, "first")
        assert capture_get(request, client, root, "first") == first
        second = capture_get(request, client, root, "second")
    assert len(calls) == 2
    assert first.artifact != second.artifact
