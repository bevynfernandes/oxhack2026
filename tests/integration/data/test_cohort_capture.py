"""Real-file discovery checkpoint replay with mocked network transport."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from oxhack2026.ingest.company_cohort import (
    CohortDiscoverySettings,
    collect_cohort,
    load_cohort,
)

pytestmark = pytest.mark.integration


def test_cohort_is_immutable_replayable_and_complete() -> None:
    """Retries use exact archived bytes; configuration changes require a new ID."""
    root = Path("tests/outputs/cohort-capture") / uuid4().hex
    settings = CohortDiscoverySettings(
        cohort_version="test-v1",
        batch_slug="winter-2020",
        batch_name="Winter 2020",
        source_revision="a" * 40,
        code_revision="b" * 40,
    )
    raw = Path("tests/fixtures/data/yc-discovery.json").read_bytes()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=raw, request=request)
    )
    client = httpx.Client(transport=transport)
    with patch("oxhack2026.ingest.company_cohort.httpx.Client", return_value=client):
        first = collect_cohort(settings, root)
    with patch("httpx.Client.send", side_effect=AssertionError("unexpected HTTP")):
        assert collect_cohort(settings, root) == first
    assert len(first.companies) == 3
    assert len(first.followups) == 9
    assert all(row.label is None for row in first.followups)
    changed = settings.model_copy(update={"source_revision": "c" * 40})
    with pytest.raises(ValueError, match="configuration"):
        collect_cohort(changed, root)
    assert load_cohort(root, settings.cohort_version) == first
    (root / first.raw_artifact.path).write_bytes(b"corruption")
    with pytest.raises(ValueError, match="SHA-256"):
        load_cohort(root, settings.cohort_version)
