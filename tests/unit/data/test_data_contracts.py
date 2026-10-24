"""C1 data identity, availability, revision, artifact and schema contract tests."""

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import orjson
import pytest
from pydantic import ValidationError

from oxhack2026.catalog.schemas import CatalogSnapshot, Package, TimeWindow
from oxhack2026.storage.contracts import (
    ArtifactReference,
    AvailabilityPolicy,
    DatasetManifest,
    ObservationQuery,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
    validate_observation_policy,
)
from oxhack2026.storage.export_contracts import CONTRACTS, export_schemas

ROOT = Path(__file__).parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "data"


def _catalog(name: str = "catalog.json") -> CatalogSnapshot:
    return CatalogSnapshot.model_validate(orjson.loads((FIXTURES / name).read_bytes()))


def _observation(state: str = "complete") -> ObservationRevision:
    return ObservationRevision.model_validate(
        orjson.loads((FIXTURES / "observation-states.json").read_bytes())["states"][
            state
        ]
    )


def _manifest() -> DatasetManifest:
    return DatasetManifest.model_validate_json(
        (FIXTURES / "dataset-manifest.json").read_bytes()
    )


def test_catalogue_and_mapping_change_fixtures() -> None:
    """Package changes create new identities; repository renames keep numeric IDs."""
    original, changed = _catalog(), _catalog("catalog-changed.json")
    assert original.synthetic and changed.synthetic
    assert (
        original.repositories[0].repository_id == changed.repositories[0].repository_id
    )
    assert original.repositories[0].full_name != changed.repositories[0].full_name
    assert len(changed.packages) == 2
    assert changed.mappings[0].valid_to == changed.mappings[1].valid_from
    assert changed.mappings[0].package_id != changed.mappings[1].package_id
    assert CatalogSnapshot.model_validate_json(original.model_dump_json()) == original


@pytest.mark.parametrize(
    "field",
    ["organizations", "tools", "packages", "repositories", "evidence", "mappings"],
)
def test_duplicate_identities_rejected(field: str) -> None:
    """Every normalized entity has a unique primary identity in a snapshot."""
    payload = _catalog().model_dump()
    payload[field] += payload[field]
    with pytest.raises(ValidationError, match="Duplicate"):
        CatalogSnapshot.model_validate(payload)


def test_duplicate_canonical_package_rejected() -> None:
    """A second internal ID cannot duplicate a registry's canonical package."""
    payload = _catalog().model_dump()
    payload["packages"] += (payload["packages"][0] | {"package_id": "duplicate"},)
    with pytest.raises(ValidationError, match="Duplicate package"):
        CatalogSnapshot.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tool_id", "unknown"),
        ("package_id", "unknown"),
        ("repository_id", 98765),
        ("evidence_ids", ["unknown"]),
    ],
)
def test_unknown_mapping_references(field: str, value: object) -> None:
    """Foreign keys and evidence IDs must resolve in the frozen snapshot."""
    payload = _catalog().model_dump()
    payload["mappings"][0][field] = value
    with pytest.raises(ValidationError, match="foreign key"):
        CatalogSnapshot.model_validate(payload)


def test_overlapping_mappings_and_verification() -> None:
    """Boundary-adjacent mappings pass; overlapping or unverified primaries fail."""
    payload = _catalog("catalog-changed.json").model_dump()
    payload["mappings"][1]["valid_from"] -= timedelta(seconds=1)
    with pytest.raises(ValidationError, match="Overlapping"):
        CatalogSnapshot.model_validate(payload)
    payload = _catalog().model_dump()
    payload["mappings"][0]["verified"] = False
    with pytest.raises(ValidationError, match="Unverified"):
        CatalogSnapshot.model_validate(payload)


def test_historical_membership_requires_dated_evidence() -> None:
    """Current official docs do not silently prove eligibility in an earlier year."""
    payload = _catalog().model_dump()
    payload["cohort_kind"] = "historical_eligibility"
    with pytest.raises(ValidationError, match="Historical membership"):
        CatalogSnapshot.model_validate(payload)
    earlier = datetime(2023, 12, 1, tzinfo=UTC)
    payload["tools"][0]["earliest_eligibility_at"] = earlier
    payload["evidence"][0]["available_at"] = earlier
    assert (
        CatalogSnapshot.model_validate(payload).cohort_kind == "historical_eligibility"
    )


@pytest.mark.parametrize(
    ("ecosystem", "name"),
    [
        ("npm", "@bad"),
        ("npm", "UpperCase"),
        ("npm", "../bad"),
        ("pypi", "Foo_Bar"),
        ("pypi", "foo.bar"),
        ("pypi", "foo--bar"),
    ],
)
def test_noncanonical_package_names(ecosystem: str, name: str) -> None:
    """Reject package identities that have not undergone registry normalization."""
    with pytest.raises(ValidationError):
        Package.model_validate(
            {"package_id": "id", "ecosystem": ecosystem, "canonical_name": name}
        )


@pytest.mark.parametrize(
    "state", ["complete", "zero", "missing", "partial", "late", "revised", "vendor"]
)
def test_observation_states(state: str) -> None:
    """All saved states retain value and provenance through JSON round trips."""
    revision = _observation(state)
    assert (
        ObservationRevision.model_validate_json(revision.model_dump_json()) == revision
    )
    assert revision.revision_id.startswith("synthetic-")


def test_zero_missing_late_and_revised_are_distinct() -> None:
    """Missing is null; late and revised facts retain their actual collection times."""
    original, zero, missing = (
        _observation(),
        _observation("zero"),
        _observation("missing"),
    )
    late, revised = _observation("late"), _observation("revised")
    assert zero.value == 0 and missing.value is None
    assert original.published_at is None
    assert original.available_at == original.assumed_available_at
    assert late.available_at == late.first_collected_at > late.window.end
    assert revised.supersedes_revision_id == original.revision_id
    assert revised.first_collected_at > original.first_collected_at
    assert original.value == 100 and revised.value == 120


@pytest.mark.parametrize(
    "changes",
    [
        {"value": True},
        {"value": -1},
        {"value": None},
        {"completeness": "missing", "value": 0},
        {"available_at": "2025-01-01T00:00:00Z"},
        {"assumed_available_at": None},
        {"first_collected_at": "2026-10-25T00:00:00Z"},
        {"first_collected_at": "2025-01-01T00:00:00Z"},
        {"supersedes_revision_id": "synthetic-original"},
    ],
)
def test_invalid_observation_states(changes: dict[str, object]) -> None:
    """Reject invented zeros, unavailable truth and contradictory time provenance."""
    with pytest.raises(ValidationError):
        ObservationRevision.model_validate(_observation().model_dump() | changes)


def test_availability_policy_must_match_assumed_bound() -> None:
    """A 48-hour policy cannot be applied to a revision carrying another lag."""
    policy = AvailabilityPolicy.model_validate_json(
        (FIXTURES / "availability-policy.json").read_bytes()
    )
    validate_observation_policy(_observation(), policy)
    different = AvailabilityPolicy.model_validate(
        policy.model_dump() | {"assumed_lag_hours": 24}
    )
    with pytest.raises(ValueError, match="pinned lag"):
        validate_observation_policy(_observation(), different)
    with pytest.raises(ValueError, match="different availability"):
        validate_observation_policy(_observation("late"), policy)
    with pytest.raises(ValidationError, match="Only assumed"):
        AvailabilityPolicy.model_validate(policy.model_dump() | {"basis": "collected"})


def test_daily_interval_and_utc() -> None:
    """Partial days, multi-day aggregates, naive times and empty windows fail."""
    payload = _observation().model_dump()
    payload["window"]["start"] += timedelta(hours=1)
    with pytest.raises(ValidationError, match="Daily observations"):
        ObservationRevision.model_validate(payload)
    instant = datetime(2025, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="start < end"):
        TimeWindow(start=instant, end=instant)
    with pytest.raises(ValidationError, match="UTC"):
        TimeWindow(start=instant.replace(tzinfo=None), end=instant + timedelta(days=1))


def test_series_and_coverage_fixtures() -> None:
    """Source scope and coverage counts remain explicit for downstream health views."""
    series = ObservationSeries.model_validate(
        orjson.loads((FIXTURES / "series.json").read_bytes())["series"][0]
    )
    coverage = SourceCoverage.model_validate(
        orjson.loads((FIXTURES / "coverage.json").read_bytes())["coverage"][0]
    )
    assert series.ecosystem == "npm" and coverage.missing_days == 2
    with pytest.raises(ValidationError, match="source"):
        ObservationSeries.model_validate(series.model_dump() | {"ecosystem": "pypi"})
    with pytest.raises(ValidationError, match="status"):
        SourceCoverage.model_validate(coverage.model_dump() | {"status": "complete"})
    with pytest.raises(ValidationError, match="add up"):
        SourceCoverage.model_validate(coverage.model_dump() | {"missing_days": 0})


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/absolute",
        "a/../../b",
        r"a\b",
        "https://example.com/data",
        "a//b",
        "./a",
        ".",
    ],
)
def test_artifact_paths_reject_escapes(path: str) -> None:
    """Artifact references cannot name URLs, absolute paths or parent traversal."""
    with pytest.raises(ValidationError, match="relative path"):
        ArtifactReference(
            path=path, sha256="a" * 64, byte_size=1, media_type="application/json"
        )


def test_manifest_provenance() -> None:
    """Complete publication requires complete, dated, matching source extractions."""
    manifest = _manifest()
    assert manifest.synthetic
    payload = manifest.model_dump()
    payload["completeness"] = "complete"
    assert DatasetManifest.model_validate(payload).completeness == "complete"
    payload["extraction_manifests"][0]["status"] = "partial"
    with pytest.raises(ValidationError, match="Incomplete extractions"):
        DatasetManifest.model_validate(payload)
    payload = manifest.model_dump()
    payload["extraction_manifests"][0]["retrieved_at"] = (
        manifest.created_at + timedelta(days=1)
    )
    with pytest.raises(ValidationError, match="after creation"):
        DatasetManifest.model_validate(payload)


def test_query_preserves_both_knowledge_filters() -> None:
    """Prospective reads can demand both available-by and actual collection cutoffs."""
    query = ObservationQuery(
        dataset_version="synthetic-v1",
        series_ids=("synthetic-npm-series",),
        window=_observation().window,
        available_by=datetime(2025, 1, 6, tzinfo=UTC),
        collected_by=datetime(2025, 1, 6, tzinfo=UTC),
    )
    assert query.available_by == query.collected_by
    assert query.collected_by is not None
    assert query.collected_by < _observation().first_collected_at


@pytest.mark.parametrize(
    ("source", "kind", "ecosystem", "unit"),
    [
        ("npm", "package", "npm", "downloads"),
        ("pypi", "package", "pypi", "downloads"),
        ("github", "repository", None, "events"),
        ("hackernews", "domain", None, "mentions"),
    ],
)
def test_series_units_match_source(
    source: str, kind: str, ecosystem: str | None, unit: str
) -> None:
    """Counts from a source cannot silently change their measurement unit."""
    payload = {
        "series_id": "synthetic-series",
        "source": source,
        "entity_kind": kind,
        "entity_id": "synthetic-entity",
        "ecosystem": ecosystem,
        "metric": "daily-count",
        "unit": unit,
    }
    assert ObservationSeries.model_validate(payload).unit == unit
    for wrong_unit in {"downloads", "events", "mentions"} - {unit}:
        with pytest.raises(ValidationError, match="unit must match"):
            ObservationSeries.model_validate(payload | {"unit": wrong_unit})


def test_schema_drift_and_export() -> None:
    """Schemas match authoritative models and export uses deterministic bytes."""
    for contract in CONTRACTS:
        path = (
            ROOT
            / "contracts"
            / "datasets"
            / "data"
            / f"{contract.__name__}.schema.json"
        )
        assert orjson.loads(path.read_bytes()) == contract.model_json_schema()
    with (
        patch.object(Path, "mkdir") as mkdir,
        patch.object(Path, "write_bytes") as write,
    ):
        export_schemas(Path("schemas"))
    mkdir.assert_called_once_with(parents=True, exist_ok=True)
    assert write.call_count == len(CONTRACTS)


def test_lightweight_imports() -> None:
    """A fresh interpreter can load C1 without database, network or model imports."""
    code = (
        "import sys; import oxhack2026.catalog.schemas; "
        "import oxhack2026.storage.contracts; "
        "assert not {'catboost','sklearn','polars','psycopg','sqlalchemy','httpx'} "
        "& sys.modules.keys()"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603
