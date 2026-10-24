"""Snapshot-scoped company routes; comparison reuses these exact profiles."""

from fastapi import APIRouter, Depends

from oxhack2026.api import company_schemas as s
from oxhack2026.api.company_repository import CompanyRepository
from oxhack2026.api.repository import RepositoryUnavailable
from oxhack2026.api.routes.public import errors
from oxhack2026.api.schemas import Identifier


def get_company_repository() -> CompanyRepository:
    """Raise RepositoryUnavailable until an actual published reader is injected."""
    raise RepositoryUnavailable


company_dependency = Depends(get_company_repository)
router = APIRouter()


@router.get(
    "/api/v1/company-snapshots", responses=errors, operation_id="company_snapshots"
)
def company_snapshots(
    repo: CompanyRepository = company_dependency,
) -> s.CompanyPublications:
    """Enumerate explicit verified company assessment publications."""
    return repo.publications()


@router.get(
    "/api/v1/company-snapshots/{snapshot_id}/companies",
    responses=errors,
    operation_id="companies",
)
def companies(
    snapshot_id: Identifier, repo: CompanyRepository = company_dependency
) -> s.CompanyList:
    """Read an exact assessment publication ID, never a source-only alias."""
    result = repo.companies(snapshot_id)
    if result.publication.assessment.publication_id != snapshot_id:
        raise RepositoryUnavailable
    return result


@router.get(
    "/api/v1/company-snapshots/{snapshot_id}/companies/{company_id}",
    responses=errors,
    operation_id="company",
)
def company(
    snapshot_id: Identifier,
    company_id: Identifier,
    repo: CompanyRepository = company_dependency,
) -> s.CompanyDetail:
    """Read a pre-outcome profile with public-safe sources and explicit unknowns."""
    result = repo.company(snapshot_id, company_id)
    if (
        result.publication.assessment.publication_id != snapshot_id
        or result.company.company_id != company_id
        or result.assessment.company_id != company_id
        or result.assessment.source_snapshot_id != result.publication.source.snapshot_id
    ):
        raise RepositoryUnavailable
    return result
