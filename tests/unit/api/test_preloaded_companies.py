"""Real preloaded input integrity and locally recomputed inference, without vendors."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.company_repository import PublishedCompanyRepository
from oxhack2026.api.company_runtime import (
    PRELOADED_COMPANY_ROOT,
    PRELOADED_PUBLICATION_ID,
    create_company_app,
)
from oxhack2026.api.repository import RepositoryUnavailable
from oxhack2026.models.dimension_serving import (
    DEFAULT_DIMENSION_MODEL_ROOT,
    DimensionModelRegistry,
)
from oxhack2026.models.public_dimensions import NumericDimensionModel
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore


@pytest.fixture
def preloaded_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Select the packaged examples and disable optional external work."""
    for key in (
        "SIGNALSHIFT_COMPANY_ROOT",
        "SIGNALSHIFT_COMPANY_PUBLICATIONS",
        "SIGNALSHIFT_RESEARCH_ROOT",
        "SIGNALSHIFT_DIMENSION_MODELS_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SIGNALSHIFT_PRELOADED_COMPANIES", "1")
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_ENABLED", "0")
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_MAPPING_ENABLED", "0")


@pytest.mark.usefixtures("preloaded_environment")
def test_default_runtime_exposes_two_complete_input_profiles() -> None:
    """Both real examples work offline with five populated views and local models."""
    with (
        patch(
            "httpx.HTTPTransport.handle_request",
            side_effect=AssertionError("Vendor request"),
        ),
        TestClient(create_company_app()) as client,
    ):
        assert client.get("/api/v1/health/ready").status_code == 200
        publication = client.get("/api/v1/company-snapshots").json()["items"][0]
        assert publication["assessment"]["publication_id"] == PRELOADED_PUBLICATION_ID
        assert publication["source"]["synthetic"] is False
        prefix = f"/api/v1/company-snapshots/{PRELOADED_PUBLICATION_ID}/companies"
        assert {
            row["company"]["company_id"] for row in client.get(prefix).json()["items"]
        } == {"qdrant", "weaviate"}
        for company_id in ("qdrant", "weaviate"):
            response = client.get(f"{prefix}/{company_id}")
            assert response.status_code == 200
            profile = response.json()
            assert profile["company"]["business_model"]
            assert profile["company"]["stage"]
            assert len(profile["metrics"]) == len(profile["definitions"]) == 11
            assert all(
                section["data_status"] == "available"
                and section["usable_metric_observation_ids"]
                for section in profile["outlook"]["specialists"]
            )
            dimensions = profile["dimension_models"]["dimensions"]
            assert all(row["eligibility"] == "eligible" for row in dimensions[:2])
            assert dimensions[1]["sample_size"] == 5
            assert all(row["score"] is None for row in dimensions[2:])
            assert all(
                row["prediction"] is None for row in profile["outlook"]["forecasts"]
            )
            missing = [row for row in profile["metrics"] if row["state"] == "missing"]
            assert len(missing) == 3
            assert all(row["value"] is None for row in missing)
            assert "raw_artifact" not in response.text
        assert client.get(f"{prefix}/unknown").status_code == 404
        assert (
            client.get("/api/v1/company-snapshots/unknown/companies").status_code == 404
        )


def test_model_outputs_are_computed_from_weights_and_source_inputs() -> None:
    """Changing loaded weights changes predictions without changing bundled inputs."""
    registry = DimensionModelRegistry.load(DEFAULT_DIMENSION_MODEL_ROOT)
    source = LocalCompanyStore(PRELOADED_COMPANY_ROOT).snapshot(
        "company-preloaded-20261025-v1"
    )
    before = source.model_dump_json()
    model = registry.models["adoption_retention"]
    assert isinstance(model, NumericDimensionModel)
    altered = replace(
        registry,
        models=registry.models
        | {
            "adoption_retention": model.model_copy(
                update={"intercept": model.intercept + 1}
            )
        },
    )

    original = registry.evaluate(source, "qdrant").dimensions[0]
    changed = altered.evaluate(source, "qdrant").dimensions[0]

    assert original.predicted_value != changed.predicted_value
    assert source.model_dump_json() == before
    assert "predicted_value" not in before
    assert '"score"' not in before


@pytest.mark.parametrize(
    "invalid", ["missing", "wrong_company", "wrong_count", "unreviewed"]
)
def test_saved_sentiment_requires_verified_named_sample(invalid: str) -> None:
    """Missing, misattributed and unverified titles cannot enable sentiment output."""
    source = LocalCompanyStore(PRELOADED_COMPANY_ROOT).snapshot(
        "company-preloaded-20261025-v1"
    )
    payload = source.model_dump(mode="json")
    metric = next(
        row
        for row in payload["metrics"]
        if row["company_id"] == "qdrant"
        and row["metric_id"] == "hn_retrieved_named_titles_v1"
    )
    if invalid == "missing":
        metric.update(state="missing", value=None, reason="Unavailable")
    elif invalid == "wrong_count":
        metric["value"]["value"] += 1
    else:
        for evidence in payload["evidence"]:
            if evidence["evidence_id"] in metric["evidence_ids"]:
                if invalid == "wrong_company":
                    evidence["assertion"] = "Another company released a database"
                else:
                    evidence["review_state"] = "unreviewed"
    modified = type(source).model_validate(payload)
    registry = DimensionModelRegistry.load(DEFAULT_DIMENSION_MODEL_ROOT)

    sentiment = registry.evaluate(modified, "qdrant").dimensions[1]

    assert sentiment.eligibility == "insufficient_data"
    assert sentiment.score is None


@pytest.mark.usefixtures("preloaded_environment")
def test_preloads_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit opt-out preserves the unconfigured unavailable behavior."""
    monkeypatch.setenv("SIGNALSHIFT_PRELOADED_COMPANIES", "0")
    with TestClient(create_company_app()) as client:
        assert client.get("/api/v1/company-snapshots").status_code == 503


@pytest.mark.usefixtures("preloaded_environment")
def test_preloaded_profiles_coexist_with_separate_read_only_research(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A standalone research root does not imply a legacy company-store root."""
    monkeypatch.setenv("SIGNALSHIFT_RESEARCH_ROOT", "/mock/research")
    with TestClient(create_company_app()) as client:
        assert client.get("/api/v1/company-snapshots").status_code == 200


def test_broken_preloaded_artifacts_fail_closed() -> None:
    """Integrity failures never fall back to unchecked example values."""
    repository = PublishedCompanyRepository(
        LocalCompanyStore(PRELOADED_COMPANY_ROOT),
        LocalCompanyAssessmentStore(PRELOADED_COMPANY_ROOT),
        (PRELOADED_PUBLICATION_ID,),
    )
    with (
        patch.object(Path, "open", side_effect=OSError("Corrupt artifact")),
        pytest.raises(RepositoryUnavailable),
    ):
        repository.company(PRELOADED_PUBLICATION_ID, "qdrant")


def test_bundled_sdk_totals_match_retained_daily_records() -> None:
    """Both model windows independently sum the actual retained npm daily inputs."""
    import orjson

    store = LocalCompanyStore(PRELOADED_COMPANY_ROOT)
    source = store.snapshot("company-preloaded-20261025-v1")
    for evidence in source.evidence:
        if evidence.provider != "npm":
            continue
        records = orjson.loads(store.artifacts.read(evidence.raw_artifact))["downloads"]
        for observation in source.metrics:
            if (
                observation.company_id != evidence.company_id
                or observation.metric_id
                not in {"npm_downloads_30d_v1", "npm_downloads_previous_30d_v1"}
            ):
                continue
            assert observation.window is not None
            assert observation.value is not None
            start = observation.window.start.date().isoformat()
            end = observation.window.end.date().isoformat()
            selected = [row for row in records if start <= row["day"] < end]
            assert len(selected) == 30
            assert sum(row["downloads"] for row in selected) == observation.value.value
