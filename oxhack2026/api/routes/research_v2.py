"""Additive standalone research API; polling and capabilities never fetch vendors."""

import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from oxhack2026.api.evidence_mapping_schemas import MappingJob, MappingJobRequest
from oxhack2026.api.repository import RepositoryUnavailable
from oxhack2026.api.research_v2_schemas import (
    PROVIDERS,
    Capabilities,
    CompanySearchRequest,
    CompanySearchResult,
    DiscoveryRequest,
    Identity,
    Job,
    JobRequest,
    ProviderCapability,
    Report,
)
from oxhack2026.api.schemas import Identifier
from oxhack2026.research.v2_service import ConfirmationRequired, QueueFull, V2Service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2")


def get_v2_service() -> V2Service | None:
    """Return unconfigured state until runtime supplies a persistent service."""
    return None


_dependency = Depends(get_v2_service)


def _service(service: V2Service | None) -> V2Service:
    if service is None:
        raise RepositoryUnavailable
    return service


def _call[Result](operation: Callable[[], Result]) -> Result:
    try:
        return operation()
    except KeyError as error:
        raise HTTPException(404, "Research resource not found") from error
    except QueueFull as error:
        raise HTTPException(
            429, "Research queue is full", headers={"Retry-After": "30"}
        ) from error
    except ConfirmationRequired as error:
        raise HTTPException(409, "Confirm a completed identity preview") from error
    except ValueError as error:
        raise HTTPException(422, "Invalid research input or stored data") from error
    except (OSError, RuntimeError) as error:
        logger.error("Research storage or worker unavailable")  # noqa: TRY400
        raise RepositoryUnavailable from error


def _read[Result](operation: Callable[[], Result]) -> Result:
    try:
        return operation()
    except ValueError as error:
        raise RepositoryUnavailable from error


@router.get("/research-capabilities", operation_id="research_v2_capabilities")
def capabilities(service: V2Service | None = _dependency) -> Capabilities:
    """Read configured worker, browser and provider availability without vendor
    requests."""
    if service is None:
        return Capabilities(
            storage_available=False,
            collection_enabled=False,
            worker_available=False,
            browser_available=False,
            providers=tuple(
                ProviderCapability(
                    provider=provider,
                    available=False,
                    reason="Research storage is unconfigured",
                )
                for provider in PROVIDERS
            ),
        )
    return _call(service.capabilities)


@router.post(
    "/research-identities", status_code=202, operation_id="research_v2_discover"
)
def discover(
    request: DiscoveryRequest, service: V2Service | None = _dependency
) -> Identity:
    """Queue bounded identity discovery; collection requires a subsequent
    confirmation."""
    return _call(lambda: _service(service).discover(request))


@router.post("/company-search", operation_id="research_v2_company_search")
def search_companies(
    request: CompanySearchRequest, service: V2Service | None = _dependency
) -> CompanySearchResult:
    """Find candidate websites by name or URL; no research job starts here.

    Args:
        request: Bounded name or URL query.
        service: Configured source-safe research service.
    Returns:
        Source-linked candidate domains and explicit discovery limitations.
    Raises:
        HTTPException: Input is invalid or the configured service is unavailable.
    """
    return _call(lambda: _service(service).search(request.query))


@router.get("/research-identities/{identity_id}", operation_id="research_v2_identity")
def identity(
    identity_id: Identifier, service: V2Service | None = _dependency
) -> Identity:
    """Read exact identity status, redirect conflicts, evidence and optional saved
    context."""
    return _call(lambda: _read(lambda: _service(service).store.identity(identity_id)))


@router.post("/research-jobs", status_code=202, operation_id="research_v2_start")
def start(request: JobRequest, service: V2Service | None = _dependency) -> Job:
    """Confirm the preview and coalesce active work; terminal refreshes create new
    reports."""
    return _call(lambda: _service(service).create(request))


@router.get("/research-jobs/{job_id}", operation_id="research_v2_job")
def job(job_id: Identifier, service: V2Service | None = _dependency) -> Job:
    """Read durable per-source progress; never enqueue or restart work."""
    return _call(lambda: _read(lambda: _service(service).store.job(job_id)))


@router.get("/research-reports/{report_id}", operation_id="research_v2_report")
def report(report_id: Identifier, service: V2Service | None = _dependency) -> Report:
    """Read the immutable report and verify all capture hashes without source
    fetching."""
    return _call(lambda: _read(lambda: _service(service).store.report(report_id)))


@router.post("/research-mapping-jobs", status_code=202, operation_id="research_v2_map")
def start_mapping(
    request: MappingJobRequest, service: V2Service | None = _dependency
) -> MappingJob:
    """Explicitly re-map retained evidence into a new immutable report."""
    return _call(lambda: _service(service).create_mapping(request))


@router.get("/research-mapping-jobs/{job_id}", operation_id="research_v2_mapping_job")
def mapping_job(
    job_id: Identifier, service: V2Service | None = _dependency
) -> MappingJob:
    """Read durable interpretation progress without enqueueing or vendor access."""
    return _call(lambda: _read(lambda: _service(service).store.mapping_job(job_id)))
