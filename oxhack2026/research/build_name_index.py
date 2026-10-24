"""Rebuild the attributed name-discovery snapshot from an official CSV download."""

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import orjson
import polars as pl


def build_name_index(source: Path, destination: Path) -> None:
    """Create a compact sorted directory without transferring popularity to scores.

    Args:
        source: Unmodified CSV from downloads.majestic.com/majestic_million.csv.
        destination: Parquet path; an adjacent JSON provenance manifest is written.
    Returns:
        None. Writes the directory and manifest, retaining the input unchanged.
    Raises:
        OSError: Input or output cannot be accessed.
        polars.exceptions.PolarsError: Required source fields are invalid.
    """
    directory = (
        pl.read_csv(
            source,
            columns=["GlobalRank", "Domain"],
            schema_overrides={"GlobalRank": pl.UInt32, "Domain": pl.String},
        )
        .rename({"GlobalRank": "source_rank", "Domain": "domain"})
        .with_columns(pl.col("domain").str.to_lowercase())
        .with_columns(
            pl.col("domain")
            .str.split(".")
            .list.first()
            .str.replace_all(r"[^a-z0-9]", "")
            .alias("name_key")
        )
        .filter(pl.col("name_key").str.len_chars() >= 2)
        .unique(subset="domain", keep="first", maintain_order=True)
        .sort(["name_key", "source_rank"])
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    directory.write_parquet(
        destination, compression="zstd", compression_level=12, row_group_size=16384
    )
    with source.open("rb") as stream:
        source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    with destination.open("rb") as stream:
        artifact_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    destination.with_suffix(".json").write_bytes(
        orjson.dumps(
            {
                "source": "https://downloads.majestic.com/majestic_million.csv",
                "publisher": "Majestic Million",
                "license": "https://creativecommons.org/licenses/by/3.0/",
                "documentation": "https://majestic.com/reports/majestic-million",
                "source_file_modified_at": datetime.fromtimestamp(
                    source.stat().st_mtime, UTC
                ).isoformat(),
                "built_at": datetime.now(UTC).isoformat(),
                "source_sha256": source_hash,
                "artifact_sha256": artifact_hash,
                "rows": directory.height,
                "transformation": "Domain, GlobalRank only; lowercase; lexical index",
                "purpose": "Unverified website candidates only, never model inputs",
            },
            option=orjson.OPT_INDENT_2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    build_name_index(arguments.source, arguments.destination)
