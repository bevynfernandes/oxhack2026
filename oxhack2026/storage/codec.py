"""Explicit Parquet representation of C1 observation revisions."""

from io import BytesIO

import polars as pl

from oxhack2026.storage.contracts import ObservationRevision

_UTC = pl.Datetime("us", "UTC")
OBSERVATION_SCHEMA = pl.Schema(
    {
        "schema_version": pl.String(),
        "revision_id": pl.String(),
        "series_id": pl.String(),
        "window": pl.Struct({"start": _UTC, "end": _UTC}),
        "value": pl.Int64(),
        "completeness": pl.String(),
        "published_at": _UTC,
        "assumed_available_at": _UTC,
        "available_at": _UTC,
        "availability_basis": pl.String(),
        "availability_policy_version": pl.String(),
        "first_collected_at": _UTC,
        "retrieved_at": _UTC,
        "extraction_id": pl.String(),
        "extraction_version": pl.String(),
        "filter_version": pl.String(),
        "source_revision_id": pl.String(),
        "supersedes_revision_id": pl.String(),
        "raw_artifact_sha256": pl.String(),
    }
)


def encode_observations(rows: tuple[ObservationRevision, ...]) -> bytes:
    """Encode validated rows as Parquet, retaining integer/null/UTC semantics.

    Args:
        rows: Selected immutable daily revisions, in stable order.
    Returns:
        Parquet bytes using the explicit data-v1 schema.
    Raises:
        ValueError: If a record cannot be represented by that schema.
    """
    frame = pl.DataFrame([row.model_dump() for row in rows], schema=OBSERVATION_SCHEMA)
    output = BytesIO()
    frame.write_parquet(output, compression="zstd")
    return output.getvalue()


def decode_observations(content: bytes) -> tuple[ObservationRevision, ...]:
    """Decode C1 Parquet only if all column types and records are valid.

    Args:
        content: Verified artifact bytes.
    Returns:
        Validated revisions in stored order.
    Raises:
        ValueError: For schema incompatibility or invalid records.
        polars.exceptions.PolarsError: For malformed Parquet.
    """
    frame = pl.read_parquet(BytesIO(content))
    if frame.schema != OBSERVATION_SCHEMA:
        message = "Observation Parquet schema differs from data-v1"
        raise ValueError(message)
    return tuple(
        ObservationRevision.model_validate(row) for row in frame.iter_rows(named=True)
    )
