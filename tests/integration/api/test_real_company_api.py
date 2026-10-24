"""Opt-in real company API acceptance over a restored checksummed publication."""

import os

import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.company_runtime import create_company_app

pytestmark = pytest.mark.integration


def test_real_company_api_reads_all_outcomes_and_multiple_metric_families() -> None:
    """Real C1/C2 bytes pass public API, privacy and immutable-read gates."""
    if not os.environ.get("SIGNALSHIFT_COMPANY_ROOT"):
        pytest.skip("Set an explicit restored real company root and publication IDs")
    with TestClient(create_company_app()) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        choices = client.get("/api/v1/company-snapshots").json()["items"]
        assert choices
        for choice in choices:
            assert choice["source"]["synthetic"] is False
            snapshot_id = choice["source"]["snapshot_id"]
            prefix = f"/api/v1/company-snapshots/{snapshot_id}/companies"
            rows = client.get(prefix).json()["items"]
            assert len(rows) >= 2
            for row in rows:
                company_id = row["company"]["company_id"]
                response = client.get(f"{prefix}/{company_id}")
                assert response.status_code == 200
                detail = response.json()
                assert detail["assessment"]["synthetic"] is False
                assert len(detail["assessment"]["outcomes"]) == 3
                assert all(
                    outcome["probability"] is None
                    for outcome in detail["assessment"]["outcomes"]
                )
                families = {
                    definition["family"] for definition in detail["definitions"]
                }
                assert families == {
                    "traction",
                    "commercial",
                    "execution",
                    "market_financing",
                }
                assert any(
                    metric["state"] == "observed" for metric in detail["metrics"]
                )
                assert any(metric["state"] == "missing" for metric in detail["metrics"])
                assert detail["evidence"]
                for forbidden in (
                    "raw_artifact",
                    "locator",
                    "label_state",
                    "success_score",
                ):
                    assert forbidden not in response.text
                assert client.get(f"{prefix}/{company_id}").content == response.content
