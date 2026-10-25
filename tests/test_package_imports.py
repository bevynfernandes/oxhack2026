"""Packaging smoke checks for the application namespaces."""

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
        "oxhack2026.research",
        "oxhack2026.api.routes",
        "oxhack2026.cli",
    ],
)
def test_package_import(package_name: str) -> None:
    """Verify that the application exposes its package namespaces.

    Args:
        package_name: Fully qualified package name to import.

    Returns:
        None.

    Raises:
        ModuleNotFoundError: If a namespace is missing from the application.
        AssertionError: If import resolution returns the wrong module.
    """
    module = import_module(package_name)

    assert module.__name__ == package_name
