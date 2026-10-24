"""Actual local worker transitions over published identities and bounded sources."""

import logging
from concurrent.futures import Executor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from oxhack2026.api.company_repository import CompanyRepository
from oxhack2026.api.repository import RepositoryUnavailable, ResourceNotFound
from oxhack2026.api.research_schemas import (
    ResearchJob,
    ResearchRequest,
    ResearchSourceState,
)
from oxhack2026.catalog.schemas import TimeWindow
from oxhack2026.research.attention import AttentionQuery, collect_attention
from oxhack2026.research.report import build_report
from oxhack2026.research.store import LocalResearchStore
from oxhack2026.storage.company import CompanySourceReader

logger = logging.getLogger(__name__)


class IdentityConfirmationRequired(Exception):
    """The entered name/domain does not match an exact saved company identity."""


@dataclass(frozen=True)
class ResearchService:
    """Bounded worker using durable state and exact existing company publications.

    Args:
        repository: Public-safe exact company reader, with explicit publications.
        sources: Verified underlying C1 reader sharing the artifact root.
        store: Durable jobs/reports and existing raw artifact root.
        executor: Lifecycle-managed bounded local worker executor.
    """

    repository: CompanyRepository
    sources: CompanySourceReader
    store: LocalResearchStore
    executor: Executor
    collection_enabled: bool = True

    def create(self, request: ResearchRequest) -> ResearchJob:
        """Confirm saved identity and persist/enqueue work; never collect inline.

        Args:
            request: User-confirmed exact saved company/domain selection.
        Returns:
            Actual queued state; later states are available through durable reads.
        Raises:
            IdentityConfirmationRequired: Domain or company cannot be confirmed.
            RepositoryUnavailable: Published data or worker is unavailable.
            OSError: Job persistence fails before enqueueing.
        """
        if not self.collection_enabled:
            raise RepositoryUnavailable
        try:
            saved = self.repository.company(
                request.assessment_publication_id, request.company_id
            )
        except ResourceNotFound as error:
            raise IdentityConfirmationRequired from error
        domain = (
            urlsplit(saved.company.website_url or "").hostname or ""
        ).removeprefix("www.")
        if domain != request.domain:
            raise IdentityConfirmationRequired
        job = ResearchJob(
            job_id=uuid4().hex,
            request=request,
            state="queued",
            requested_at=datetime.now(UTC),
            sources=(ResearchSourceState(state="pending"),),
        )
        self.store.save_job(job)
        try:
            self.executor.submit(self.run, job.job_id)
        except RuntimeError as error:
            self.store.save_job(
                job.model_copy(
                    update={
                        "state": "failed",
                        "finished_at": datetime.now(UTC),
                        "sources": (ResearchSourceState(state="failed"),),
                        "reason_codes": ("worker_unavailable",),
                    }
                )
            )
            raise RepositoryUnavailable from error
        return job

    def recover(self) -> None:
        """Resume queued jobs and fail interrupted running jobs under one worker lease.

        Raises:
            OSError: Durable job recovery cannot read/write its state.
            ValueError: Stored metadata is corrupt.
            RuntimeError: The lifecycle-managed executor is unavailable.
        """
        for job in self.store.jobs():
            if job.state == "queued":
                self.executor.submit(self.run, job.job_id)
            elif job.state == "running":
                self.store.save_job(
                    job.model_copy(
                        update={
                            "state": "failed",
                            "finished_at": datetime.now(UTC),
                            "sources": (
                                ResearchSourceState(
                                    state="failed",
                                    reason_codes=("worker_interrupted",),
                                ),
                            ),
                            "reason_codes": ("worker_interrupted",),
                        }
                    )
                )

    def run(self, job_id: str) -> None:
        """Claim and execute one job; record safe provider/storage failure states.

        Args:
            job_id: Persisted job identity; repeated claims cannot rerun work.
        Returns:
            None after terminal state, or when another worker owns the claim.
        Raises:
            OSError: Failure state itself cannot be persisted.
        """
        job = self.store.job(job_id)
        if job.state != "queued":
            return
        running = job.model_copy(
            update={
                "state": "running",
                "started_at": datetime.now(UTC),
                "sources": (ResearchSourceState(state="running"),),
            }
        )
        try:
            self.store.save_job(running)
        except ValueError:
            logger.error("Research job claim was rejected")  # noqa: TRY400
            return
        try:
            saved = self.repository.company(
                job.request.assessment_publication_id, job.request.company_id
            )
            source = self.sources.snapshot(saved.publication.source.snapshot_id)
            end = datetime.now(UTC).replace(microsecond=0)
            query = AttentionQuery(
                job.request.company_id,
                job.request.domain,
                TimeWindow(start=end - timedelta(days=30), end=end),
            )
            with httpx.Client() as client:
                captured = collect_attention(query, client, self.store.root, job_id)
            report = build_report(running, saved, source, captured)
            self.store.publish(report)
            reasons = () if captured.complete else ("provider_results_truncated",)
            finished = running.model_copy(
                update={
                    "state": "completed" if captured.complete else "partial",
                    "finished_at": datetime.now(UTC),
                    "report_id": report.report_id,
                    "reason_codes": reasons,
                    "sources": (
                        ResearchSourceState(
                            state="succeeded" if captured.complete else "partial",
                            reason_codes=reasons,
                        ),
                    ),
                }
            )
        except (
            httpx.HTTPError,
            OSError,
            ValueError,
            KeyError,
            RuntimeError,
            RepositoryUnavailable,
            ResourceNotFound,
        ):
            logger.error("Research provider or storage failed")  # noqa: TRY400
            finished = running.model_copy(
                update={
                    "state": "failed",
                    "finished_at": datetime.now(UTC),
                    "reason_codes": ("research_source_unavailable",),
                    "sources": (
                        ResearchSourceState(
                            state="failed",
                            reason_codes=("research_source_unavailable",),
                        ),
                    ),
                }
            )
        self.store.save_job(finished)
