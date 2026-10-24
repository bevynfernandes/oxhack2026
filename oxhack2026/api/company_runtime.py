"""Environment-configured company API over explicit local immutable publications."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import TypeAdapter, ValidationError

from oxhack2026.api.app import create_app
from oxhack2026.api.company_repository import PublishedCompanyRepository
from oxhack2026.api.schemas import Identifier
from oxhack2026.research.runtime import configure_research
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
        return configure_research(create_app())
    try:
        publications = TypeAdapter(tuple[Identifier, ...]).validate_python(
            tuple(item.strip() for item in selection.split(","))
        )
    except ValidationError:
        logger.error("Company publication configuration is invalid")  # noqa: TRY400
        return configure_research(create_app())
    directory = Path(root).expanduser()
    sources = LocalCompanyStore(directory)
    repository = PublishedCompanyRepository(
        sources, LocalCompanyAssessmentStore(directory), publications
    )
    app = create_app(company_repository=repository)
    return configure_research(app, repository)
