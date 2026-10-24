"""Additive research transport; numerical model policy remains model-owned."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from oxhack2026.api.company_schemas import CompanyDetail, CompanySource
from oxhack2026.api.schemas import DTO, Identifier, UTCDateTime
from oxhack2026.catalog.schemas import Sha256, TimeWindow
from oxhack2026.models.startup_outlook import StartupOutlook

Domain = Annotated[
    str,
    Field(
        min_length=4,
        max_length=253,
        pattern=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    ),
]
JobState = Literal["queued", "running", "partial", "completed", "failed"]


class ResearchRequest(DTO):
    """Exact saved identity confirmed by the user; domains are never fetched."""

    assessment_publication_id: Identifier
    company_id: Identifier
    domain: Domain
    identity_confirmed: Literal[True]

    @field_validator("identity_confirmed", mode="before")
    @classmethod
    def validate_confirmation(cls, value: object) -> object:
        """Require an explicit boolean; reject coerced strings and integers."""
        if value is not True:
            message = "Identity must be explicitly confirmed"
            raise ValueError(message)
        return value


class ResearchSourceState(DTO):
    """Actual bounded provider state, independent of model/data readiness."""

    provider: Literal["hn_algolia"] = "hn_algolia"
    state: Literal["pending", "running", "succeeded", "partial", "failed"]
    reason_codes: tuple[Identifier, ...] = ()


class ResearchJob(DTO):
    """Durable research state; terminal times and report presence are consistent.

    Raises:
        ValueError: Timestamps or completion/report state contradict the job state.
    """

    schema_version: Literal["research-job-v1"] = "research-job-v1"
    job_id: Identifier
    request: ResearchRequest
    state: JobState
    requested_at: UTCDateTime
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    sources: Annotated[
        tuple[ResearchSourceState, ...], Field(min_length=1, max_length=1)
    ]
    report_id: Identifier | None = None
    reason_codes: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def _validate_state(self) -> Self:
        terminal = self.state in {"partial", "completed", "failed"}
        expected_source = {
            "queued": "pending",
            "running": "running",
            "completed": "succeeded",
            "partial": "partial",
            "failed": "failed",
        }[self.state]
        if self.sources[0].state != expected_source:
            message = "Source state must agree with the actual job state"
            raise ValueError(message)
        if self.state == "queued" and self.started_at is not None:
            message = "Queued research cannot already have started"
            raise ValueError(message)
        if terminal != (self.finished_at is not None):
            message = "Terminal research jobs require a finish time"
            raise ValueError(message)
        if (self.state in {"partial", "completed"}) != (self.report_id is not None):
            message = "Only completed or partial jobs have a report"
            raise ValueError(message)
        if self.state == "running" and self.started_at is None:
            message = "Running research requires a start time"
            raise ValueError(message)
        if self.started_at is not None and self.started_at < self.requested_at:
            message = "Research cannot start before it was requested"
            raise ValueError(message)
        if self.finished_at is not None and self.finished_at < (
            self.started_at or self.requested_at
        ):
            message = "Research cannot finish before it started"
            raise ValueError(message)
        return self


class AttentionObservation(DTO):
    """Fresh exact-domain HN link count, outside all v1 C1 metric families.

    A missing value means a truncated query; zero is valid only for a complete
    bounded query. The count does not measure users, sentiment or success.
    """

    observation_id: Identifier
    metric_id: Literal["hn_exact_domain_story_links_30d_v1"] = (
        "hn_exact_domain_story_links_30d_v1"
    )
    company_id: Identifier
    definition: str = (
        "HN stories linking the exact confirmed domain during the declared window; "
        "not broad mentions, sentiment, users or independent endorsement."
    )
    unit: Literal["story_links"] = "story_links"
    window: TimeWindow
    window_end_exclusive: Literal[True] = True
    value: Annotated[int, Field(ge=0, strict=True)] | None
    state: Literal["observed", "missing"]
    available_at: UTCDateTime
    collected_at: UTCDateTime
    evidence_ids: tuple[Identifier, ...]
    reason_codes: tuple[Identifier, ...]

    @model_validator(mode="after")
    def _validate_measurement(self) -> Self:
        if (self.state == "observed") != (self.value is not None):
            message = "Observed attention requires a complete query count"
            raise ValueError(message)
        if self.available_at != self.collected_at:
            message = "Fresh research availability uses actual collection time"
            raise ValueError(message)
        if self.window.end > self.collected_at:
            message = "Attention window cannot follow collection"
            raise ValueError(message)
        return self


class ResearchInventory(DTO):
    """Exact saved lineage and separately identified fresh public observations."""

    inventory_id: Identifier
    company_id: Identifier
    as_of: UTCDateTime
    synthetic: StrictBool
    saved_context: CompanyDetail
    observations: tuple[AttentionObservation, ...]
    evidence: tuple[CompanySource, ...]
    capture_sha256: Sha256
    capture_byte_size: Annotated[int, Field(ge=0, le=4194304, strict=True)]


class ResearchReport(DTO):
    """Immutable report embedding the unchanged model-owned outlook payload."""

    schema_version: Literal["research-report-v1"] = "research-report-v1"
    report_id: Identifier
    job_id: Identifier
    researched_at: UTCDateTime
    source_publication_id: Identifier
    assessment_publication_id: Identifier
    inventory: ResearchInventory
    outlook: StartupOutlook
    data_version: Literal["research-inventory-v1"] = "research-inventory-v1"
    model_version: None = None
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_inventory(self) -> Self:
        inventory = self.inventory
        saved = inventory.saved_context
        if (
            inventory.company_id != saved.company.company_id
            or self.source_publication_id != saved.publication.source.snapshot_id
            or self.assessment_publication_id
            != saved.publication.assessment.publication_id
            or self.outlook.company_id != inventory.company_id
            or self.outlook.source_snapshot_id != inventory.inventory_id
            or self.outlook.as_of != inventory.as_of
            or self.outlook.synthetic != inventory.synthetic
            or inventory.synthetic != saved.publication.source.synthetic
            or self.researched_at != inventory.as_of
        ):
            message = "Research inventory identity or saved lineage disagrees"
            raise ValueError(message)
        ids = {row.observation_id for row in saved.metrics} | {
            row.observation_id for row in inventory.observations
        }
        if (
            len(ids) != len(saved.metrics) + len(inventory.observations)
            or any(row.company_id != inventory.company_id for row in saved.metrics)
            or any(
                row.company_id != inventory.company_id for row in inventory.observations
            )
        ):
            message = "Research observations must be unique and company-scoped"
            raise ValueError(message)
        evidence = (*saved.evidence, *inventory.evidence)
        support = {row.evidence_id for row in evidence}
        if len(support) != len(evidence):
            message = "Research evidence identities must be unique"
            raise ValueError(message)
        if any(not set(row.evidence_ids) <= support for row in saved.metrics) or any(
            not set(row.evidence_ids) <= support for row in inventory.observations
        ):
            message = "Research observations reference unknown evidence"
            raise ValueError(message)
        if any(
            row.collected_at != inventory.as_of or row.available_at != inventory.as_of
            for row in inventory.observations
        ) or any(
            row.access != "public"
            or row.review_state != "verified"
            or row.collected_at != inventory.as_of
            or row.available_at != inventory.as_of
            for row in inventory.evidence
        ):
            message = "Fresh research requires public verified evidence at its cutoff"
            raise ValueError(message)
        assigned = set(self.outlook.unassigned_metric_observation_ids)
        for section in self.outlook.specialists:
            assigned.update(section.metric_observation_ids)
            if not set(section.evidence_ids) <= support:
                message = "Research outlook references unknown evidence"
                raise ValueError(message)
        if assigned != ids:
            message = "Research outlook must resolve every inventory observation"
            raise ValueError(message)
        return self
