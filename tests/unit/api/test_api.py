"""Saved synthetic contract tests; no databases, vendors or model calls."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, create_autospec

import orjson
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from oxhack2026.api import schemas as s
from oxhack2026.api.app import create_app
from oxhack2026.api.export_contract import export_contract
from oxhack2026.api.repository import (
    ImmatureOutcome,
    PublishedRepository,
    RepositoryUnavailable,
    ResourceNotFound,
)

FIXTURE = Path("tests/fixtures/api/scouting.json")
BATCH = "synthetic-npm-2025-01-06"


class FixtureBundle(BaseModel):
    """Validate every saved response before installing mocked repository reads."""

    catalog: s.Catalog
    cutoffs: s.Cutoffs
    forecast: s.ForecastBatch
    rankings: s.Rankings
    reveal: s.Reveal
    history: s.History
    evaluation: s.Evaluation
    data_health: s.DataHealth


@pytest.fixture
def bundle() -> FixtureBundle:
    """Return validated, unmistakably synthetic public-response fixtures."""
    return FixtureBundle.model_validate(orjson.loads(FIXTURE.read_bytes()))


@pytest.fixture
def repository(bundle: FixtureBundle) -> Mock:
    """Return mocked storage/scoring methods with no external side effects."""
    mock: Mock = create_autospec(PublishedRepository, instance=True)
    mock.readiness.return_value = s.Health(status="ready")
    for name in FixtureBundle.model_fields:
        getattr(mock, name).return_value = getattr(bundle, name)
    return mock


@pytest.fixture
def client(repository: Mock) -> Iterator[TestClient]:
    """Yield an in-process API client; close its transport after the test."""
    with TestClient(create_app(repository)) as transport:
        yield transport


@pytest.mark.parametrize(
    "path",
    [
        "/health/live",
        "/health/ready",
        "/catalog",
        "/cutoffs",
        f"/catalog?batch_id={BATCH}&ecosystem=npm",
        "/cutoffs?ecosystem=npm&target_id=downloads_next_30d_v1",
        f"/forecasts/{BATCH}",
        f"/rankings/{BATCH}",
        f"/tools/tool-1/history?batch_id={BATCH}",
        "/evaluations/synthetic-evaluation-v1",
        "/data-health",
    ],
)
def test_reads(client: TestClient, path: str) -> None:
    """Public reads return validated published DTOs for supported identifiers."""
    response = client.get(f"/api/v1{path}")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/catalog?ecosystem=unknown",
        "/cutoffs?target_id=bad",
        "/forecasts/bad%20id",
        f"/tools/tool-1/history?batch_id={BATCH}&limit=3661",
        "/tools/tool-1/history",
    ],
)
def test_invalid_queries(client: TestClient, path: str) -> None:
    """Reject invalid IDs, unsupported targets and unbounded history reads."""
    assert client.get(f"/api/v1{path}").status_code == 422


@pytest.mark.parametrize(
    "selection",
    [
        ["org-1", "org-1"],
        [f"org-{i}" for i in range(6)],
        ["unknown"],
        ["org-7"],
        ["bad id"],
    ],
)
def test_invalid_shortlists(
    client: TestClient, repository: Mock, selection: list[str]
) -> None:
    """Reject duplicate, oversized, unknown and ineligible selections."""
    response = client.post(
        f"/api/v1/replays/{BATCH}/reveal", json={"organization_ids": selection}
    )
    assert response.status_code == 422
    repository.reveal.assert_not_called()


def test_reveal_does_not_change_forecast(
    client: TestClient, bundle: FixtureBundle, repository: Mock
) -> None:
    """Outcome values arrive only through reveal; the forecast remains unchanged."""
    before = client.get(f"/api/v1/forecasts/{BATCH}")
    selection = bundle.reveal.selected_organization_ids
    response = client.post(
        f"/api/v1/replays/{BATCH}/reveal", json={"organization_ids": selection}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "actual_downloads" in response.text
    assert "actual_downloads" not in before.text
    assert "realized_growth" not in before.text
    assert client.get(f"/api/v1/forecasts/{BATCH}").content == before.content
    repository.reveal.assert_called_once_with(
        BATCH, s.RevealRequest(organization_ids=selection)
    )


@pytest.mark.parametrize(
    "error,status",
    [(ImmatureOutcome, 409), (ResourceNotFound, 404), (RepositoryUnavailable, 503)],
)
def test_repository_errors(
    client: TestClient, repository: Mock, error: type[Exception], status: int
) -> None:
    """Map adapter errors without echoing secrets from internal messages."""
    repository.reveal.side_effect = error("private database configuration")
    response = client.post(
        f"/api/v1/replays/{BATCH}/reveal", json={"organization_ids": []}
    )
    assert response.status_code == status
    assert "private" not in response.text


def test_unconfigured_factory() -> None:
    """Unconfigured startup permits health/schema access but never fake results."""
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503
        assert client.get("/api/v1/cutoffs").status_code == 503
        assert client.get("/openapi.json").status_code == 200


def test_unready_repository(client: TestClient, repository: Mock) -> None:
    """A running process cannot report ready with unavailable required artifacts."""
    repository.readiness.return_value = s.Health(
        status="unavailable", reasons=("missing_artifact",)
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    response_schema = create_app().openapi()["paths"]["/api/v1/health/ready"]["get"][
        "responses"
    ]["503"]["content"]["application/json"]["schema"]
    assert {item["$ref"] for item in response_schema["anyOf"]} == {
        "#/components/schemas/Health",
        "#/components/schemas/Error",
    }


def test_history_future_boundary(
    client: TestClient, repository: Mock, bundle: FixtureBundle
) -> None:
    """Fail closed when an adapter returns a future measurement or availability."""
    point = bundle.history.points[0]
    future = datetime(2025, 2, 1, tzinfo=UTC)
    for invalid in (
        point.model_copy(update={"available_at": future}),
        point.model_copy(
            update={"window": s.Window(start=point.window.start, end=future)}
        ),
    ):
        repository.history.return_value = bundle.history.model_copy(
            update={"points": (invalid,)}
        )
        assert (
            client.get(f"/api/v1/tools/tool-1/history?batch_id={BATCH}").status_code
            == 503
        )


def test_history_unknown_tool(client: TestClient, repository: Mock) -> None:
    """Unknown batch members never trigger an unrestricted repository history read."""
    assert (
        client.get(f"/api/v1/tools/unknown/history?batch_id={BATCH}").status_code == 404
    )
    repository.history.assert_not_called()


def test_inconsistent_publication(
    client: TestClient, repository: Mock, bundle: FixtureBundle
) -> None:
    """Reject wrong versions and duplicate organizations in published rankings."""
    repository.catalog.return_value = bundle.catalog.model_copy(
        update={"mapping_version": "other"}
    )
    assert client.get(f"/api/v1/catalog?batch_id={BATCH}").status_code == 503
    repository.rankings.return_value = bundle.rankings.model_copy(
        update={"primary": s.Ranking(name="invalid", tool_ids=("tool-1", "tool-1"))}
    )
    assert client.get(f"/api/v1/rankings/{BATCH}").status_code == 503


def test_reveal_exact_selection(
    client: TestClient, repository: Mock, bundle: FixtureBundle
) -> None:
    """A mismatched scorer result cannot be attributed to the user's selection."""
    repository.reveal.return_value = bundle.reveal
    assert (
        client.post(
            f"/api/v1/replays/{BATCH}/reveal", json={"organization_ids": ["org-1"]}
        ).status_code
        == 503
    )


def test_null_and_zero_are_distinct(client: TestClient) -> None:
    """Partial history preserves missingness separately from measured zero."""
    points = client.get(f"/api/v1/tools/tool-1/history?batch_id={BATCH}").json()[
        "points"
    ]
    assert points[0]["downloads"] == 0
    assert points[1]["downloads"] is None


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "https://name:secret@example.com",
        "https://example.com?key=secret",
    ],
)
def test_unsafe_public_links(value: str) -> None:
    """Public links cannot execute script or carry credential-bearing URLs."""
    with pytest.raises(ValidationError):
        s.ReportLink(label="Unsafe", url=value)


def test_schema_guards(bundle: FixtureBundle) -> None:
    """Reject future actuals, contradictory states, nonfinite values and bad windows."""
    payload = bundle.forecast.model_dump()
    with pytest.raises(ValidationError):
        s.ForecastBatch.model_validate({**payload, "actual_downloads": 100})
    result = bundle.forecast.results[0].model_dump()
    for update in (
        {"predicted_downloads": float("nan")},
        {"availability": "unavailable"},
        {"predicted_growth_pct": None},
    ):
        with pytest.raises(ValidationError):
            s.Forecast.model_validate({**result, **update})
    for start, end in (
        ("2025-01-01", "2025-01-02"),
        ("2025-01-01T01:00:00+01:00", "2025-01-02T00:00:00Z"),
        ("2025-01-02T00:00:00Z", "2025-01-01T00:00:00Z"),
    ):
        with pytest.raises(ValidationError):
            s.Window.model_validate({"start": start, "end": end})
    with pytest.raises(ValidationError):
        s.Interval(
            lower=20,
            upper=10,
            nominal_coverage=0.8,
            method="test",
            calibration_id="synthetic",
            status="validated",
        )


def test_openapi_drift_and_outcome_separation() -> None:
    """Committed schema is reproducible and the forecast graph cannot reach outcomes."""
    assert export_contract(Path("contracts/api/openapi.json"), check=True)
    schema = create_app().openapi()
    visited: set[str] = set()
    pending = ["ForecastBatch", "Rankings", "Catalog", "History", "Cutoffs"]
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        serialized = orjson.dumps(schema["components"]["schemas"][name]).decode()
        assert "actual_downloads" not in serialized
        assert "realized_growth" not in serialized
        for candidate in schema["components"]["schemas"]:
            if f'#/components/schemas/{candidate}"' in serialized:
                pending.append(candidate)
    assert "Outcome" not in visited


def test_contract_export_mocked_filesystem() -> None:
    """Export writes canonical bytes without contacting an external service."""
    destination = Mock(spec=Path)
    assert export_contract(destination)
    assert destination.write_bytes.call_args.args[0].endswith(b"\n")
    destination.is_file.return_value = False
    assert export_contract(destination, check=True) is False


def test_catalog_search(client: TestClient) -> None:
    """Bounded text search filters verified catalogue metadata, not ranking policy."""
    response = client.get("/api/v1/catalog?q=Company%208")
    assert response.status_code == 200
    assert [tool["tool_id"] for tool in response.json()["tools"]] == ["tool-8"]
    assert client.get(f"/api/v1/catalog?q={'x' * 121}").status_code == 422


def test_revalidate_invalid_adapter_instances(
    client: TestClient, repository: Mock, bundle: FixtureBundle
) -> None:
    """A constructed/mutated model cannot bypass response-boundary validation."""
    invalid = bundle.forecast.results[0].model_copy(update={"predicted_downloads": -1})
    repository.forecast.return_value = bundle.forecast.model_copy(
        update={"results": (invalid,)}
    )
    assert client.get(f"/api/v1/forecasts/{BATCH}").status_code == 503


def test_retrospective_catalogue_cannot_appear_prospective(
    client: TestClient, repository: Mock, bundle: FixtureBundle
) -> None:
    """Only explicitly labelled reconstruction can show later mapping inspection."""
    original = bundle.catalog.tools[0]
    evidence = original.mapping_evidence[0].model_copy(
        update={"observed_at": datetime(2026, 1, 1, tzinfo=UTC)}
    )
    tool = original.model_copy(update={"mapping_evidence": (evidence,)})
    repository.catalog.return_value = bundle.catalog.model_copy(
        update={"tools": (tool,)}
    )
    assert client.get(f"/api/v1/catalog?batch_id={BATCH}").status_code == 503
    tool = tool.model_copy(update={"mapping_verification": "retrospective"})
    repository.catalog.return_value = bundle.catalog.model_copy(
        update={"tools": (tool,)}
    )
    assert client.get(f"/api/v1/catalog?batch_id={BATCH}").status_code == 200
    repository.forecast.return_value = bundle.forecast.model_copy(
        update={"mode": "prospective"}
    )
    assert client.get(f"/api/v1/catalog?batch_id={BATCH}").status_code == 503
