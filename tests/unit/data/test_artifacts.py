"""Mocked filesystem tests for bounded content-addressed artifact I/O."""

from hashlib import sha256
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference


def _reference(content: bytes = b"example") -> ArtifactReference:
    digest = sha256(content).hexdigest()
    return ArtifactReference(
        path=f"objects/{digest[:2]}/{digest}",
        sha256=digest,
        byte_size=len(content),
        media_type="application/octet-stream",
    )


@pytest.mark.parametrize("content", [b"example", b"corrupt", b"", b"example!"])
def test_read_verifies_hash_size_and_bounded_io(content: bytes) -> None:
    """Reading consumes at most the declared size plus one and rejects corruption."""
    store = FileArtifactStore(Path("bundle"))
    path = MagicMock(spec=Path)
    stream = path.open.return_value.__enter__.return_value
    stream.read.return_value = content
    with patch.object(FileArtifactStore, "_path", return_value=path):
        if content == b"example":
            assert store.read(_reference()) == content
        else:
            with pytest.raises(ValueError, match="SHA-256"):
                store.read(_reference())
    path.open.assert_called_once_with("rb")
    stream.read.assert_called_once_with(8)


def test_size_caps_fail_before_filesystem_access() -> None:
    """Configured limits apply to reads and writes before a path is resolved."""
    store = FileArtifactStore(Path("bundle"), maximum_bytes=1)
    with patch.object(FileArtifactStore, "_path") as path:
        with pytest.raises(ValueError, match="read limit"):
            store.read(_reference())
        with pytest.raises(ValueError, match="write limit"):
            store.write(b"example", "application/json")
    path.assert_not_called()


def test_resolved_path_cannot_escape_root() -> None:
    """A valid relative reference cannot follow a symlink outside the bundle."""
    with (
        patch.object(Path, "resolve", side_effect=[Path("/bundle"), Path("/other")]),
        pytest.raises(ValueError, match="outside"),
    ):
        FileArtifactStore(Path("bundle")).read(_reference())


def test_repeated_write_verifies_existing_bytes() -> None:
    """Existing content is verified rather than replaced or silently trusted."""
    path = MagicMock(spec=Path)
    path.exists.return_value = True
    with (
        patch.object(FileArtifactStore, "_path", return_value=path),
        patch.object(FileArtifactStore, "read", return_value=b"example") as read,
        patch("oxhack2026.storage.artifacts.NamedTemporaryFile") as temporary,
    ):
        result = FileArtifactStore(Path("bundle")).write(
            b"example", "application/octet-stream"
        )
    assert result == _reference()
    read.assert_called_once_with(result)
    temporary.assert_not_called()


def test_new_write_flushes_before_atomic_move_and_verifies() -> None:
    """Raw bytes become visible atomically and are read back after durability calls."""
    destination = MagicMock(spec=Path)
    destination.exists.return_value = False
    stream = MagicMock()
    stream.name = "pending-example"
    stream.fileno.return_value = 12
    with (
        patch.object(FileArtifactStore, "_path", return_value=destination),
        patch.object(FileArtifactStore, "read", return_value=b"example") as read,
        patch("oxhack2026.storage.artifacts.NamedTemporaryFile") as temporary,
        patch("oxhack2026.storage.artifacts.os.fsync") as fsync,
        patch("oxhack2026.storage.artifacts.os.replace") as replace,
        patch("oxhack2026.storage.artifacts.os.open", return_value=13),
        patch("oxhack2026.storage.artifacts.os.close") as close,
    ):
        temporary.return_value.__enter__.return_value = stream
        reference = FileArtifactStore(Path("bundle")).write(
            b"example", "application/octet-stream"
        )
    stream.write.assert_called_once_with(b"example")
    stream.flush.assert_called_once()
    assert [call.args[0] for call in fsync.call_args_list] == [12, 13]
    replace.assert_called_once_with(Path("pending-example"), destination)
    close.assert_called_once_with(13)
    read.assert_called_once_with(reference)
