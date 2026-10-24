"""Recovery archives reject unsafe paths and resource expansion before extraction."""

from io import BytesIO
from zipfile import ZipFile, ZipInfo

import pytest

from oxhack2026.storage.recovery import archive_members


@pytest.mark.parametrize("name", ["../outside", "/absolute", ".env", "objects/x/file"])
def test_forbidden_archive_paths(name: str) -> None:
    """Only fixed index names and content-addressed objects can be restored."""
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("company-snapshots.json", "{}")
        archive.writestr(name, "private")
        with pytest.raises(ValueError, match="forbidden"):
            archive_members(archive)


def test_link_and_oversized_archive_entries() -> None:
    """ZIP links and excessive expanded size fail without filesystem access."""
    with ZipFile(BytesIO(), "w") as archive:
        entry = ZipInfo("company-snapshots.json")
        entry.create_system = 3
        entry.external_attr = 0o120777 << 16
        archive.writestr(entry, "target")
        with pytest.raises(ValueError, match="non-regular"):
            archive_members(archive)
        entry.external_attr = 0o100600 << 16
        entry.file_size = 300 * 1024 * 1024
        with pytest.raises(ValueError, match="oversized"):
            archive_members(archive)


def test_duplicate_members_rejected() -> None:
    """Duplicate indexes cannot make ZIP readers disagree about publication bytes."""
    with ZipFile(BytesIO(), "w") as archive:
        archive.writestr("company-snapshots.json", "{}")
        with pytest.warns(UserWarning):
            archive.writestr("company-snapshots.json", "{}")
        with pytest.raises(ValueError, match="inventory"):
            archive_members(archive)
