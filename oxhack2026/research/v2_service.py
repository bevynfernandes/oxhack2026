"""Bounded on-demand identity discovery and checkpointed multi-source workers."""

import importlib.util
import logging
import os
from concurrent.futures import Executor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

import httpx

from oxhack2026.api.company_repository import CompanyRepository
from oxhack2026.api.repository import RepositoryUnavailable
from oxhack2026.api.research_v2_schemas import (
    PROVIDERS,
    Capabilities,
    DiscoveryRequest,
    Identity,
    Job,
    JobRequest,
    ProviderCapability,
    ResearchEvidence,
    SourceState,
)
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
    _lock: Lock = field(default_factory=Lock)

    def capabilities(self) -> Capabilities:
        """Read configuration and local executable presence without vendor requests."""
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
                    os.environ.get("SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS")
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
            storage_available=self.store.root.is_dir(),
            collection_enabled=self.executor is not None,
            worker_available=self.executor is not None,
            browser_available=browser,
            providers=providers,
        )

    def _capacity(self) -> None:
        if self.executor is None:
            raise RepositoryUnavailable
        active = sum(job.state in {"queued", "running"} for job in self.store.jobs())
        active += sum(
            identity.state in {"queued", "running"}
            for identity in self.store.identities()
        )
        if active >= 10:
            raise QueueFull

    def discover(self, request: DiscoveryRequest) -> Identity:
        """Queue bounded discovery; invalid URLs fail before any network access.

        Raises:
            ValueError: Invalid input or saved context does not match the input domain.
            QueueFull: Ten tasks already occupy active/queued capacity.
            RepositoryUnavailable: Worker or optional saved context unavailable.
        """
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

    def _fetcher(self) -> Fetcher:
        return Fetcher(FileArtifactStore(self.store.root), self.quotas, self.transport)

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

    def create(self, request: JobRequest) -> Job:
        """Coalesce active work for a confirmed canonical domain; refresh terminal work.

        Raises:
            ConfirmationRequired: Discovery has not completed.
            KeyError: Identity is absent.
            QueueFull: Worker queue is full.
            RepositoryUnavailable: Collection is disabled.
        """
        identity = self.store.identity(request.identity_id)
        if identity.state != "ready":
            raise ConfirmationRequired
        with self._lock:
            for previous in self.store.jobs():
                if previous.state in {"queued", "running"}:
                    known = self.store.identity(previous.identity_id)
                    if (
                        known.canonical_domain == identity.canonical_domain
                        and known.saved_context == identity.saved_context
                    ):
                        return previous
            self._capacity()
            job = Job(
                job_id=uuid4().hex,
                identity_id=identity.identity_id,
                requested_at=datetime.now(UTC),
                sources=tuple(
                    SourceState(provider=provider, name=_NAMES[provider])
                    for provider in PROVIDERS
                ),
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

    def _finish(self, job: Job, identity: Identity) -> None:
        from oxhack2026.research.composition import compose

        useful = any(
            source.evidence or source.observations or source.events
            for source in job.sources
        )
        report_id = None
        state = "failed"
        if useful:
            report = compose(job, identity)
            self.store.publish(report)
            report_id = report.report_id
            state = (
                "partial"
                if any(source.state in {"partial", "failed"} for source in job.sources)
                else "completed"
            )
        self.store.save_job(
            Job.model_validate(
                {
                    **job.model_dump(),
                    "state": state,
                    "report_id": report_id,
                    "finished_at": datetime.now(UTC),
                }
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
        fetcher = self._fetcher()
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
                self.executor.submit(self.run, job.job_id)
            elif job.state == "running":
                self._interrupt(job, "worker_interrupted")
