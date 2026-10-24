"""Packaging smoke checks for the template namespaces."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "package_name",
    [
        "oxhack2026",
        "oxhack2026.catalog",
        "oxhack2026.ingest",
        "oxhack2026.storage",
        "oxhack2026.features",
        "oxhack2026.models",
        "oxhack2026.evaluation",
        "oxhack2026.api",
        "oxhack2026.explanations",
        "oxhack2026.cli",
    ],
)
def test_package_import(package_name: str) -> None:
    """Verify that the installed scaffold exposes its planned namespaces.

    Args:
        package_name: Fully qualified package name to import.

    Returns:
        None.

    Raises:
        ModuleNotFoundError: If a namespace is missing from the scaffold.
        AssertionError: If import resolution returns the wrong module.
    """
    module = import_module(package_name)

    assert module.__name__ == package_name
