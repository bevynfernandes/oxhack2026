"""Environment-configured company API over explicit local immutable publications."""

import fcntl
import logging
import os
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import TypeAdapter, ValidationError

from oxhack2026.api.app import create_app
from oxhack2026.api.company_repository import PublishedCompanyRepository
from oxhack2026.api.routes.research import get_research_service
from oxhack2026.api.schemas import Identifier
from oxhack2026.research.service import ResearchService
from oxhack2026.research.store import LocalResearchStore
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import (
    LocalCompanyAssessmentStore,
)

logger = logging.getLogger(__name__)


def create_company_app() -> FastAPI:
    """Build a company application from explicit environment configuration.

    Reads SIGNALSHIFT_COMPANY_ROOT and comma-separated
    SIGNALSHIFT_COMPANY_PUBLICATIONS. Missing/invalid configuration leaves data
    and readiness unavailable. No import-time reads, source collection, model
    execution, latest-version selection or synthetic fallback occurs.

    SIGNALSHIFT_RESEARCH_ENABLED=1 explicitly enables a writable local worker
    lifecycle with two threads and one exclusive process lease per store root.
    Without this flag all data operations remain published reads.

    Returns:
        ASGI application with exact published readers and an optional research
        worker. Artifact integrity is verified on reads; failures return safe 503s.
    """
    root = os.environ.get("SIGNALSHIFT_COMPANY_ROOT", "").strip()
    selection = os.environ.get("SIGNALSHIFT_COMPANY_PUBLICATIONS", "").strip()
    if not root or not selection:
        if root or selection:
            logger.error("Company root and explicit publication selection are required")
        return create_app()
    try:
        publications = TypeAdapter(tuple[Identifier, ...]).validate_python(
            tuple(item.strip() for item in selection.split(","))
        )
    except ValidationError:
        logger.error("Company publication configuration is invalid")  # noqa: TRY400
        return create_app()
    directory = Path(root).expanduser()
    sources = LocalCompanyStore(directory)
    repository = PublishedCompanyRepository(
        sources, LocalCompanyAssessmentStore(directory), publications
    )
    app = create_app(company_repository=repository)
    if os.environ.get("SIGNALSHIFT_RESEARCH_ENABLED") != "1":
        return app

    @asynccontextmanager
    async def research_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".research-worker.lock").open("a+b") as lease:
            fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with ThreadPoolExecutor(max_workers=2) as executor:
                service = ResearchService(
                    repository, sources, LocalResearchStore(directory), executor
                )
                _app.dependency_overrides[get_research_service] = lambda: service
                service.recover()
                yield

    app.router.lifespan_context = research_lifespan
    return app
