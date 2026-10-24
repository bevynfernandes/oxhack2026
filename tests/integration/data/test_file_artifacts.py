"""Opt-in local filesystem verification; outputs are retained for inspection."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from oxhack2026.storage.artifacts import FileArtifactStore

pytestmark = pytest.mark.integration
OUTPUTS = Path(__file__).resolve().parents[2] / "outputs" / "file-artifacts"


def test_concurrent_roundtrip_and_corruption_detection() -> None:
    """Concurrent identical writes share one verified object; tampering fails closed."""
    store = FileArtifactStore(OUTPUTS / uuid4().hex)
    content = b'{"synthetic":true,"value":0}'
    with ThreadPoolExecutor(max_workers=4) as pool:
        references = list(
            pool.map(lambda _: store.write(content, "application/json"), range(8))
        )
    assert all(reference == references[0] for reference in references)
    assert store.read(references[0]) == content
    (store.root / references[0].path).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        store.read(references[0])
    with pytest.raises(ValueError, match="SHA-256"):
        store.write(content, "application/json")


def test_symlink_cannot_redirect_read_outside_bundle() -> None:
    """Local path resolution enforces the configured root for artifact references."""
    run = OUTPUTS / uuid4().hex
    external = FileArtifactStore(run / "external")
    reference = external.write(b"synthetic", "application/octet-stream")
    root = run / "bundle"
    root.mkdir()
    (root / "objects").symlink_to((external.root / "objects").resolve())
    with pytest.raises(ValueError, match="outside"):
        FileArtifactStore(root).read(reference)
