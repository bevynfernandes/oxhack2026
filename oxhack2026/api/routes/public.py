"""Public read and reveal routes; numerical policy stays in published artifacts."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.exceptions import RequestValidationError

from oxhack2026.api import schemas as s
from oxhack2026.api.company_repository import CompanyRepository
from oxhack2026.api.repository import (
    ImmatureOutcome,
    PublishedRepository,
    RepositoryUnavailable,
    ResourceNotFound,
)


def get_repository() -> PublishedRepository:
    """Raise RepositoryUnavailable until the application injects a read adapter."""
    raise RepositoryUnavailable


repo_dependency = Depends(get_repository)


def get_readiness_repository() -> PublishedRepository | CompanyRepository:
    """Raise RepositoryUnavailable until the factory selects its readiness adapter."""
    raise RepositoryUnavailable


readiness_dependency = Depends(get_readiness_repository)
errors: dict[int | str, dict[str, object]] = {
    code: {"model": s.Error} for code in (404, 409, 422, 503)
}
router = APIRouter()


def _require(condition: bool) -> None:
    if not condition:
        raise RepositoryUnavailable


def _batch(repository: PublishedRepository, batch_id: str) -> s.ForecastBatch:
    batch = repository.forecast(batch_id)
    _require(batch.batch_id == batch_id)
    return batch


def _rankings(repository: PublishedRepository, batch: s.ForecastBatch) -> s.Rankings:
    rankings = repository.rankings(batch.batch_id)
    _require(rankings.batch_id == batch.batch_id)
    tools = {item.tool_id: item for item in batch.results}
    for ordering in (rankings.primary, *rankings.baselines):
        _require(len(set(ordering.tool_ids)) == len(ordering.tool_ids))
        _require(all(tool_id in tools for tool_id in ordering.tool_ids))
        _require(all(tools[tool_id].ranking_eligible for tool_id in ordering.tool_ids))
        _require(
            len({tools[tool_id].organization_id for tool_id in ordering.tool_ids})
            == len(ordering.tool_ids)
        )
    _require(
        rankings.recommended_tool_ids
        == rankings.primary.tool_ids[: len(rankings.recommended_tool_ids)]
    )
    _require(all(item.tool_id in tools for item in rankings.exclusions))
    return rankings


@router.get("/api/v1/health/live", operation_id="liveness")
def liveness() -> s.Health:
    """Return process health; no repository or vendor access is performed."""
    return s.Health(status="ready")


@router.get(
    "/api/v1/health/ready",
    responses={**errors, 503: {"model": s.Health | s.Error}},
    operation_id="readiness",
)
def readiness(
    response: Response,
    repo: PublishedRepository | CompanyRepository = readiness_dependency,
) -> s.Health:
    """Return required repository readiness; use HTTP 503 when unavailable."""
    health = repo.readiness()
    if health.status != "ready":
        response.status_code = 503
    return health


@router.get("/api/v1/catalog", responses=errors, operation_id="catalog")
def catalog(
    ecosystem: s.Ecosystem | None = None,
    batch_id: s.Identifier | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    repo: PublishedRepository = repo_dependency,
) -> s.Catalog:
    """Return verified identities, frozen to batch_id when provided."""
    result = repo.catalog(ecosystem, batch_id)
    _require(ecosystem is None or all(t.ecosystem == ecosystem for t in result.tools))
    if batch_id is not None:
        batch = _batch(repo, batch_id)
        _require(
            result.catalog_version == batch.provenance.catalog_version
            and result.mapping_version == batch.provenance.mapping_version
            and result.synthetic == batch.provenance.synthetic
        )
        if result.membership_basis == "contemporary_reconstruction":
            _require(
                batch.mode == "reconstructed"
                and result.cohort_kind == "contemporary_catalogue"
                and result.recorded_at is not None
            )
        if batch.mode == "prospective":
            _require(
                result.recorded_at is not None
                and result.recorded_at <= batch.decision_at
            )
        for tool in result.tools:
            retrospective = any(
                evidence.available_at > batch.decision_at
                or evidence.observed_at > batch.decision_at
                for evidence in tool.mapping_evidence
            )
            _require(all(item.kind == "mapping" for item in tool.mapping_evidence))
            _require((tool.mapping_verification == "retrospective") == retrospective)
            _require(not retrospective or batch.mode == "reconstructed")
    if q:
        search = q.casefold()
        return result.model_copy(
            update={
                "tools": tuple(
                    tool
                    for tool in result.tools
                    if search
                    in " ".join(
                        (tool.tool_name, tool.organization_name, tool.package_name)
                    ).casefold()
                )
            }
        )
    return result


@router.get("/api/v1/cutoffs", responses=errors, operation_id="cutoffs")
def cutoffs(
    ecosystem: s.Ecosystem | None = None,
    target_id: s.Target | None = None,
    repo: PublishedRepository = repo_dependency,
) -> s.Cutoffs:
    """Return only saved ecosystem/target/cutoff combinations."""
    result = repo.cutoffs(ecosystem, target_id)
    _require(
        all(
            (ecosystem is None or item.ecosystem == ecosystem)
            and (target_id is None or item.target_id == target_id)
            for item in result.items
        )
    )
    return result


@router.get("/api/v1/forecasts/{batch_id}", responses=errors, operation_id="forecasts")
def forecasts(
    batch_id: s.Identifier, repo: PublishedRepository = repo_dependency
) -> s.ForecastBatch:
    """Return the immutable forecast; this DTO cannot serialize future actuals."""
    return _batch(repo, batch_id)


@router.get("/api/v1/rankings/{batch_id}", responses=errors, operation_id="rankings")
def rankings(
    batch_id: s.Identifier, repo: PublishedRepository = repo_dependency
) -> s.Rankings:
    """Return saved policy ordering, exclusions and baseline comparisons."""
    return _rankings(repo, _batch(repo, batch_id))


@router.get("/api/v1/tools/{tool_id}/history", responses=errors, operation_id="history")
def history(
    tool_id: s.Identifier,
    batch_id: s.Identifier,
    limit: Annotated[int, Query(ge=1, le=3660)] = 365,
    repo: PublishedRepository = repo_dependency,
) -> s.History:
    """Return bounded observations; reject an adapter leaking future data."""
    batch = _batch(repo, batch_id)
    if tool_id not in {item.tool_id for item in batch.results}:
        raise ResourceNotFound
    result = repo.history(tool_id, batch_id, limit)
    _require(
        result.batch_id == batch_id
        and result.tool_id == tool_id
        and result.dataset_version == batch.provenance.dataset_version
        and result.observation_window_end == batch.observation_window_end
        and len(result.points) <= limit
    )
    _require(
        all(
            point.window.end <= batch.observation_window_end
            and point.available_at <= batch.decision_at
            for point in result.points
        )
    )
    return result


@router.post(
    "/api/v1/replays/{batch_id}/reveal", responses=errors, operation_id="reveal"
)
def reveal(
    batch_id: s.Identifier,
    selection: s.RevealRequest,
    response: Response,
    repo: PublishedRepository = repo_dependency,
) -> s.Reveal:
    """Return mature outcomes and authoritative scores for the exact selection."""
    response.headers["Cache-Control"] = "no-store"
    batch = _batch(repo, batch_id)
    ranking = _rankings(repo, batch)
    tools = {item.tool_id: item for item in batch.results}
    selectable = {tools[key].organization_id for key in ranking.primary.tool_ids}
    if not set(selection.organization_ids).issubset(selectable):
        raise RequestValidationError([])
    if not ranking.reveal_allowed:
        raise ImmatureOutcome
    result = repo.reveal(batch_id, selection)
    _require(
        result.batch_id == batch_id
        and result.selected_organization_ids == selection.organization_ids
        and result.selection_score.organization_ids == selection.organization_ids
        and batch.target_window.end <= result.available_at <= datetime.now(UTC)
        and all(item.tool_id in tools for item in result.outcomes)
    )
    return result


@router.get(
    "/api/v1/evaluations/{evaluation_id}", responses=errors, operation_id="evaluation"
)
def evaluation(
    evaluation_id: s.Identifier, repo: PublishedRepository = repo_dependency
) -> s.Evaluation:
    """Return the exact published evaluation, including failed challengers."""
    result = repo.evaluation(evaluation_id)
    _require(result.evaluation_id == evaluation_id)
    return result


@router.get("/api/v1/data-health", responses=errors, operation_id="data_health")
def data_health(repo: PublishedRepository = repo_dependency) -> s.DataHealth:
    """Return public source freshness and coverage diagnostics."""
    return repo.data_health()
