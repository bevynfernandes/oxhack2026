"""Public company projection, immutable publication and redaction boundaries."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, create_autospec

import orjson
import pytest
from fastapi.testclient import TestClient

from oxhack2026.api.app import create_app
from oxhack2026.api.company_repository import (
    CompanyAssessmentReader,
    PublishedCompanyRepository,
)
from oxhack2026.api.repository import RepositoryUnavailable
from oxhack2026.catalog.company import CompanySourceSnapshot, DecimalValue
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import CompanySourceReader

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/api/companies.json"
SNAPSHOT = "synthetic-companies-v1"
PREFIX = f"/api/v1/company-snapshots/{SNAPSHOT}/companies"


@pytest.fixture
def company_readers() -> tuple[Mock, Mock]:
    """Return mocked source/assessment readers over saved synthetic publications."""
    payload = orjson.loads(FIXTURE.read_bytes())
    source = CompanySourceSnapshot.model_validate(payload["source"])
    assessments = tuple(
        CompanyAssessment.model_validate(row) for row in payload["assessments"]
    )
    sources = create_autospec(CompanySourceReader, instance=True)
    models = create_autospec(CompanyAssessmentReader, instance=True)
    sources.snapshot.return_value = source
    models.snapshot_ids.return_value = (SNAPSHOT,)
    models.assessments.return_value = assessments
    return sources, models


def _client(readers: tuple[Mock, Mock]) -> TestClient:
    return TestClient(
        create_app(company_repository=PublishedCompanyRepository(*readers))
    )


def test_company_routes_preserve_outcomes_zero_unknowns_and_sources(
    company_readers: tuple[Mock, Mock],
) -> None:
    """Every section survives projection; no raw artifacts or truth enter responses."""
    with _client(company_readers) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        choices = client.get("/api/v1/company-snapshots").json()
        listing = client.get(PREFIX).json()
        response = client.get(f"{PREFIX}/alpha")
        detail = response.json()

    assert choices["items"][0]["source"]["snapshot_id"] == SNAPSHOT
    assert [row["company"]["company_id"] for row in listing["items"]] == [
        "alpha",
        "beta",
    ]
    assert response.status_code == 200
    assert len(detail["assessment"]["outcomes"]) == 3
    assert detail["assessment"]["outcomes"][1]["assessment_status"] == "unavailable"
    assert all(row["probability"] is None for row in detail["assessment"]["outcomes"])
    assert detail["metrics"][0]["value"]["value"] == 0
    assert detail["metrics"][2]["value"] is None
    assert detail["metrics"][2]["state"] == "missing"
    assert len(detail["coverage"]) == 4
    assert detail["evidence"][0]["review_state"] == "verified"
    for forbidden in ("raw_artifact", "locator", "label_state", "success_score"):
        assert forbidden not in response.text
    assert detail["publication"] == listing["publication"]


def test_restricted_evidence_contents_and_urls_are_redacted(
    company_readers: tuple[Mock, Mock],
) -> None:
    """Attachment contents and private object locations never cross the API."""
    sources, _ = company_readers
    payload = sources.snapshot.return_value.model_dump(mode="json")
    payload["evidence"][0].update(
        access="restricted", url=None, assertion="private attachment contents"
    )
    sources.snapshot.return_value = CompanySourceSnapshot.model_validate(payload)

    with _client(company_readers) as client:
        response = client.get(f"{PREFIX}/alpha")

    assert response.status_code == 200
    assert response.json()["evidence"][0]["assertion"] is None
    assert response.json()["evidence"][0]["url"] is None
    assert "private attachment contents" not in response.text
    assert "raw_artifact" not in response.text


@pytest.mark.parametrize(
    "mutation",
    [
        "source_id",
        "cutoff",
        "synthetic",
        "family",
        "evidence",
        "metric",
        "event",
        "gap",
        "missing_company",
        "duplicate_company",
        "future_label",
    ],
)
def test_incompatible_assessment_sets_fail_closed(
    company_readers: tuple[Mock, Mock], mutation: str
) -> None:
    """A mismatched publication cannot be presented as another company's assessment."""
    _, models = company_readers
    original = models.assessments.return_value
    row = original[0]
    if mutation == "source_id":
        row = row.model_copy(update={"source_snapshot_id": "other"})
    elif mutation == "cutoff":
        row = row.model_copy(update={"as_of": row.as_of + timedelta(days=1)})
    elif mutation == "synthetic":
        row = row.model_copy(update={"synthetic": False})
    elif mutation == "family":
        row = row.model_copy(update={"family_id": "wrong-family"})
    elif mutation in {"evidence", "metric", "event", "gap"}:
        index = 1 if mutation == "gap" else 0
        field = {
            "evidence": "evidence_ids",
            "metric": "metric_observation_ids",
            "event": "event_ids",
            "gap": "missing_metric_ids",
        }[mutation]
        statement = row.statements[index].model_copy(update={field: ("unknown",)})
        statements = list(row.statements)
        statements[index] = statement
        row = row.model_copy(update={"statements": tuple(statements)})
    elif mutation == "future_label":
        outcome = row.outcomes[0].model_copy(update={"probability": 0.9})
        row = row.model_copy(update={"outcomes": (outcome, *row.outcomes[1:])})
    records: tuple[CompanyAssessment, ...] = (row, original[1])
    if mutation == "missing_company":
        records = (row,)
    elif mutation == "duplicate_company":
        records = (row, row)
    models.assessments.return_value = records

    with _client(company_readers) as client:
        assert client.get(PREFIX).status_code == 503
        assert client.get(f"{PREFIX}/alpha").status_code == 503


def test_exact_ids_and_unconfigured_routes_never_substitute_fixtures(
    company_readers: tuple[Mock, Mock],
) -> None:
    """Unknown company/snapshot is 404; absent production composition is 503."""
    with _client(company_readers) as client:
        assert client.get(f"{PREFIX}/unknown").status_code == 404
        assert client.get(PREFIX.replace(SNAPSHOT, "unknown")).status_code == 404
        assert client.get(f"{PREFIX}/bad%20id").status_code == 422
        assert client.get("/api/v1/cutoffs").status_code == 503
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/company-snapshots").status_code == 503
        assert client.get(PREFIX).status_code == 503


def test_storage_errors_are_redacted_and_empty_publications_are_not_ready(
    company_readers: tuple[Mock, Mock], caplog: pytest.LogCaptureFixture
) -> None:
    """Private exceptions do not enter public responses or logs."""
    sources, models = company_readers
    sources.snapshot.side_effect = OSError("private/key?token=secret")
    with _client(company_readers) as client:
        response = client.get(f"{PREFIX}/alpha")
    assert response.status_code == 503
    assert "secret" not in response.text + caplog.text
    models.snapshot_ids.return_value = ()
    with _client(company_readers) as client:
        assert client.get("/api/v1/company-snapshots").json() == {"items": []}
        assert client.get("/api/v1/health/ready").status_code == 503


def test_decimal_projection_retains_precision(
    company_readers: tuple[Mock, Mock],
) -> None:
    """Financial decimals remain strings rather than lossy JavaScript numbers."""
    sources, _ = company_readers
    source = sources.snapshot.return_value
    metric = source.metrics[0].model_copy(
        update={"value": DecimalValue(value=Decimal("12345678901234567890.123456"))}
    )
    definition = source.definitions[0].model_copy(update={"value_kind": "decimal"})
    # Both companies share this definition; keep the matrix type-consistent.
    rows = tuple(
        row.model_copy(
            update={"value": DecimalValue(value=Decimal(str(row.value.value)))}
        )
        if row.metric_id == definition.metric_id and row.value is not None
        else row
        for row in source.metrics
    )
    sources.snapshot.return_value = source.model_copy(
        update={
            "metrics": (metric, *rows[1:]),
            "definitions": (definition, *source.definitions[1:]),
        }
    )
    with _client(company_readers) as client:
        response = client.get(f"{PREFIX}/alpha")
    assert response.status_code == 200
    assert (
        response.json()["metrics"][0]["value"]["value"] == "12345678901234567890.123456"
    )


def test_duplicate_publication_ids_fail(company_readers: tuple[Mock, Mock]) -> None:
    """Enumeration cannot present conflicting duplicate publication choices."""
    company_readers[1].snapshot_ids.return_value = (SNAPSHOT, SNAPSHOT)
    with pytest.raises(RepositoryUnavailable):
        PublishedCompanyRepository(*company_readers).publications()
