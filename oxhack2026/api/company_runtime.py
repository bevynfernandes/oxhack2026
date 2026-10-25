"""Environment-configured company API over explicit local immutable publications."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import TypeAdapter, ValidationError

from oxhack2026.api.app import create_app
from oxhack2026.api.company_repository import PublishedCompanyRepository
from oxhack2026.api.schemas import Identifier
from oxhack2026.models.dimension_serving import (
    DEFAULT_DIMENSION_MODEL_ROOT,
    DimensionModelRegistry,
)
from oxhack2026.research.runtime import configure_research
from oxhack2026.storage.company import LocalCompanyStore
from oxhack2026.storage.company_assessments import (
    LocalCompanyAssessmentStore,
)

logger = logging.getLogger(__name__)
PRELOADED_COMPANY_ROOT = (
    Path(__file__).resolve().parents[1] / "catalog/bundled/preloaded_companies_v1"
)
PRELOADED_PUBLICATION_ID = "company-assessments-preloaded-20261025-v1"


def _dimension_registry() -> DimensionModelRegistry | None:
    root = Path(
        os.environ.get(
            "SIGNALSHIFT_DIMENSION_MODELS_ROOT", str(DEFAULT_DIMENSION_MODEL_ROOT)
        )
    ).expanduser()
    if not (root / "run.json").is_file():
        return None
    try:
        return DimensionModelRegistry.load(root)
    except (ValueError, OSError):
        logger.error(
            "Experimental dimension bundle unavailable or invalid", exc_info=True
        )
        return None


def create_company_app() -> FastAPI:
    """Build a company application from explicit environment configuration.

    Reads SIGNALSHIFT_COMPANY_ROOT and comma-separated
    SIGNALSHIFT_COMPANY_PUBLICATIONS. With neither configured, the two dated real
    preloaded companies are available unless SIGNALSHIFT_PRELOADED_COMPANIES=0.
    Partial/invalid explicit configuration remains unavailable. No import-time
    reads, source collection, training,
    latest-version selection or synthetic fallback occurs. An explicit dimension
    bundle (or the pinned local experimental bundle) is verified at creation;
    eligible company requests run portable SDK proxy inference independently of
    saved assessments and the still-untrained company-outcome forecasts.

    SIGNALSHIFT_RESEARCH_ENABLED=1 explicitly enables a writable local worker
    lifecycle with two threads and one exclusive process lease per store root.
    Without this flag all data operations remain published reads.

    Returns:
        ASGI application with exact published readers and an optional research
        worker. Artifact integrity is verified on reads; failures return safe 503s.
    """
    root = os.environ.get("SIGNALSHIFT_COMPANY_ROOT", "").strip()
    selection = os.environ.get("SIGNALSHIFT_COMPANY_PUBLICATIONS", "").strip()
    models = _dimension_registry()
    if (
        not root
        and not selection
        and os.environ.get("SIGNALSHIFT_PRELOADED_COMPANIES", "1") == "1"
    ):
        root = str(PRELOADED_COMPANY_ROOT)
        selection = PRELOADED_PUBLICATION_ID
    if not root or not selection:
        if root or selection:
            logger.error("Company root and explicit publication selection are required")
        return configure_research(create_app(), dimension_models=models)
    try:
        publications = TypeAdapter(tuple[Identifier, ...]).validate_python(
            tuple(item.strip() for item in selection.split(","))
        )
    except ValidationError:
        logger.error("Company publication configuration is invalid")  # noqa: TRY400
        return configure_research(create_app(), dimension_models=models)
    directory = Path(root).expanduser()
    sources = LocalCompanyStore(directory)
    repository = PublishedCompanyRepository(
        sources,
        LocalCompanyAssessmentStore(directory),
        publications,
        dimension_models=models,
    )
    app = create_app(company_repository=repository)
    return configure_research(app, repository, models)
