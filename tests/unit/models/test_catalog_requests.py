"""Frozen catalogue request resolution is independent of future download outcomes."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import orjson
import pytest

from oxhack2026.catalog.schemas import CatalogSnapshot
from oxhack2026.features.catalog import RequestScope, catalog_requests
from oxhack2026.storage.contracts import ObservationSeries

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/data"
SCOPE = RequestScope(
    "synthetic-dataset",
    "npm",
    "downloads_next_30d_v1",
    datetime(2025, 1, 6, tzinfo=UTC),
    "reconstructed",
)


def _catalog() -> CatalogSnapshot:
    return CatalogSnapshot.model_validate_json((FIXTURES / "catalog.json").read_bytes())


def _series() -> ObservationSeries:
    return ObservationSeries.model_validate(
        orjson.loads((FIXTURES / "series.json").read_bytes())["series"][0]
    )


def test_reconstructed_cohort_preserves_frozen_representation_and_caveats() -> None:
    """Later verification is explicit, with deterministic mode/schema-bound IDs."""
    catalog, series = _catalog(), _series()

    batch = catalog_requests(catalog, [series], SCOPE)
    repeated = catalog_requests(catalog, [series], SCOPE)

    assert batch == repeated
    assert len(batch.requests) == 1
    assert batch.requests[0].identity.package_id == series.entity_id
    assert batch.representatives == (("synthetic-org", "synthetic-tool"),)
    assert any("survivorship" in reason for reason in batch.limitations)
    assert any("verification occurred after" in reason for reason in batch.limitations)


def test_prospective_requires_actual_catalogue_and_mapping_inspection() -> None:
    """A current catalogue cannot be backdated to produce a prospective replay."""
    catalog, series = _catalog(), _series()
    scope = replace(SCOPE, mode="prospective")

    with pytest.raises(ValueError, match="catalogue must be recorded"):
        catalog_requests(catalog, [series], scope)
    with pytest.raises(ValueError, match="after its recording"):
        CatalogSnapshot.model_validate(
            catalog.model_dump() | {"recorded_at": SCOPE.decision_at}
        )


def test_effective_end_is_exclusive_and_future_tool_is_excluded() -> None:
    """Mapping and tool eligibility gates use the decision, never target outcomes."""
    catalog = _catalog()
    mapping = catalog.mappings[0].model_dump() | {"valid_to": SCOPE.decision_at}
    ended = CatalogSnapshot.model_validate(
        catalog.model_dump() | {"mappings": [mapping]}
    )
    tool = catalog.tools[0].model_dump() | {
        "earliest_eligibility_at": SCOPE.decision_at + timedelta(days=1)
    }
    future_tool = CatalogSnapshot.model_validate(
        catalog.model_dump() | {"tools": [tool]}
    )

    assert catalog_requests(ended, [_series()], SCOPE).requests == ()
    assert catalog_requests(future_tool, [_series()], SCOPE).requests == ()


def test_missing_or_ambiguous_series_fail_without_silently_removing_company() -> None:
    """A catalogue/data wiring error remains visible instead of improving a cohort."""
    with pytest.raises(ValueError, match="absent"):
        catalog_requests(_catalog(), [], SCOPE)
    with pytest.raises(ValueError, match="ambiguous"):
        catalog_requests(_catalog(), [_series(), _series()], SCOPE)


def test_community_references_do_not_enter_company_selection() -> None:
    """Community comparison tools never become startup headline candidates."""
    catalog = _catalog()
    organization = catalog.organizations[0].model_dump() | {"kind": "community"}
    community = CatalogSnapshot.model_validate(
        catalog.model_dump() | {"organizations": [organization]}
    )

    result = catalog_requests(community, [_series()], SCOPE)

    assert result.requests == result.representatives == ()


def test_prospective_snapshot_after_verification_has_distinct_row_identity() -> None:
    """Mode forms part of the immutable row ID even for identical observed values."""
    scope = replace(SCOPE, decision_at=datetime(2026, 10, 26, tzinfo=UTC))
    reconstructed = catalog_requests(_catalog(), [_series()], scope)
    prospective = catalog_requests(
        _catalog(), [_series()], replace(scope, mode="prospective")
    )

    assert (
        reconstructed.requests[0].feature_row_id
        != prospective.requests[0].feature_row_id
    )
    assert not any(
        "verification occurred after" in reason for reason in prospective.limitations
    )


def test_contemporary_mapping_policy_requires_explicit_reconstructed_opt_in() -> None:
    """Today's mappings stay dated today even when studying old download histories."""
    catalog = _catalog()
    mapping = catalog.mappings[0].model_dump() | {"valid_from": catalog.recorded_at}
    current = CatalogSnapshot.model_validate(
        catalog.model_dump() | {"mappings": [mapping]}
    )

    strict = catalog_requests(current, [_series()], SCOPE)
    contemporary = catalog_requests(current, [_series()], SCOPE, contemporary=True)

    assert strict.requests == ()
    assert len(contemporary.requests) == 1
    assert any(
        "not historically known" in reason for reason in contemporary.limitations
    )
    assert current.mappings[0].valid_from == catalog.recorded_at
    with pytest.raises(ValueError, match="requires reconstructed"):
        catalog_requests(
            current,
            [_series()],
            replace(
                SCOPE,
                mode="prospective",
                decision_at=datetime(2026, 10, 26, tzinfo=UTC),
            ),
            contemporary=True,
        )
