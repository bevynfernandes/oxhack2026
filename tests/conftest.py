"""Shared synthetic data fixtures; creation performs no network or filesystem I/O."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import orjson
import pytest

from oxhack2026.catalog.schemas import CatalogSnapshot, TimeWindow
from oxhack2026.ingest.npm import NpmCheckpoint, NpmRequest, normalize_range
from oxhack2026.storage.build import CandidateConfig, write_candidate
from oxhack2026.storage.contracts import ArtifactReference, ArtifactStore
from oxhack2026.storage.datasets import DatasetBundle


class MemoryArtifacts:
    """Mock artifact store with the same content addressing as filesystem storage."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def write(self, content: bytes, media_type: str) -> ArtifactReference:
        """Store bytes in memory, returning their exact size/type/hash reference."""
        digest = sha256(content).hexdigest()
        self.objects[digest] = content
        return ArtifactReference.model_validate(
            {
                "path": f"objects/{digest[:2]}/{digest}",
                "sha256": digest,
                "byte_size": len(content),
                "media_type": media_type,
            }
        )

    def read(self, reference: ArtifactReference) -> bytes:
        """Return a mock artifact; raise KeyError for unknown objects."""
        return self.objects[reference.sha256]


@pytest.fixture
def synthetic_bundle() -> tuple[DatasetBundle, ArtifactStore]:
    """Build labelled three-day data with a zero, missing day and positive count."""
    catalog = CatalogSnapshot.model_validate_json(
        (Path(__file__).parent / "fixtures/data/catalog.json").read_bytes()
    )
    artifacts = MemoryArtifacts()
    request = NpmRequest(
        package=catalog.packages[0],
        catalog_version=catalog.catalog_version,
        window=TimeWindow(
            start=datetime(2025, 1, 1, tzinfo=UTC), end=datetime(2025, 1, 4, tzinfo=UTC)
        ),
    )
    content = orjson.dumps(
        {
            "package": request.package.canonical_name,
            "start": "2025-01-01",
            "end": "2025-01-03",
            "downloads": [
                {"day": "2025-01-01", "downloads": 0},
                {"day": "2025-01-03", "downloads": 120},
            ],
        }
    )
    retrieved = datetime(2026, 10, 24, 15, tzinfo=UTC)
    extraction = normalize_range(
        NpmCheckpoint(
            request=request,
            retrieved_at=retrieved,
            raw_artifact=artifacts.write(content, "application/json"),
        ),
        content,
    )
    with (
        patch("oxhack2026.storage.build.FileArtifactStore", return_value=artifacts),
        patch("oxhack2026.storage.build.atomic_write"),
    ):
        bundle = write_candidate(
            catalog,
            (extraction,),
            Path("mock"),
            CandidateConfig(
                dataset_version="synthetic-dataset-v1",
                created_at=retrieved,
                code_revision="synthetic-code",
                configuration_sha256="a" * 64,
            ),
        )
    return bundle, artifacts
