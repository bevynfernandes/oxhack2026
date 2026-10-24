"""Explicit synthetic API composition for browser tests; never production startup."""

from pathlib import Path
from unittest.mock import Mock, create_autospec

import orjson
from fastapi import FastAPI

from oxhack2026.api import schemas as s
from oxhack2026.api.app import create_app as create_api
from oxhack2026.api.company_repository import (
    PublishedCompanyRepository,
)
from oxhack2026.api.repository import PublishedRepository, ResourceNotFound
from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.storage.company import CompanySourceReader
from oxhack2026.storage.company_assessments import (
    CompanyAssessmentManifest,
    CompanyAssessmentReader,
)


def create_app() -> FastAPI:
    """Return a test-only ASGI app using labelled fixtures and mocked repositories.

    Raises:
        OSError: The committed fixture cannot be read.
        ValueError: Fixture JSON or its public schemas are invalid.
    """
    payload = orjson.loads(Path(__file__).with_name("scouting.json").read_bytes())
    batch = s.ForecastBatch.model_validate(payload["forecast"])
    catalog = s.Catalog.model_validate(payload["catalog"])
    rankings = s.Rankings.model_validate(payload["rankings"])
    outcome = s.Reveal.model_validate(payload["reveal"])
    history = s.History.model_validate(payload["history"])
    evaluation = s.Evaluation.model_validate(payload["evaluation"])
    cutoffs = s.Cutoffs.model_validate(payload["cutoffs"])
    repository: Mock = create_autospec(PublishedRepository, instance=True)

    def require_batch(batch_id: str) -> s.ForecastBatch:
        if batch_id != batch.batch_id:
            raise ResourceNotFound
        return batch

    def read_catalog(ecosystem: str | None, batch_id: str | None) -> s.Catalog:
        if batch_id is not None:
            require_batch(batch_id)
        return catalog.model_copy(
            update={
                "tools": tuple(
                    tool
                    for tool in catalog.tools
                    if ecosystem is None or tool.ecosystem == ecosystem
                )
            }
        )

    def read_history(tool_id: str, batch_id: str, limit: int) -> s.History:
        require_batch(batch_id)
        return history.model_copy(
            update={"tool_id": tool_id, "points": history.points[-limit:]}
        )

    def reveal(batch_id: str, selection: s.RevealRequest) -> s.Reveal:
        require_batch(batch_id)
        return outcome.model_copy(
            update={
                "selected_organization_ids": selection.organization_ids,
                "selection_score": outcome.selection_score.model_copy(
                    update={
                        "organization_ids": selection.organization_ids,
                    }
                ),
            }
        )

    def read_cutoffs(ecosystem: str | None, target_id: str | None) -> s.Cutoffs:
        return s.Cutoffs(
            items=tuple(
                item
                for item in cutoffs.items
                if (ecosystem is None or item.ecosystem == ecosystem)
                and (target_id is None or item.target_id == target_id)
            )
        )

    def read_evaluation(evaluation_id: str) -> s.Evaluation:
        if evaluation_id != evaluation.evaluation_id:
            raise ResourceNotFound
        return evaluation

    repository.readiness.return_value = s.Health(
        status="ready", reasons=("synthetic_test_composition",)
    )
    repository.forecast.side_effect = require_batch
    repository.catalog.side_effect = read_catalog
    repository.cutoffs.side_effect = read_cutoffs
    repository.rankings.return_value = rankings
    repository.history.side_effect = read_history
    repository.reveal.side_effect = reveal
    repository.evaluation.side_effect = read_evaluation
    repository.data_health.return_value = s.DataHealth.model_validate(
        payload["data_health"]
    )
    company_payload = orjson.loads(
        Path(__file__).with_name("companies.json").read_bytes()
    )
    sources = create_autospec(CompanySourceReader, instance=True)
    assessments = create_autospec(CompanyAssessmentReader, instance=True)
    sources.snapshot.return_value = CompanySourceSnapshot.model_validate(
        company_payload["source"]
    )
    publication = CompanyAssessmentManifest.model_validate(
        company_payload["publication"]
    )
    assessments.manifest.return_value = publication
    assessments.assessments.return_value = tuple(
        CompanyAssessment.model_validate(row) for row in company_payload["assessments"]
    )
    return create_api(
        repository,
        company_repository=PublishedCompanyRepository(
            sources, assessments, (publication.publication_id,)
        ),
    )
