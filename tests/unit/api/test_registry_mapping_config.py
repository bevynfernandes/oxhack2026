"""Registry configuration defaults preserve exact-domain mapping boundaries."""

from pathlib import Path

import pytest

from oxhack2026.research.registry import registry_mapping_path


def test_packaged_mapping_is_available_without_a_local_test_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal checkout locates its bundled catalog without an ignored test file."""
    monkeypatch.delenv("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS", raising=False)
    path = registry_mapping_path()
    assert path.name == "reviewed-registry-mappings.json"
    assert path.parent.name == "bundled"


def test_operator_mapping_override_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit catalog never silently merges with bundled identities."""
    configured = Path("operator mappings.json")
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS", str(configured))
    assert registry_mapping_path() == configured
