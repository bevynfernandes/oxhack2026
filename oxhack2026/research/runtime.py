"""Optional standalone research runtime with a single process lease and durable
reads."""

import fcntl
import os
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import ParamSpec, TypeVar

from fastapi import FastAPI

from oxhack2026.api.company_repository import CompanyRepository
from oxhack2026.api.routes.research import get_research_service
from oxhack2026.api.routes.research_v2 import get_v2_service
from oxhack2026.models.dimension_serving import DimensionModelRegistry
from oxhack2026.research.service import ResearchService
from oxhack2026.research.store import LocalResearchStore
from oxhack2026.research.v2_service import V2Service
from oxhack2026.research.v2_store import V2Store
from oxhack2026.storage.company import LocalCompanyStore

_Parameters = ParamSpec("_Parameters")
_Value = TypeVar("_Value")


class ReadOnlyExecutor(Executor):
    """Reject legacy writes while allowing existing report reads."""

    def submit(
        self,
        fn: Callable[_Parameters, _Value],
        /,
        *args: _Parameters.args,
        **kwargs: _Parameters.kwargs,
    ) -> Future[_Value]:
        """Raise RuntimeError because collection is disabled."""
        message = "Research collection is disabled"
        raise RuntimeError(message)


def configure_research(
    app: FastAPI,
    repository: CompanyRepository | None = None,
    dimension_models: DimensionModelRegistry | None = None,
) -> FastAPI:
    """Attach persistent reads and an opt-in worker, independent of saved publications.

    Args:
        app: Company or standalone API to configure.
        repository: Optional reviewed saved-company publication reader.
        dimension_models: Verified experimental proxies for newly composed reports.
    Returns:
        The same application with configured research dependencies and lifecycle.
    Raises:
        OSError: Worker lease or persistent root cannot be acquired at startup.
    """
    selection = (
        os.environ.get("SIGNALSHIFT_RESEARCH_ROOT", "").strip()
        or os.environ.get("SIGNALSHIFT_COMPANY_ROOT", "").strip()
    )
    if not selection:
        return app
    directory = Path(selection).expanduser()
    read_service = V2Service(
        V2Store(directory), repository=repository, dimension_models=dimension_models
    )
    app.dependency_overrides[get_v2_service] = lambda: read_service
    # Legacy stored reports remain readable even when new collection is disabled.
    if repository is not None:
        legacy_sources = LocalCompanyStore(
            Path(os.environ["SIGNALSHIFT_COMPANY_ROOT"]).expanduser()
        )
        legacy = ResearchService(
            repository,
            legacy_sources,
            LocalResearchStore(legacy_sources.root),
            ReadOnlyExecutor(),
            False,
        )
        app.dependency_overrides[get_research_service] = lambda: legacy
    if os.environ.get("SIGNALSHIFT_RESEARCH_ENABLED") != "1":
        return app

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".research-worker.lock").open("a+b") as lease:
            fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="research"
            ) as executor:
                service = V2Service(
                    V2Store(directory),
                    executor,
                    repository,
                    dimension_models=dimension_models,
                )
                _app.dependency_overrides[get_v2_service] = lambda: service
                service.recover()
                if repository is not None:
                    legacy_service = ResearchService(
                        repository,
                        legacy_sources,
                        LocalResearchStore(legacy_sources.root),
                        executor,
                    )
                    _app.dependency_overrides[get_research_service] = lambda: (
                        legacy_service
                    )
                    legacy_service.recover()
                try:
                    yield
                finally:
                    _app.dependency_overrides[get_v2_service] = lambda: read_service

    app.router.lifespan_context = lifespan
    return app
