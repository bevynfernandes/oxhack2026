"""Additive research writes and exact read-only job/report retrieval."""

from fastapi import APIRouter, Depends

from oxhack2026.api.repository import RepositoryUnavailable, ResourceNotFound
from oxhack2026.api.research_schemas import ResearchJob, ResearchReport, ResearchRequest
from oxhack2026.api.routes.public import errors
from oxhack2026.api.schemas import Identifier
from oxhack2026.research.service import (
    ResearchService,
)


def get_research_service() -> ResearchService:
    """Raise RepositoryUnavailable until a durable worker is configured."""
    raise RepositoryUnavailable


research_dependency = Depends(get_research_service)
router = APIRouter()


@router.post(
    "/api/v1/research-jobs",
    status_code=202,
    responses=errors,
    operation_id="start_research",
)
def start_research(
    request: ResearchRequest, service: ResearchService = research_dependency
) -> ResearchJob:
    """Confirm exact saved identity and enqueue bounded public-source collection."""
    try:
        return service.create(request)
    except (OSError, ValueError) as error:
        raise RepositoryUnavailable from error


@router.get(
    "/api/v1/research-jobs/{job_id}", responses=errors, operation_id="research_job"
)
def research_job(
    job_id: Identifier, service: ResearchService = research_dependency
) -> ResearchJob:
    """Read actual persisted job state without running or restarting work."""
    try:
        return service.store.job(job_id)
    except KeyError as error:
        raise ResourceNotFound from error
    except (OSError, ValueError) as error:
        raise RepositoryUnavailable from error


@router.get(
    "/api/v1/research-reports/{report_id}",
    responses=errors,
    operation_id="research_report",
)
def research_report(
    report_id: Identifier, service: ResearchService = research_dependency
) -> ResearchReport:
    """Read exact immutable report/source bytes without inference or collection."""
    try:
        report = service.store.report(report_id)
    except KeyError as error:
        raise ResourceNotFound from error
    except (OSError, ValueError) as error:
        raise RepositoryUnavailable from error
    try:
        service.sources.snapshot(report.source_publication_id)
    except (OSError, ValueError, KeyError) as error:
        raise RepositoryUnavailable from error
    return report
