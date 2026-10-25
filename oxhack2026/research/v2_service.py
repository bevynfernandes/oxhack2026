"""Bounded on-demand identity discovery and checkpointed multi-source workers."""

import importlib.util
import logging
import os
import time
from concurrent.futures import Executor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

import httpx

from oxhack2026.api.company_repository import CompanyRepository
from oxhack2026.api.evidence_mapping_schemas import (
    MappingCapability,
    MappingJob,
    MappingJobRequest,
    MappingProgress,
)
from oxhack2026.api.repository import RepositoryUnavailable
from oxhack2026.api.research_configuration import (
    ContinueRequest,
    ResearchProfile,
    ResearchSettings,
    profile_settings,
)
from oxhack2026.api.research_v2_schemas import (
    PROVIDERS,
    Capabilities,
    CompanySearchResult,
    DiscoveryRequest,
    Identity,
    Job,
    JobRequest,
    ProviderCapability,
    Report,
    ResearchEvidence,
    SourceState,
)
from oxhack2026.models.dimension_serving import DimensionModelRegistry
from oxhack2026.research.network import (
    CollectionError,
    Fetcher,
    PinnedTransport,
    Quotas,
    normalize_domain,
)
from oxhack2026.research.v2_store import V2Store
from oxhack2026.storage.artifacts import FileArtifactStore

logger = logging.getLogger(__name__)
_NAMES = {
    "website": "Company website",
    "github": "GitHub",
    "npm": "npm downloads",
    "hiring": "Official hiring",
    "hn": "Hacker News",
    "news": "GDELT news",
    "sec": "SEC disclosures",
    "companies_house": "Companies House",
}


class QueueFull(Exception):
    """The bounded discovery/research queue has reached capacity."""


class ConfirmationRequired(Exception):
    """The requested identity preview is not ready for explicit confirmation."""


@dataclass
class V2Service:
    """One process lease, two workers, eight queued tasks and shared network quotas.

    Args:
        store: Separate durable v2 metadata and raw captures.
        executor: Lifecycle-owned two-thread executor; None disables collection.
        repository: Optional explicitly selected saved publications.
        transport: Controlled transport or deterministic test double.
    """

    store: V2Store
    executor: Executor | None = None
    repository: CompanyRepository | None = None
    transport: httpx.BaseTransport = field(default_factory=PinnedTransport)
    quotas: Quotas = field(default_factory=Quotas)
    dimension_models: DimensionModelRegistry | None = None
    collection_enabled: bool = True
    mapping_enabled: bool = True
    _lock: Lock = field(default_factory=Lock)
    process_started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def capabilities(self) -> Capabilities:
        """Read configuration and local executable presence without vendor requests."""
        from oxhack2026.research.registry import registry_mapping_path

        browser = False
        if (
            os.environ.get("SIGNALSHIFT_RESEARCH_BROWSER") == "1"
            and importlib.util.find_spec("playwright") is not None
        ):
            from oxhack2026.research.browser import browser_available

            browser = browser_available()
        providers = tuple(
            ProviderCapability(
                provider=provider,
                available=provider not in {"sec", "companies_house"}
                or bool(
                    registry_mapping_path().is_file()
                    and os.environ.get(
                        "SEC_USER_AGENT"
                        if provider == "sec"
                        else "COMPANIES_HOUSE_API_KEY"
                    )
                ),
                reason="Requires verified official account links"
                if provider in {"github", "npm", "hiring"}
                else "Requires a reviewed entity mapping and provider configuration"
                if provider in {"sec", "companies_house"}
                else None,
            )
            for provider in PROVIDERS
        )
        return Capabilities(
            profiles=tuple(
                self._settings(name) for name in ("fast", "thorough", "deep")
            ),
            process_started_at=self.process_started_at,
            runtime_revision=os.environ.get("SIGNALSHIFT_RUNTIME_REVISION"),
            storage_available=self.store.root.is_dir(),
            collection_enabled=self.executor is not None and self.collection_enabled,
            worker_available=self.executor is not None,
            browser_available=browser,
            providers=providers,
            mapping=self.mapping_capability(),
        )

    def mapping_capability(self) -> MappingCapability:
        """Read mapping configuration and optional SDK presence without API calls."""
        from oxhack2026.explanations.config import (
            DEFAULT_MODEL,
            gemini_api_key,
            mapping_mode,
        )

        model = os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        if "-live" in model:
            installed = importlib.util.find_spec("websockets") is not None
        else:
            installed = importlib.util.find_spec("google") is not None
            installed = (
                installed and importlib.util.find_spec("google.genai") is not None
            )
        available = bool(gemini_api_key()) and installed
        return MappingCapability(
            enabled=self.executor is not None and self.mapping_enabled,
            mode=mapping_mode(),
            gemini_available=available,
            reason=None
            if available
            else "Gemini credentials or optional SDK unavailable",
        )

    def _capacity(self) -> None:
        if self.executor is None:
            raise RepositoryUnavailable
        active = sum(job.state in {"queued", "running"} for job in self.store.jobs())
        active += sum(
            identity.state in {"queued", "running"}
            for identity in self.store.identities()
        )
        active += sum(
            job.progress.state in {"pending", "running"}
            for job in self.store.mapping_jobs()
        )
        if active >= 10:
            raise QueueFull

    def search(self, query: str) -> CompanySearchResult:
        """Retrieve bounded name/domain candidates before identity confirmation.

        Args:
            query: User-supplied company name or HTTPS URL.
        Returns:
            Source-backed candidate websites or an actionable unavailable state.
        Raises:
            RepositoryUnavailable: Research collection is disabled.
            ValueError: The name or URL is invalid.
        """
        from oxhack2026.research.company_search import company_search

        if self.executor is None or not self.collection_enabled:
            raise RepositoryUnavailable
        return company_search(query)

    def discover(self, request: DiscoveryRequest) -> Identity:
        """Queue bounded discovery; invalid URLs fail before any network access.

        Raises:
            ValueError: Invalid input or saved context does not match the input domain.
            QueueFull: Ten tasks already occupy active/queued capacity.
            RepositoryUnavailable: Worker or optional saved context unavailable.
        """
        if not self.collection_enabled:
            raise RepositoryUnavailable
        domain = normalize_domain(request.domain)
        saved = None
        if request.company_id and request.assessment_publication_id:
            if self.repository is None:
                raise RepositoryUnavailable
            saved = self.repository.company(
                request.assessment_publication_id, request.company_id
            )
            if normalize_domain(saved.company.website_url or "") != domain:
                message = "Saved context domain does not match the requested domain"
                raise ValueError(message)
        with self._lock:
            self._capacity()
            identity = Identity(
                identity_id=uuid4().hex,
                request=request,
                state="queued",
                requested_at=datetime.now(UTC),
                requested_domain=domain,
                canonical_domain=domain,
                company_name=domain,
                saved_context=saved,
            )
            self.store.save_identity(identity)
            if self.executor is None:
                raise RepositoryUnavailable
            try:
                self.executor.submit(self.run_discovery, identity.identity_id)
            except RuntimeError as error:
                self.store.save_identity(
                    identity.model_copy(
                        update={
                            "state": "failed",
                            "finished_at": datetime.now(UTC),
                            "limitations": ("worker_unavailable",),
                        }
                    )
                )
                raise RepositoryUnavailable from error
            return identity

    def _settings(self, profile: ResearchProfile) -> ResearchSettings:
        from oxhack2026.explanations.config import DEFAULT_MODEL, mapping_mode

        settings = profile_settings(profile)
        return settings.model_copy(
            update={
                "model": os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL,
                "mapping_mode": mapping_mode(),
            }
        )

    def _fetcher(self, settings: ResearchSettings | None = None) -> Fetcher:
        fetcher = Fetcher(
            FileArtifactStore(self.store.root), self.quotas, self.transport
        )
        if settings:
            fetcher.deadline = time.monotonic() + settings.deadline_seconds * 0.7
            fetcher.max_requests = settings.requests
            fetcher.max_bytes = settings.capture_bytes
        return fetcher

    def run_discovery(self, identity_id: str) -> None:
        """Read one homepage plus two official identity pages; retain redirect
        conflicts."""
        from oxhack2026.research.extraction import company_links, parse_page

        identity = self.store.identity(identity_id)
        identity = identity.model_copy(update={"state": "running"})
        self.store.save_identity(identity)
        fetcher = self._fetcher()
        import time

        fetcher.deadline = time.monotonic() + 45
        evidence: list[ResearchEvidence] = []
        links: set[str] = set()
        conflicts: list[str] = []
        limitations: list[str] = []
        name = identity.company_name
        domain = identity.canonical_domain
        state = "ready"
        try:
            capture, content = fetcher.fetch(f"https://{domain}/")
            domain = normalize_domain(capture.final_url)
            if domain != identity.requested_domain:
                conflicts.append(
                    f"Homepage redirected from {identity.requested_domain} "
                    f"to {domain}; "
                    "confirm this destination explicitly."
                )
            page = parse_page(capture, content)
            name = page.name or domain
            if (
                identity.saved_context
                and identity.saved_context.company.display_name.casefold()
                != name.casefold()
            ):
                conflicts.append(
                    "Saved context name differs from the fresh website name; "
                    "the association requires review."
                )
            evidence.extend(page.evidence)
            links.update(page.links)
            if len(set(page.organizations)) > 1:
                conflicts.append(
                    "Multiple Organization names appear in homepage structured data."
                )
            for link in company_links(page.links, domain)[:2]:
                try:
                    extra, body = fetcher.fetch(link)
                    if normalize_domain(extra.final_url) != domain:
                        limitations.append(
                            "Identity page redirected to an unconfirmed domain."
                        )
                        continue
                    parsed = parse_page(extra, body)
                    evidence.extend(parsed.evidence[:2])
                    links.update(parsed.links)
                except CollectionError as error:
                    logger.error("Identity supporting page unavailable: %s", str(error))  # noqa: TRY400
                    limitations.append(str(error))
            if page.needs_browser:
                limitations.append(
                    "Homepage has limited static content; collection may "
                    "require the local browser."
                )
        except CollectionError as error:
            logger.error("Research identity discovery unavailable: %s", str(error))  # noqa: TRY400
            limitations.append(str(error))
            # API collectors may still have useful evidence for an unavailable website.
            limitations.append(
                "Website unavailable; identity name is unverified. Domain"
                " ownership does not establish a legal entity."
            )
        except (OSError, ValueError) as error:
            logger.error(  # noqa: TRY400
                "Research discovery persistence or parsing failed: %s",
                type(error).__name__,
            )
            state = "failed"
            limitations.append("discovery_storage_or_parser_failure")
        self.store.save_identity(
            identity.model_copy(
                update={
                    "state": state,
                    "finished_at": datetime.now(UTC),
                    "canonical_domain": domain,
                    "company_name": name,
                    "evidence": tuple(evidence),
                    "captures": tuple(fetcher.captures),
                    "official_links": tuple(sorted(links)),
                    "conflicts": tuple(conflicts),
                    "limitations": tuple(limitations),
                }
            )
        )

    def create(self, request: JobRequest, resume_from: Job | None = None) -> Job:
        """Coalesce active work for a confirmed canonical domain; refresh terminal work.

        Raises:
            ConfirmationRequired: Discovery has not completed.
            KeyError: Identity is absent.
            QueueFull: Worker queue is full.
            RepositoryUnavailable: Collection is disabled.
        """
        if not self.collection_enabled:
            raise RepositoryUnavailable
        identity = self.store.identity(request.identity_id)
        if identity.state != "ready":
            raise ConfirmationRequired
        with self._lock:
            for previous in self.store.jobs():
                if previous.state in {"queued", "running"}:
                    known = self.store.identity(previous.identity_id)
                    if (
                        previous.settings == self._settings(request.profile)
                        and previous.derived_from_report_id
                        == (resume_from.report_id if resume_from else None)
                        and known.canonical_domain == identity.canonical_domain
                        and known.saved_context == identity.saved_context
                    ):
                        return previous
            self._capacity()
            job = Job(
                job_id=uuid4().hex,
                identity_id=identity.identity_id,
                settings=self._settings(request.profile),
                derived_from_report_id=resume_from.report_id if resume_from else None,
                requested_at=datetime.now(UTC),
                sources=tuple(
                    SourceState(provider=provider, name=_NAMES[provider])
                    for provider in PROVIDERS
                ),
                mapping=MappingProgress() if self.mapping_enabled else None,
            )
            if resume_from:
                job = job.model_copy(
                    update={"sources": self._resume_sources(resume_from)}
                )
            self.store.save_job(job)
            if self.executor is None:
                raise RepositoryUnavailable
            try:
                self.executor.submit(self.run, job.job_id)
            except RuntimeError as error:
                self.store.save_job(
                    job.model_copy(
                        update={
                            "state": "failed",
                            "finished_at": datetime.now(UTC),
                            "reason_codes": ("worker_unavailable",),
                            "sources": tuple(
                                source.model_copy(
                                    update={
                                        "state": "failed",
                                        "reason_codes": ("worker_unavailable",),
                                        "finished_at": datetime.now(UTC),
                                    }
                                )
                                for source in job.sources
                            ),
                        }
                    )
                )
                raise RepositoryUnavailable from error
            return job

    def continue_job(self, job_id: str, request: ContinueRequest) -> Job:
        """Queue remaining terminal work without changing its report.

        Args:
            job_id: Exact previous job with durable source or interpretation work.
            request: New bounded research depth.
        Returns:
            A new or coalesced continuation job.
        Raises:
            ValueError: Work is active or no usable continuation checkpoint exists.
            KeyError: Previous job is absent.
            RepositoryUnavailable: Collection is disabled.
        """
        previous = self.store.job(job_id)
        pending = any(
            source.details and (source.details.frontier or source.details.cursor)
            for source in previous.sources
        )
        if previous.state not in {"completed", "partial"} or not previous.report_id:
            message = "Continue requires a terminal useful research job"
            raise ValueError(message)
        if not pending and not (
            previous.mapping and previous.mapping.state == "partial"
        ):
            message = "No continuation checkpoint; refresh research instead"
            raise ValueError(message)
        return self.create(
            JobRequest(
                identity_id=previous.identity_id,
                identity_confirmed=True,
                profile=request.profile,
            ),
            previous,
        )

    def _resume_sources(self, previous: Job) -> tuple[SourceState, ...]:
        states = []
        for source in previous.sources:
            details = source.details
            updates: dict[str, object] = {}
            if details:
                details = details.model_copy(
                    update={
                        "retained_capture_ids": tuple(
                            c.capture_id for c in source.captures
                        ),
                    }
                )
                updates["details"] = details
                if details.frontier or details.cursor:
                    updates.update(state="pending", started_at=None, finished_at=None)
            states.append(source.model_copy(update=updates))
        return tuple(states)

    def _finish(self, job: Job, identity: Identity) -> None:
        from oxhack2026.research.composition import compose

        useful = any(
            source.evidence or source.observations or source.events
            for source in job.sources
        )
        report_id = None
        state = "failed"
        if useful:
            report = compose(job, identity, self.dimension_models).model_copy(
                update={
                    "settings": job.settings,
                    "derived_from_report_id": job.derived_from_report_id,
                }
            )
            if self.mapping_enabled:
                report = self._map_report(job.job_id, report)
            self.store.publish(report)
            report_id = report.report_id
            state = (
                "partial"
                if any(source.state in {"partial", "failed"} for source in job.sources)
                or (report.mapping and report.mapping.state == "partial")
                else "completed"
            )
        self.store.save_job(
            Job.model_validate(
                {
                    **job.model_dump(),
                    "mapping": self.store.job(job.job_id).mapping,
                    "state": state,
                    "report_id": report_id,
                    "finished_at": datetime.now(UTC),
                }
            )
        )

    def _map_report(self, job_id: str, report: Report) -> Report:
        from oxhack2026.research.evidence_mapping import MappingEngine

        def checkpoint(progress: MappingProgress) -> None:
            current = self.store.job(job_id)
            if current.mapping:
                progress = progress.model_copy(
                    update={
                        "started_at": current.mapping.started_at or progress.started_at,
                        "completed_batches": max(
                            current.mapping.completed_batches,
                            progress.completed_batches,
                        ),
                    }
                )
            self.store.save_job(current.model_copy(update={"mapping": progress}))

        result = MappingEngine(self.store.root, checkpoint).map(report)
        current = self.store.job(job_id)
        checkpoint(
            MappingProgress(
                state=result.mapping.state if result.mapping else "failed",
                started_at=current.mapping.started_at if current.mapping else None,
                finished_at=datetime.now(UTC),
                completed_batches=current.mapping.completed_batches
                if current.mapping
                else 0,
                reason_codes=result.mapping.reason_codes
                if result.mapping
                else ("mapping_unavailable",),
            )
        )
        return result

    def create_mapping(self, request: MappingJobRequest) -> MappingJob:
        """Queue retained-capture interpretation; coalesce equivalent active work.

        Raises:
            RepositoryUnavailable: Mapping worker is disabled.
            QueueFull: Shared research queue has no free slots.
            KeyError: Source report does not exist.
            ValueError: Report or captures fail integrity verification.
        """
        if self.executor is None or not self.mapping_enabled:
            raise RepositoryUnavailable
        source_report = self.store.report(request.source_report_id)
        settings = self._settings(
            source_report.settings.profile if source_report.settings else "thorough"
        )
        with self._lock:
            for previous in self.store.mapping_jobs():
                if (
                    previous.source_report_id == request.source_report_id
                    and previous.cache_policy == request.cache_policy
                    and previous.settings == settings
                    and previous.progress.state in {"pending", "running"}
                ):
                    return previous
            self._capacity()
            job = MappingJob(
                job_id=uuid4().hex,
                source_report_id=request.source_report_id,
                cache_policy=request.cache_policy,
                settings=settings,
                requested_at=datetime.now(UTC),
            )
            self.store.save_mapping_job(job)
            try:
                self.executor.submit(self.run_mapping, job.job_id)
            except RuntimeError as error:
                self.store.save_mapping_job(
                    job.model_copy(
                        update={
                            "progress": MappingProgress(
                                state="failed",
                                finished_at=datetime.now(UTC),
                                reason_codes=("worker_unavailable",),
                            )
                        }
                    )
                )
                raise RepositoryUnavailable from error
            return job

    def run_mapping(self, job_id: str) -> None:
        """Publish a new report from retained captures only; preserve source dates."""
        from oxhack2026.research.evidence_mapping import MappingEngine

        job = self.store.mapping_job(job_id)
        if job.progress.state not in {"pending", "running"}:
            return
        started = job.progress.started_at or datetime.now(UTC)

        def checkpoint(progress: MappingProgress) -> None:
            current = self.store.mapping_job(job_id)
            progress = progress.model_copy(
                update={
                    "started_at": current.progress.started_at or progress.started_at,
                    "completed_batches": max(
                        current.progress.completed_batches, progress.completed_batches
                    ),
                }
            )
            self.store.save_mapping_job(
                current.model_copy(update={"progress": progress})
            )

        checkpoint(
            MappingProgress(
                state="running",
                started_at=started,
                completed_batches=job.progress.completed_batches,
            )
        )
        try:
            source = self.store.report(job.source_report_id)
            report_id = uuid4().hex
            source = source.model_copy(
                update={
                    "report_id": report_id,
                    "outlook": source.outlook.model_copy(
                        update={"source_snapshot_id": report_id}
                    ),
                }
            )
            report = MappingEngine(self.store.root, checkpoint).map(
                source, job.source_report_id
            )
            self.store.publish(report)
            current = self.store.mapping_job(job_id)
            progress = MappingProgress(
                state=report.mapping.state if report.mapping else "failed",
                started_at=started,
                finished_at=datetime.now(UTC),
                completed_batches=current.progress.completed_batches,
                reason_codes=report.mapping.reason_codes if report.mapping else (),
            )
            self.store.save_mapping_job(
                current.model_copy(
                    update={"progress": progress, "report_id": report_id}
                )
            )
        except (OSError, ValueError, RuntimeError) as error:
            logger.error(  # noqa: TRY400
                "Retained evidence mapping failed: %s", type(error).__name__
            )
            checkpoint(
                MappingProgress(
                    state="failed",
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    reason_codes=("mapping_storage_or_integrity_failure",),
                )
            )

    def run(self, job_id: str) -> None:
        """Checkpoint every collector transition; independent failures preserve
        successes."""
        from oxhack2026.research.collectors import Collector

        job = self.store.job(job_id)
        job = job.model_copy(
            update={
                "state": "running",
                "started_at": job.started_at or datetime.now(UTC),
            }
        )
        self.store.save_job(job)
        identity = self.store.identity(job.identity_id)
        fetcher = self._fetcher(job.settings)
        try:
            for index, source in enumerate(job.sources):
                if source.state != "pending":
                    continue
                running = source.model_copy(
                    update={"state": "running", "started_at": datetime.now(UTC)}
                )
                states = list(job.sources)
                states[index] = running
                job = job.model_copy(update={"sources": tuple(states)})
                self.store.save_job(job)
                linked_identity = identity.model_copy(
                    update={
                        "official_links": tuple(
                            sorted(
                                set(identity.official_links)
                                | {link for item in job.sources for link in item.links}
                            )
                        ),
                    }
                )
                collector = Collector(
                    fetcher,
                    linked_identity,
                    running,
                    os.environ.get("SIGNALSHIFT_RESEARCH_BROWSER") == "1",
                )
                states[index] = collector.collect()
                job = job.model_copy(update={"sources": tuple(states)})
                self.store.save_job(job)
            self._finish(job, identity)
        except (OSError, ValueError, RuntimeError) as error:
            logger.error(  # noqa: TRY400
                "Research worker persistence or composition failed: %s",
                type(error).__name__,
            )
            self._interrupt(job, "worker_storage_or_composition_failure")

    def _interrupt(self, job: Job, reason: str) -> None:
        states = tuple(
            source.model_copy(
                update={
                    "state": "failed",
                    "finished_at": datetime.now(UTC),
                    "reason_codes": (reason,),
                }
            )
            if source.state in {"pending", "running"}
            else source
            for source in job.sources
        )
        job = job.model_copy(update={"sources": states, "reason_codes": (reason,)})
        self.store.save_job(job)
        self._finish(job, self.store.identity(job.identity_id))

    def recover(self) -> None:
        """Recover under the process lease, preserving all completed checkpoints."""
        if self.executor is None:
            return
        for identity in self.store.identities():
            if identity.state in {"queued", "running"}:
                self.store.save_identity(
                    identity.model_copy(
                        update={
                            "state": "failed",
                            "finished_at": datetime.now(UTC),
                            "limitations": ("discovery_interrupted",),
                        }
                    )
                )
        for job in self.store.jobs():
            if job.state == "queued":
                if self.collection_enabled:
                    self.executor.submit(self.run, job.job_id)
                else:
                    self._cancel_queued_collection(job)
            elif job.state == "running":
                self._interrupt(job, "worker_interrupted")
        self._recover_mappings(self.executor)

    def _recover_mappings(self, executor: Executor) -> None:
        for mapping_job in self.store.mapping_jobs():
            if mapping_job.progress.state in {"pending", "running"}:
                if self.mapping_enabled:
                    executor.submit(self.run_mapping, mapping_job.job_id)
                else:
                    self.store.save_mapping_job(
                        mapping_job.model_copy(
                            update={
                                "progress": mapping_job.progress.model_copy(
                                    update={
                                        "state": "failed",
                                        "finished_at": datetime.now(UTC),
                                        "reason_codes": (
                                            "mapping_disabled_during_recovery",
                                        ),
                                    }
                                ),
                            }
                        )
                    )

    def _cancel_queued_collection(self, job: Job) -> None:
        finished = datetime.now(UTC)
        self.store.save_job(
            job.model_copy(
                update={
                    "state": "failed",
                    "finished_at": finished,
                    "reason_codes": ("collection_disabled_during_recovery",),
                    "sources": tuple(
                        source.model_copy(
                            update={
                                "state": "failed",
                                "finished_at": finished,
                                "reason_codes": (
                                    "collection_disabled_during_recovery",
                                ),
                            }
                        )
                        for source in job.sources
                    ),
                }
            )
        )
