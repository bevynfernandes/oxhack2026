"""Discovery retains inactive companies without inventing historical outcome labels."""

from pathlib import Path

import orjson
import pytest

from oxhack2026.ingest.company_cohort import (
    CohortDiscoverySettings,
    CompanyFollowup,
    parse_cohort,
)


@pytest.fixture
def yc_rows() -> bytes:
    """Read an explicitly synthetic small directory fixture."""
    return Path("tests/fixtures/data/yc-discovery.json").read_bytes()


def test_complete_batch_preserves_all_statuses(yc_rows: bytes) -> None:
    """Every current status survives discovery, with no inferred historical identity."""
    rows = parse_cohort(yc_rows, "Winter 2020")
    assert tuple(row.directory_status for row in rows) == (
        "Active",
        "Inactive",
        "Acquired",
    )
    assert all(
        not row.historical_identity_verified and row.family_id is None for row in rows
    )
    followup = CompanyFollowup(company_id="yc-2", outcome_id="operating_growth_24m_v1")
    assert followup.label is None
    assert followup.state == "pending_source_review"
    with pytest.raises(ValueError):
        CompanyFollowup.model_validate(followup.model_dump() | {"label": False})


@pytest.mark.parametrize("problem", ["duplicate", "wrong_batch", "wrong_host", "empty"])
def test_invalid_batch_is_rejected_without_dropping_rows(
    yc_rows: bytes, problem: str
) -> None:
    """Invalid records fail a batch instead of silently changing cohort composition."""
    rows = orjson.loads(yc_rows)
    if problem == "duplicate":
        rows.append(rows[0])
    elif problem == "wrong_batch":
        rows[0]["batch"] = "Summer 2020"
    elif problem == "wrong_host":
        rows[0]["url"] = "https://example.com/companies/other"
    else:
        rows = []
    with pytest.raises(ValueError):
        parse_cohort(orjson.dumps(rows), "Winter 2020")


def test_discovery_config_pins_safe_commit_url() -> None:
    """A mutable branch name or path traversal cannot replace a reviewed commit."""
    settings = {
        "cohort_version": "test-v1",
        "batch_slug": "winter-2020",
        "batch_name": "Winter 2020",
        "source_revision": "a" * 40,
        "code_revision": "b" * 40,
    }
    assert (
        "/" + "a" * 40 + "/"
        in CohortDiscoverySettings.model_validate(settings).source_url
    )
    with pytest.raises(ValueError):
        CohortDiscoverySettings.model_validate(settings | {"source_revision": "main"})
    with pytest.raises(ValueError):
        CohortDiscoverySettings.model_validate(settings | {"batch_slug": "../secret"})
