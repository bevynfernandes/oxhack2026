"""Company source integrity, missingness, knowledge-time and exact-reader checks."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from oxhack2026.catalog.company import (
    BooleanValue,
    CompanySourceSnapshot,
    DecimalValue,
    IntegerValue,
)
from oxhack2026.catalog.schemas import Contract
from oxhack2026.storage.company import LocalCompanyStore, metadata, resolve_family
from oxhack2026.storage.contracts import ArtifactStore


def test_roundtrip_zero_missing_coverage(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """Zero remains observed and commercial missingness reduces applicable coverage."""
    snapshot, _ = company_source
    assert (
        CompanySourceSnapshot.model_validate_json(snapshot.model_dump_json())
        == snapshot
    )
    coverage = {row.family: row for row in snapshot.coverage("alpha")}
    assert coverage["traction"].observed_metric_ids == ("sdk_downloads_30d_v1",)
    assert coverage["commercial"].missing_metric_ids == (
        "operating_cashflow_12m_usd_v1",
    )
    assert snapshot.metrics[0].value == IntegerValue(value=0)
    assert "evidence" not in metadata(snapshot).model_dump()
    with pytest.raises(KeyError):
        snapshot.coverage("unknown")


@pytest.mark.parametrize(
    "kind,value",
    [
        ("integer", True),
        ("integer", "12"),
        ("integer", 1.5),
        ("decimal", 12.1),
        ("decimal", "NaN"),
        ("boolean", 1),
    ],
)
def test_strict_value_kinds(kind: str, value: object) -> None:
    """Counts, financial decimals and flags cannot silently coerce or be nonfinite."""
    models: dict[str, type[Contract]] = {
        "integer": IntegerValue,
        "decimal": DecimalValue,
        "boolean": BooleanValue,
    }
    model = models[kind]
    with pytest.raises(ValidationError):
        model.model_validate({"kind": kind, "value": value})
    assert (
        DecimalValue(value=Decimal("123.45")).model_dump(mode="json")["value"]
        == "123.45"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "cross_company",
        "future",
        "duplicate",
        "missing_row",
        "wrong_type",
        "unknown_definition",
        "missing_zero",
        "fact_before_source",
        "two_periods",
        "wrong_basis",
        "restricted_url",
    ],
)
def test_rejects_corrupt_tables(  # noqa: C901 - independent corruption cases
    company_source: tuple[CompanySourceSnapshot, ArtifactStore], mutation: str
) -> None:
    """Publication facts must agree with attribution, measurement and provenance."""
    snapshot, _ = company_source
    payload = snapshot.model_dump(mode="json")
    if mutation == "cross_company":
        payload["metrics"][0]["evidence_ids"] = ["beta-source"]
    elif mutation == "future":
        payload["evidence"][0]["collected_at"] = "2026-01-01T00:00:00Z"
    elif mutation == "duplicate":
        payload["metrics"].append(payload["metrics"][0] | {"observation_id": "another"})
    elif mutation == "missing_row":
        payload["metrics"].pop()
    elif mutation == "wrong_type":
        payload["metrics"][0]["value"] = {"kind": "decimal", "value": "1.1"}
    elif mutation == "unknown_definition":
        payload["metrics"][0]["metric_id"] = "unknown"
    elif mutation == "missing_zero":
        payload["metrics"][0]["state"] = "missing"
    elif mutation == "fact_before_source":
        payload["metrics"][0]["available_at"] = "2025-01-31T00:00:00Z"
    elif mutation == "two_periods":
        payload["metrics"][0]["measured_at"] = payload["as_of"]
    elif mutation == "wrong_basis":
        payload["evidence"][0]["availability_basis"] = "dated_publication"
    elif mutation == "restricted_url":
        payload["evidence"][0]["access"] = "restricted"
    with pytest.raises(ValidationError):
        CompanySourceSnapshot.model_validate(payload)


def test_family_cutoffs_and_conflict(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """Current family evidence cannot establish earlier ownership; conflicts survive."""
    snapshot, _ = company_source
    assert resolve_family(snapshot, "alpha", snapshot.as_of).family_id == "alpha"
    assert (
        resolve_family(snapshot, "alpha", snapshot.as_of - timedelta(days=1)).family_id
        is None
    )
    payload = snapshot.model_dump()
    payload["relationships"] = (
        *payload["relationships"],
        dict(
            payload["relationships"][0],
            relationship_id="conflict",
            subject_id="another-family",
        ),
    )
    conflict = CompanySourceSnapshot.model_validate(payload)
    assert resolve_family(conflict, "alpha", snapshot.as_of).reason_codes == (
        "conflicting_family_evidence",
    )
    with pytest.raises(ValueError, match="cutoff"):
        resolve_family(snapshot, "alpha", snapshot.as_of + timedelta(days=1))


def test_staleness_uses_frozen_measurement_cutoff(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """Re-reading old measurements does not refresh their measurement freshness."""
    snapshot, _ = company_source
    stale = CompanySourceSnapshot.model_validate(
        snapshot.model_dump()
        | {
            "as_of": snapshot.as_of + timedelta(days=40),
            "recorded_at": snapshot.recorded_at + timedelta(days=40),
        }
    )
    assert stale.coverage("alpha")[0].stale_metric_ids == ("sdk_downloads_30d_v1",)


def test_reader_methods_never_substitute_unknown_company(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """Readers expose exact tables and errors without touching a filesystem."""
    snapshot, _ = company_source
    store = LocalCompanyStore(Path("mock"))
    with patch.object(LocalCompanyStore, "snapshot", return_value=snapshot):
        assert len(store.companies("v1")) == 2
        assert store.company("v1", "alpha").display_name == "Synthetic alpha"
        assert len(store.definitions("v1")) == 3
        assert len(store.metrics("v1", "alpha")) == 3
        assert len(store.events("v1", "alpha")) == 1
        assert store.evidence("v1", "alpha-source").company_id == "alpha"
        assert len(store.relationships("v1", "alpha")) == 1
        assert len(store.coverage("v1", "alpha")) == 4
        assert store.family_at("v1", "alpha", snapshot.as_of).family_id == "alpha"
        for method in (
            store.company,
            store.metrics,
            store.events,
            store.relationships,
            store.coverage,
        ):
            with pytest.raises(KeyError):
                method("v1", "absent")
