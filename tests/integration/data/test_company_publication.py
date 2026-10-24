"""Opt-in real filesystem company publication, corruption and concurrency tests."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.contracts import ArtifactStore

pytestmark = pytest.mark.integration


def _store(snapshot: CompanySourceSnapshot, source: ArtifactStore) -> LocalCompanyStore:
    store = LocalCompanyStore(Path("tests/outputs/company-publication") / uuid4().hex)
    for evidence in snapshot.evidence:
        ref = evidence.raw_artifact
        assert store.artifacts.write(source.read(ref), ref.media_type) == ref
    return store


def test_company_publication_roundtrip_and_integrity(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """Exact reads, idempotence, version conflicts and raw corruption are enforced."""
    snapshot, source = company_source
    store = _store(snapshot, source)
    manifest = store.publish(snapshot, None)
    assert store.publish(snapshot, None) == manifest
    assert store.snapshot(snapshot.snapshot_id) == snapshot
    assert store.snapshots()[0].snapshot_id == snapshot.snapshot_id
    with pytest.raises(KeyError):
        store.snapshot("absent")
    changed = CompanySourceSnapshot.model_validate(
        snapshot.model_dump() | {"limitations": ("different",)}
    )
    with pytest.raises(ValueError, match="immutable"):
        store.publish(changed, snapshot.snapshot_id)
    (store.root / snapshot.evidence[0].raw_artifact.path).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        store.snapshot(snapshot.snapshot_id)


def test_failed_and_concurrent_publications(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
) -> None:
    """Failed pointer writes retain the old snapshot; competing CAS has one winner."""
    snapshot, source = company_source
    store = _store(snapshot, source)
    store.publish(snapshot, None)
    variants = [
        CompanySourceSnapshot.model_validate(
            snapshot.model_dump() | {"snapshot_id": f"variant-{index}"}
        )
        for index in range(2)
    ]
    with (
        patch(
            "oxhack2026.storage.company.atomic_write",
            side_effect=OSError("interrupted"),
        ),
        pytest.raises(OSError),
    ):
        store.publish(variants[0], snapshot.snapshot_id)
    assert store.snapshot(snapshot.snapshot_id) == snapshot
    assert store.index().current == snapshot.snapshot_id

    def publish(candidate: CompanySourceSnapshot) -> bool:
        try:
            store.publish(candidate, snapshot.snapshot_id)
        except ValueError as exc:
            assert "compare-and-swap" in str(exc)
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(publish, variants)) == [False, True]
    assert store.snapshot(snapshot.snapshot_id) == snapshot
