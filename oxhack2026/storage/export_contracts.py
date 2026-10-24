"""Generate C1 JSON Schema snapshots without storage or service initialization."""

from pathlib import Path

import orjson

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.catalog.schemas import CatalogSnapshot, Contract
from oxhack2026.storage.company import CompanySourceManifest
from oxhack2026.storage.contracts import (
    ArtifactReference,
    AvailabilityPolicy,
    DatasetManifest,
    ExtractionManifest,
    ObservationQuery,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)

CONTRACTS: tuple[type[Contract], ...] = (
    CatalogSnapshot,
    CompanySourceSnapshot,
    CompanySourceManifest,
    ArtifactReference,
    AvailabilityPolicy,
    DatasetManifest,
    ExtractionManifest,
    ObservationQuery,
    ObservationRevision,
    ObservationSeries,
    SourceCoverage,
)


def export_schemas(directory: Path) -> None:
    """Write deterministic schemas for C1 consumer review and drift tests.

    Args:
        directory: Destination for checked-in schema files.
    Returns:
        None.
    Raises:
        OSError: If creating the directory or writing a schema fails.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for contract in CONTRACTS:
        payload = orjson.dumps(contract.model_json_schema(), option=orjson.OPT_INDENT_2)
        (directory / f"{contract.__name__}.schema.json").write_bytes(payload + b"\n")


if __name__ == "__main__":
    export_schemas(Path("contracts/datasets/data"))
