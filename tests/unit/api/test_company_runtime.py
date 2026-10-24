"""Configuration and exact-reader composition without filesystem or vendor access."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.company_runtime import create_company_app
from oxhack2026.api.schemas import Health


@pytest.mark.parametrize(
    "root,publications", [("", ""), ("mock", ""), ("", "v1"), ("mock", "bad/id")]
)
def test_missing_or_invalid_configuration_never_loads_fixtures(
    monkeypatch: pytest.MonkeyPatch, root: str, publications: str
) -> None:
    """Unconfigured production is live but has no usable data or synthetic fallback."""
    monkeypatch.setenv("SIGNALSHIFT_COMPANY_ROOT", root)
    monkeypatch.setenv("SIGNALSHIFT_COMPANY_PUBLICATIONS", publications)
    with TestClient(create_company_app()) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503
        assert client.get("/api/v1/company-snapshots").status_code == 503


def test_runtime_composes_only_explicit_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime never resolves current/latest or executes ingestion/model code."""
    monkeypatch.setenv("SIGNALSHIFT_COMPANY_ROOT", "/mock/company-root")
    monkeypatch.setenv("SIGNALSHIFT_COMPANY_PUBLICATIONS", "first-v1, second-v2")
    with (
        patch("oxhack2026.api.company_runtime._dimension_registry", return_value=None),
        patch("oxhack2026.api.company_runtime.LocalCompanyStore") as sources,
        patch("oxhack2026.api.company_runtime.LocalCompanyAssessmentStore") as models,
        patch(
            "oxhack2026.api.company_runtime.PublishedCompanyRepository"
        ) as repository,
    ):
        repository.return_value.readiness.return_value = Health(status="ready")
        with TestClient(create_company_app()) as client:
            assert client.get("/api/v1/health/ready").status_code == 200
        sources.assert_called_once_with(Path("/mock/company-root"))
        models.assert_called_once_with(Path("/mock/company-root"))
        repository.assert_called_once_with(
            sources.return_value,
            models.return_value,
            ("first-v1", "second-v2"),
            dimension_models=None,
        )
