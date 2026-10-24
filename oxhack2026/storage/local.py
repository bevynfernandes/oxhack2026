"""POSIX local metadata locks and durable atomic writes; no import-time I/O."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Hold a process-safe exclusive lock; release it even when work fails.

    Args:
        path: Dedicated local lock file, outside artifact objects.
    Yields:
        None while the lock is held. File descriptors close on process exit.
    Raises:
        OSError: If the directory, lock file, or OS lock cannot be accessed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_write(path: Path, content: bytes) -> None:
    """Flush new metadata before atomic replacement, preserving old bytes on failure.

    Args:
        path: Destination controlled by the application.
        content: Complete serialized metadata.
    Returns:
        None after rename and directory fsync.
    Raises:
        OSError: For write/fsync/rename failure; abandoned temporary files remain.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent, prefix=".pending-", delete=False
    ) as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
