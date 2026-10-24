"""Local content-addressed artifacts with bounded, verified reads."""

import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from oxhack2026.storage.contracts import ArtifactReference


@dataclass(frozen=True)
class FileArtifactStore:
    """Local implementation of ArtifactStore; constructing it performs no I/O."""

    root: Path
    maximum_bytes: int = 128 * 1024 * 1024

    def _path(self, relative: str) -> Path:
        root = self.root.resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            message = "Artifact path resolves outside the configured bundle root"
            raise ValueError(message)
        return path

    def read(self, reference: ArtifactReference) -> bytes:
        """Read an artifact only if its bounded size and SHA-256 match.

        Args:
            reference: Expected location, size, checksum and media type.
        Returns:
            Verified artifact bytes.
        Raises:
            OSError: If the artifact cannot be opened.
            ValueError: For path escapes, excessive size, truncation or corruption.
        """
        if reference.byte_size > self.maximum_bytes:
            message = "Artifact exceeds the configured read limit"
            raise ValueError(message)
        with self._path(reference.path).open("rb") as stream:
            content = stream.read(reference.byte_size + 1)
        if (
            len(content) != reference.byte_size
            or sha256(content).hexdigest() != reference.sha256
        ):
            message = "Artifact size or SHA-256 does not match its immutable reference"
            raise ValueError(message)
        return content

    def write(self, content: bytes, media_type: str) -> ArtifactReference:
        """Atomically store content and verify it without replacing different content.

        Args:
            content: Serialized artifact bytes.
            media_type: Supported type from the C1 artifact contract.
        Returns:
            A content-addressed immutable reference, identical for repeated bytes.
        Raises:
            OSError: If writing, flushing, moving or read-back fails.
            ValueError: For oversized content, invalid type or corrupt existing data.
        """
        if len(content) > self.maximum_bytes:
            message = "Artifact exceeds the configured write limit"
            raise ValueError(message)
        digest = sha256(content).hexdigest()
        reference = ArtifactReference.model_validate(
            {
                "path": f"objects/{digest[:2]}/{digest}",
                "sha256": digest,
                "byte_size": len(content),
                "media_type": media_type,
            }
        )
        destination = self._path(reference.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            self.read(reference)
            return reference
        with NamedTemporaryFile(
            dir=destination.parent, prefix=".pending-", delete=False
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        self.read(reference)
        return reference
