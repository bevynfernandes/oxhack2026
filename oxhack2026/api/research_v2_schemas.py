"""Standalone, provenance-preserving research contracts, additive to v1."""

import re
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field, TypeAdapter, model_validator

from oxhack2026.api.company_schemas import CompanyDetail
from oxhack2026.api.evidence_mapping_schemas import (
    MappingBundle,
    MappingCapability,
    MappingProgress,
)
from oxhack2026.api.research_schemas import Domain, JobState, ResearchRequest
from oxhack2026.api.schemas import DTO, Identifier, PublicURL, UTCDateTime, Window
from oxhack2026.models.dimension_serving import CompanyDimensionModels
from oxhack2026.models.startup_outlook import StartupOutlook
from oxhack2026.storage.contracts import ArtifactReference

_PUBLIC_URL = TypeAdapter(PublicURL)


def _event_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme == "https"
        and parsed.netloc == "news.ycombinator.com"
        and parsed.path == "/item"
        and re.fullmatch(r"id=[1-9][0-9]*", parsed.query)
        and not parsed.fragment
    ):
        return value
    return _PUBLIC_URL.validate_python(value)


EventURL = Annotated[str, Field(max_length=2048), AfterValidator(_event_url)]

Provider = Literal[
    "website", "github", "npm", "hiring", "hn", "news", "sec", "companies_house"
]
PROVIDERS: tuple[Provider, ...] = (
    "website",
    "github",
    "npm",
    "hiring",
    "hn",
    "news",
    "sec",
    "companies_house",
)


class DiscoveryRequest(DTO):
    """Domain input and optional exact saved context; no collection confirmation."""

    domain: Annotated[str, Field(min_length=4, max_length=2048)]
    assessment_publication_id: Identifier | None = None
    company_id: Identifier | None = None

    @model_validator(mode="after")
    def _paired_context(self) -> Self:
        if (self.company_id is None) != (self.assessment_publication_id is None):
            message = "Saved context requires both exact identifiers"
            raise ValueError(message)
        return self


class Capture(DTO):
    """Integrity-checked raw response; URLs omit query data and credentials."""

    capture_id: Identifier
    url: PublicURL
    final_url: PublicURL
    status_code: int
    collected_at: UTCDateTime
    artifact: ArtifactReference
    content_type: str
    parser_version: Literal["research-extract-v2"] = "research-extract-v2"
    rendered: bool = False


class ResearchEvidence(DTO):
    """Public excerpt and deterministic extraction location in a retained capture."""

    evidence_id: Identifier
    capture_id: Identifier
    url: PublicURL
    excerpt: Annotated[str, Field(max_length=4000)]
    location: str
    collected_at: UTCDateTime


class Identity(DTO):
    """Discovered brand identity; never establishes legal or account ownership."""

    identity_id: Identifier
    request: DiscoveryRequest
    state: Literal["queued", "running", "ready", "failed"]
    requested_at: UTCDateTime
    finished_at: UTCDateTime | None = None
    requested_domain: Domain
    canonical_domain: Domain
    company_name: str
    evidence: tuple[ResearchEvidence, ...] = ()
    captures: tuple[Capture, ...] = ()
    conflicts: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    official_links: tuple[PublicURL, ...] = ()
    saved_context: CompanyDetail | None = None


class JobRequest(DTO):
    """Explicit confirmation of the exact preview, including any redirect conflicts."""

    identity_id: Identifier
    identity_confirmed: Literal[True]

    @model_validator(mode="before")
    @classmethod
    def _strict_confirmation(cls, value: object) -> object:
        if isinstance(value, dict):
            ResearchRequest.validate_confirmation(value.get("identity_confirmed"))
        return value


class SourceState(DTO):
    """One collector checkpoint, including skipped and interrupted work."""

    provider: Provider
    name: str
    state: Literal[
        "pending", "running", "completed", "partial", "failed", "skipped"
    ] = "pending"
    reason_codes: tuple[str, ...] = ()
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    captures: tuple[Capture, ...] = ()
    evidence: tuple[ResearchEvidence, ...] = ()
    observations: tuple["Observation", ...] = ()
    claims: tuple["Claim", ...] = ()
    events: tuple["Event", ...] = ()
    links: tuple[PublicURL, ...] = ()


class Observation(DTO):
    """Measured proxy or explicit gap; measurement time differs from collection."""

    observation_id: Identifier
    metric_id: Identifier
    definition: str
    unit: str
    value: Annotated[float, Field(strict=True)] | None = None
    window: Window | None = None
    collected_at: UTCDateTime
    evidence_ids: tuple[Identifier, ...] = ()
    origin: Literal["fresh", "saved"] = "fresh"
    applicability: Literal["applicable", "unknown", "not_applicable"] = "applicable"
    missing_reason: str | None = None

    @model_validator(mode="after")
    def _measurement(self) -> Self:
        if (self.value is None) != (self.missing_reason is not None):
            message = "Missing measurements require an explicit reason"
            raise ValueError(message)
        if self.value is not None and not self.evidence_ids:
            message = "Measurements require supporting evidence"
            raise ValueError(message)
        if self.window and self.window.end > self.collected_at:
            message = "Measurement window cannot follow collection"
            raise ValueError(message)
        return self


class Claim(DTO):
    """Attributed statement, not a normalized financial metric."""

    claim_id: Identifier
    text: str
    category: str
    attribution: Literal["company_reported", "registry", "coverage_candidate"]
    evidence_ids: tuple[Identifier, ...]
    published_on: str | None = None
    conflicts_with: tuple[Identifier, ...] = ()


class Event(DTO):
    """Dated retrieved record; occurrence does not establish business outcomes."""

    event_id: Identifier
    kind: str
    title: str
    url: EventURL
    published_at: str | None = None
    evidence_ids: tuple[Identifier, ...]


class Job(DTO):
    """Durable multi-source work; complete collector checkpoints survive recovery."""

    schema_version: Literal["research-job-v2"] = "research-job-v2"
    job_id: Identifier
    identity_id: Identifier
    state: JobState = "queued"
    requested_at: UTCDateTime
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    report_id: Identifier | None = None
    sources: tuple[SourceState, ...]
    reason_codes: tuple[str, ...] = ()
    mapping: MappingProgress | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        terminal = self.state in {"completed", "partial", "failed"}
        if terminal != (self.finished_at is not None):
            message = "Terminal state requires a finish time"
            raise ValueError(message)
        if (self.state in {"completed", "partial"}) != (self.report_id is not None):
            message = "Useful terminal results require a report"
            raise ValueError(message)
        if tuple(source.provider for source in self.sources) != PROVIDERS:
            message = "Every collector must have exactly one ordered state"
            raise ValueError(message)
        if self.state == "running" and self.started_at is None:
            message = "Running jobs require a start time"
            raise ValueError(message)
        if self.started_at and self.started_at < self.requested_at:
            message = "Start precedes request"
            raise ValueError(message)
        if self.finished_at and self.finished_at < (
            self.started_at or self.requested_at
        ):
            message = "Finish precedes start"
            raise ValueError(message)
        return self


class Report(DTO):
    """Immutable standalone report with raw artifact lineage and null forecasts."""

    schema_version: Literal["research-report-v2"] = "research-report-v2"
    report_id: Identifier
    job_id: Identifier
    researched_at: UTCDateTime
    identity: Identity
    sources: tuple[SourceState, ...]
    observations: tuple[Observation, ...]
    claims: tuple[Claim, ...]
    events: tuple[Event, ...]
    evidence: tuple[ResearchEvidence, ...]
    captures: tuple[Capture, ...]
    outlook: StartupOutlook
    dimension_models: CompanyDimensionModels | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    limitations: tuple[str, ...]
    mapping: MappingBundle | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _references(self) -> Self:
        captures = {item.capture_id for item in self.captures}
        evidence = {item.evidence_id for item in self.evidence}
        if len(captures) != len(self.captures) or len(evidence) != len(self.evidence):
            message = "Capture and evidence identifiers must be unique"
            raise ValueError(message)
        if any(item.capture_id not in captures for item in self.evidence):
            message = "ResearchEvidence references an absent capture"
            raise ValueError(message)
        referenced: tuple[Observation | Claim | Event, ...] = (
            *self.observations,
            *self.claims,
            *self.events,
        )
        for item in referenced:
            if not set(item.evidence_ids) <= evidence:
                message = "Result references absent evidence"
                raise ValueError(message)
        if len({item.observation_id for item in self.observations}) != len(
            self.observations
        ):
            message = "Observation identifiers must be unique"
            raise ValueError(message)
        if self.mapping:
            support = {item.evidence_id: item for item in self.evidence}
            records = {
                "observation": {item.observation_id for item in self.observations},
                "claim": {item.claim_id for item in self.claims},
                "event": {item.event_id for item in self.events},
            }
            for mapped in self.mapping.records:
                if (
                    mapped.record_id not in records[mapped.record_type]
                    or not set(mapped.evidence_ids) <= evidence
                ):
                    message = "Mapping references an absent record or evidence"
                    raise ValueError(message)
                if any(
                    quote.evidence_id not in mapped.evidence_ids
                    or quote.capture_id not in captures
                    or support[quote.evidence_id].capture_id != quote.capture_id
                    or support[quote.evidence_id].excerpt != quote.exact
                    for quote in mapped.quotes
                ):
                    message = "Mapping quote references absent support"
                    raise ValueError(message)
        return self


class ProviderCapability(DTO):
    """Configuration-only provider availability; never probes a vendor."""

    provider: Provider
    available: bool
    reason: str | None = None


class Capabilities(DTO):
    """Independent storage, worker and browser availability."""

    schema_version: Literal["research-capabilities-v2"] = "research-capabilities-v2"
    storage_available: bool
    collection_enabled: bool
    worker_available: bool
    browser_available: bool
    providers: tuple[ProviderCapability, ...]
    active_jobs: int = 2
    queued_jobs: int = 8
    network_operations: int = 8
    deadline_seconds: int = 300
    request_budget: int = 120
    response_bytes: int = 4194304
    capture_bytes: int = 33554432
    mapping: MappingCapability | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
