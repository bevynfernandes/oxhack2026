"""Real filesystem C1/C2 publication, corruption, retry and rollback acceptance."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore
from oxhack2026.storage.contracts import ArtifactStore

pytestmark = pytest.mark.integration


def test_assessment_publication_and_rollback(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
) -> None:
    """Assessments stay source-bound across retry, failure and corruption."""
    source, artifacts = company_source
    root = Path("tests/outputs/assessment-publication") / uuid4().hex
    source_store = LocalCompanyStore(root)
    for evidence in source.evidence:
        ref = evidence.raw_artifact
        source_store.artifacts.write(artifacts.read(ref), ref.media_type)
    source_store.publish(source, None)
    store = LocalCompanyAssessmentStore(root)
    manifest = store.publish("first", company_assessments, None)
    assert (
        store.publish("first", tuple(reversed(company_assessments)), None) == manifest
    )
    assert store.assessments("first") == company_assessments
    assert store.company("first", "alpha") == company_assessments[0]
    assert store.publications()[0].company_ids == ("alpha", "beta")
    assert "source_manifest" not in store.publications()[0].model_dump()
    with pytest.raises(KeyError):
        store.company("first", "unknown")
    with pytest.raises(KeyError):
        store.assessments("unknown")
    with (
        patch(
            "oxhack2026.storage.company_assessments.atomic_write",
            side_effect=OSError("interruption"),
        ),
        pytest.raises(OSError),
    ):
        store.publish("second", company_assessments, "first")
    assert store.index().current == "first"
    assert store.assessments("first") == company_assessments
    with pytest.raises(ValueError, match="compare-and-swap"):
        store.publish("second", company_assessments, None)
    (root / source.evidence[0].raw_artifact.path).write_bytes(b"corruption")
    with pytest.raises(ValueError, match="SHA-256"):
        store.assessments("first")


def test_source_scoped_api_selection_is_explicit(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
) -> None:
    """A new policy publication cannot silently change an API's configured batch."""
    from oxhack2026.storage.company_assessments import SourceScopedAssessmentReader

    source, artifacts = company_source
    root = Path("tests/outputs/assessment-api-selection") / uuid4().hex
    source_store = LocalCompanyStore(root)
    for item in source.evidence:
        source_store.artifacts.write(
            artifacts.read(item.raw_artifact), item.raw_artifact.media_type
        )
    source_store.publish(source, None)
    store = LocalCompanyAssessmentStore(root)
    store.publish("first", company_assessments, None)
    newer = tuple(
        CompanyAssessment.model_validate(
            row.model_dump() | {"policy_version": "new-policy"}
        )
        for row in company_assessments
    )
    store.publish("second", newer, "first")
    selected = SourceScopedAssessmentReader(store, ("first",))
    assert selected.snapshot_ids() == (source.snapshot_id,)
    assert selected.assessments(source.snapshot_id) == company_assessments
    with pytest.raises(KeyError):
        selected.assessments("absent")
    with pytest.raises(ValueError, match="one assessment"):
        SourceScopedAssessmentReader(store, ("first", "second")).snapshot_ids()
