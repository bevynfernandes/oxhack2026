"""Run with python -m oxhack2026.api.export_contract to export C3 OpenAPI."""

import argparse
from pathlib import Path

import orjson

from oxhack2026.api.app import create_app


def export_contract(destination: Path, *, check: bool = False) -> bool:
    """Write or compare the canonical OpenAPI export without repository access.

    Args:
        destination: File to write, or compare in check mode.
        check: Compare bytes without modifying the file when true.

    Returns:
        Whether the file matches the generated contract after this operation.

    Raises:
        OSError: The destination cannot be read or written.
    """
    content = (
        orjson.dumps(
            create_app().openapi(), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
        )
        + b"\n"
    )
    if check:
        return destination.is_file() and destination.read_bytes() == content
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("contracts/api/openapi.json")
    )
    arguments = parser.parse_args()
    raise SystemExit(
        0 if export_contract(arguments.output, check=arguments.check) else 1
    )
