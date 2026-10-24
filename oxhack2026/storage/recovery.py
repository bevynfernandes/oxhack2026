"""Bounded, verified backups of published company sources and assessments only."""

import os
import re
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import LocalCompanyAssessmentStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock

MAX_BACKUP_BYTES = 256 * 1024 * 1024
MAX_BACKUP_FILES = 100_000
_INDEX_NAMES = {"company-snapshots.json", "company-assessments.json"}
_OBJECT_NAME = re.compile(r"objects/[0-9a-f]{2}/[0-9a-f]{64}")


def published_files(root: Path) -> dict[str, bytes]:
    """Verify and collect the complete reachable company publication graph.

    Args:
        root: Local company store; callers hold publication locks during writes.
    Returns:
        Exact index and referenced artifact bytes, excluding unrelated files.
    Raises:
        ValueError, KeyError, OSError: For empty, corrupt or oversized stores.
    """
    sources = LocalCompanyStore(root)
    assessments = LocalCompanyAssessmentStore(root)
    source_index = sources.index()
    assessment_index = assessments.index()
    if not source_index.versions:
        message = "Cannot back up an empty company source store"
        raise ValueError(message)
    files = {"company-snapshots.json": source_index.model_dump_json().encode()}
    total = len(files["company-snapshots.json"])

    def include(reference: ArtifactReference) -> None:
        nonlocal total
        if reference.path in files:
            return
        total += reference.byte_size
        if total > MAX_BACKUP_BYTES or len(files) >= MAX_BACKUP_FILES:
            message = "Company backup exceeds its bounded size or file count"
            raise ValueError(message)
        files[reference.path] = sources.artifacts.read(reference)

    for key, reference in source_index.versions.items():
        snapshot = sources.snapshot(key)
        include(reference)
        include(sources.manifest(key).content)
        for evidence in snapshot.evidence:
            include(evidence.raw_artifact)
    if assessment_index.versions:
        content = assessment_index.model_dump_json().encode()
        total += len(content)
        files["company-assessments.json"] = content
        for key, reference in assessment_index.versions.items():
            assessments.assessments(key)
            include(reference)
            manifest = assessments.manifest(key)
            include(manifest.source_manifest)
            include(manifest.assessments)
    if total > MAX_BACKUP_BYTES:
        message = "Company backup exceeds its bounded size"
        raise ValueError(message)
    return files


def backup_company_store(root: Path, archive: Path) -> str:
    """Create a new recovery archive; return its externally recorded SHA-256.

    Args:
        root: Local published source/assessment store, on a POSIX filesystem.
        archive: New ZIP path; an existing backup is never overwritten.
    Returns:
        SHA-256 of the exact ZIP bytes, required by restore_company_store.
    Raises:
        OSError, ValueError, KeyError: For existing output or failed validation.
    """
    with (
        file_lock(root / ".company-publication.lock"),
        file_lock(root / ".company-assessments.lock"),
    ):
        files = published_files(root)
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as bundle:
        for name, content in sorted(files.items()):
            bundle.writestr(name, content)
        archive_members(bundle)
    content = buffer.getvalue()
    if len(content) > MAX_BACKUP_BYTES:
        message = "Compressed backup exceeds its bounded size"
        raise ValueError(message)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(content).hexdigest()


def archive_members(bundle: ZipFile) -> tuple[str, ...]:
    """Validate a recovery archive's bounded, unique, regular-file allowlist.

    Args:
        bundle: Open ZIP; no extraction has occurred.
    Returns:
        Validated member names.
    Raises:
        ValueError: For traversal, links, duplicates, extra files or size limits.
    """
    entries = bundle.infolist()
    names = tuple(entry.filename for entry in entries)
    if (
        len(names) != len(set(names))
        or not names
        or len(names) > MAX_BACKUP_FILES
        or sum(entry.file_size for entry in entries) > MAX_BACKUP_BYTES
        or "company-snapshots.json" not in names
    ):
        message = "Invalid or oversized recovery archive inventory"
        raise ValueError(message)
    for entry in entries:
        kind = (entry.external_attr >> 16) & 0o170000
        if (
            entry.filename not in _INDEX_NAMES
            and not _OBJECT_NAME.fullmatch(entry.filename)
        ) or kind not in {0, 0o100000}:
            message = "Recovery archive contains a forbidden path or non-regular file"
            raise ValueError(message)
    return names


def restore_company_store(
    archive: Path, destination: Path, expected_sha256: str
) -> None:
    """Restore into a new root only after checksum and full lineage verification.

    Args:
        archive: Company recovery ZIP, bounded to 256 MiB.
        destination: New local store path; existing destinations are refused.
        expected_sha256: Independently recorded archive checksum.
    Returns:
        None after successful validation and atomic directory rename.
    Raises:
        ValueError, OSError, KeyError: For checksum, structure or lineage failures.
        BadZipFile: For an invalid ZIP. Failed staging files remain for diagnosis.
    """
    with archive.open("rb") as stream:
        content = stream.read(MAX_BACKUP_BYTES + 1)
    if (
        len(content) > MAX_BACKUP_BYTES
        or sha256(content).hexdigest() != expected_sha256
    ):
        message = "Recovery archive size or SHA-256 does not match"
        raise ValueError(message)
    with file_lock(destination.parent / f".{destination.name}.restore.lock"):
        if destination.exists() or destination.is_symlink():
            message = "Restore destination must not already exist"
            raise ValueError(message)
        staging = destination.parent / f".{destination.name}.restore-{uuid4().hex}"
        with ZipFile(BytesIO(content)) as bundle:
            names = archive_members(bundle)
            staging.mkdir()
            for name in names:
                atomic_write(staging / name, bundle.read(name))
        expected = published_files(staging)
        if set(expected) != set(names):
            message = "Recovery archive contains unreferenced files"
            raise ValueError(message)
        staging.rename(destination)
