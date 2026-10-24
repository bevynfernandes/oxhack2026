"""Real filesystem restore verifies all historical publications before activation."""

from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore
from oxhack2026.storage.contracts import ArtifactStore
from oxhack2026.storage.recovery import backup_company_store, restore_company_store

pytestmark = pytest.mark.integration


def test_restore_preserves_versions_and_refuses_corruption(
    company_source: tuple[CompanySourceSnapshot, ArtifactStore],
    company_assessments: tuple[CompanyAssessment, ...],
) -> None:
    """Restore off-line, excluding secrets and rejecting corrupt data."""
    root = Path("tests/outputs/company-recovery") / uuid4().hex
    live = root / "live"
    source, raw = company_source
    sources = LocalCompanyStore(live)
    for evidence in source.evidence:
        sources.artifacts.write(
            raw.read(evidence.raw_artifact), evidence.raw_artifact.media_type
        )
    sources.publish(source, None)
    store = LocalCompanyAssessmentStore(live)
    store.publish("first", company_assessments, None)
    store.publish("second", company_assessments, "first")
    (live / ".env").write_text("PRIVATE=excluded")
    archive = root / "backup.zip"
    digest = backup_company_store(live, archive)
    with ZipFile(archive) as bundle:
        assert ".env" not in bundle.namelist()
    restored = root / "restored"
    restore_company_store(archive, restored, digest)
    recovered = LocalCompanyAssessmentStore(restored)
    assert recovered.index() == store.index()
    assert recovered.assessments("first") == company_assessments
    assert recovered.assessments("second") == company_assessments
    with pytest.raises(ValueError, match="already exist"):
        restore_company_store(archive, restored, digest)
    with pytest.raises(ValueError, match="SHA-256"):
        restore_company_store(archive, root / "wrong-hash", "0" * 64)
    assert not (root / "wrong-hash").exists()
    with ZipFile(archive) as original, ZipFile(root / "corrupt.zip", "w") as corrupt:
        for name in original.namelist():
            data = original.read(name)
            if name == source.evidence[0].raw_artifact.path:
                data = b"corrupted"
            corrupt.writestr(name, data)
    bad = root / "corrupt.zip"
    with pytest.raises(ValueError, match="SHA-256"):
        restore_company_store(bad, root / "bad", sha256(bad.read_bytes()).hexdigest())
    assert not (root / "bad").exists()
    assert sources.snapshot(source.snapshot_id) == source
    with pytest.raises(FileExistsError):
        backup_company_store(live, archive)
