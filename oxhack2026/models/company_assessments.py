"""Source-linked company evidence assessments, separate from future outcome truth."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from oxhack2026.features.company_outcomes import (
    COMPANY_OUTCOME_IDS,
    CompanyOutcomeId,
    company_horizon_end,
)
from oxhack2026.features.definitions import require_utc
from oxhack2026.models.contracts import Contract, ForecastMode

_Identifier = Annotated[str, Field(min_length=1)]
_OUTCOMES = frozenset(COMPANY_OUTCOME_IDS)


class AssessmentStatement(Contract):
    """A deterministic fact, risk or explicitly identified evidence gap.

    Attributes:
        statement_id: Immutable identifier within one assessment.
        role: Observation, supported risk, or absence of applicable evidence.
        text: Plain source-backed description, not an unvalidated likelihood.
        evidence_ids: C1 evidence supporting a fact/risk; empty for a pure gap.
        metric_observation_ids: Exact C1 observations used in the statement.
        event_ids: Exact C1 events used in the statement.
        missing_metric_ids: Definitions whose evidence is missing or conflicting.

    Raises:
        ValueError: A fact/risk lacks evidence, or a gap lacks its missing definition.
    """

    statement_id: _Identifier
    role: Literal["observation", "risk", "evidence_gap"]
    text: _Identifier
    evidence_ids: tuple[_Identifier, ...] = ()
    metric_observation_ids: tuple[_Identifier, ...] = ()
    event_ids: tuple[_Identifier, ...] = ()
    missing_metric_ids: tuple[_Identifier, ...] = ()

    @model_validator(mode="after")
    def _validate_support(self) -> Self:
        if self.role == "evidence_gap":
            if not self.missing_metric_ids:
                message = "An evidence gap must identify its missing metric definitions"
                raise ValueError(message)
        elif not self.evidence_ids:
            message = "A company observation or risk requires source evidence"
            raise ValueError(message)
        return self


class CompanyOutcomeAssessment(Contract):
    """One prospective question explained from currently available evidence.

    Attributes:
        outcome_id: Separate versioned company outcome, never a composite score.
        horizon_end: Exact calendar horizon derived from the assessment cutoff.
        assessment_status: Evidence-only facts, or unavailable relevant evidence.
        summary: Short explanation of facts/gaps without unsupported probability.
        statement_ids: Supporting/risk/gap statements in the containing assessment.
        reason_codes: Explicit limitations or reasons relevant evidence is absent.
        probability: Always null in this evidence-only contract version. A later
            validated prediction contract requires its own model/evaluation gate.

    Raises:
        ValueError: An unavailable outcome lacks reasons, or facts lack statements.
    """

    outcome_id: CompanyOutcomeId
    horizon_end: datetime
    assessment_status: Literal["evidence_only", "unavailable"]
    summary: _Identifier
    statement_ids: tuple[_Identifier, ...] = ()
    reason_codes: tuple[_Identifier, ...] = ()
    probability: None = None

    @field_validator("horizon_end")
    @classmethod
    def _validate_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode="after")
    def _validate_status(self) -> Self:
        if self.assessment_status == "evidence_only" and not self.statement_ids:
            message = "An evidence-only assessment requires referenced statements"
            raise ValueError(message)
        if self.assessment_status == "unavailable" and not self.reason_codes:
            message = "An unavailable outcome requires explicit reasons"
            raise ValueError(message)
        return self


class CompanyAssessment(Contract):
    """Immutable company outlook without future labels or an invented success score.

    Attributes:
        schema_version: Evidence-assessment contract version.
        assessment_id: Immutable assessment identity.
        company_id: C1 company identity, reusing verified organization identity.
        family_id: Effective family at as_of, or null for unresolved ownership.
        family_reason_codes: Explicit reasons when ownership is unknown/conflicting.
        source_snapshot_id: Exact verified C1 source publication consumed.
        policy_version: Deterministic evidence interpretation policy.
        as_of: UTC evidence/measurement cutoff for this assessment.
        first_recorded_at: Actual time the immutable assessment was first recorded.
        mode: Historical reconstruction or genuinely pre-cutoff prospective record.
        outcomes: Exactly the three separate outcome sections, including unknowns.
        statements: Source-linked facts, risks and missing-definition explanations.
        synthetic: Must match the source publication; fixtures never become real data.
        limitations: Publication/cohort restrictions retained for the consumer.

    Raises:
        ValueError: Sections, references, dates or prospective provenance conflict.
    """

    schema_version: Literal["company-assessments-v1"] = "company-assessments-v1"
    assessment_id: _Identifier
    company_id: _Identifier
    family_id: _Identifier | None
    family_reason_codes: tuple[_Identifier, ...] = ()
    source_snapshot_id: _Identifier
    policy_version: _Identifier
    as_of: datetime
    first_recorded_at: datetime
    mode: ForecastMode
    outcomes: tuple[CompanyOutcomeAssessment, ...]
    statements: tuple[AssessmentStatement, ...]
    synthetic: bool
    limitations: tuple[_Identifier, ...] = ()

    @field_validator("as_of", "first_recorded_at")
    @classmethod
    def _validate_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode="after")
    def _validate_scope(self) -> Self:
        if self.family_id is None and not self.family_reason_codes:
            message = "Unresolved company family requires explicit ownership reasons"
            raise ValueError(message)
        if (
            len(self.outcomes) != 3
            or {row.outcome_id for row in self.outcomes} != _OUTCOMES
        ):
            message = "A company assessment requires each of the three outcomes once"
            raise ValueError(message)
        if self.mode == "prospective" and self.first_recorded_at >= self.as_of:
            message = "Prospective company assessments must be recorded before cutoff"
            raise ValueError(message)
        statements = {row.statement_id: row for row in self.statements}
        if len(statements) != len(self.statements):
            message = "Company assessment statement IDs must be unique"
            raise ValueError(message)
        for outcome in self.outcomes:
            if outcome.horizon_end != company_horizon_end(
                self.as_of, outcome.outcome_id
            ):
                message = "Company assessment horizon does not match its outcome cutoff"
                raise ValueError(message)
            if not set(outcome.statement_ids) <= statements.keys():
                message = "Company outcome refers to an unknown assessment statement"
                raise ValueError(message)
            has_facts = any(
                statements[key].role != "evidence_gap" for key in outcome.statement_ids
            )
            if (outcome.assessment_status == "evidence_only") != has_facts:
                message = (
                    "Evidence gaps alone cannot establish an evidence-only outlook"
                )
                raise ValueError(message)
        return self
