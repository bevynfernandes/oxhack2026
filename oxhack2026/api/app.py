"""Read-only FastAPI factory with no import-time connections or synthetic fallback."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from oxhack2026.api import schemas as s
from oxhack2026.api.repository import (
    ImmatureOutcome,
    PublishedRepository,
    RepositoryUnavailable,
    ResourceNotFound,
)
from oxhack2026.api.routes.public import get_repository, router

logger = logging.getLogger(__name__)


async def unavailable(_request: Request, _error: Exception) -> JSONResponse:
    """Return a safe 503 for repository or response-validation failures."""
    logger.error("Published repository or response contract unavailable")
    return JSONResponse(
        status_code=503,
        content=s.Error(
            code="repository_unavailable",
            message="Published data is unavailable. Try again later.",
        ).model_dump(),
    )


async def not_found(_request: Request, _error: Exception) -> JSONResponse:
    """Return a safe 404 for unknown published resources."""
    return JSONResponse(
        status_code=404,
        content=s.Error(
            code="not_found", message="The requested published resource was not found."
        ).model_dump(),
    )


async def immature(_request: Request, _error: Exception) -> JSONResponse:
    """Return a safe 409 until complete outcomes can be revealed."""
    return JSONResponse(
        status_code=409,
        content=s.Error(
            code="outcome_immature",
            message="Complete outcomes are not yet available for this batch.",
        ).model_dump(),
    )


async def invalid(_request: Request, _error: Exception) -> JSONResponse:
    """Return a safe 422 without reflecting request values or secrets."""
    return JSONResponse(
        status_code=422,
        content=s.Error(
            code="invalid_request",
            message="Check identifiers, filters and the five distinct organizations.",
        ).model_dump(),
    )


def create_app(repository: PublishedRepository | None = None) -> FastAPI:
    """Build an API without vendor access or synthetic results.

    Args:
        repository: Published read/scoring adapter. None permits liveness/OpenAPI
            but reports readiness as unavailable. The caller owns its lifecycle.

    Returns:
        An ASGI application with strict public responses and redacted failures.
    """
    app = FastAPI(title="SignalShift", version=s.CONTRACT_VERSION)
    if repository is not None:
        app.dependency_overrides[get_repository] = lambda: repository
    for error in (RepositoryUnavailable, ValidationError, ResponseValidationError):
        app.add_exception_handler(error, unavailable)
    app.add_exception_handler(ResourceNotFound, not_found)
    app.add_exception_handler(ImmatureOutcome, immature)
    app.add_exception_handler(RequestValidationError, invalid)
    app.include_router(router)
    return app
