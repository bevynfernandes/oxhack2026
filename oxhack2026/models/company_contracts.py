"""Separate company-outcome truth contracts; these records are never predictors."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from oxhack2026.features.company_outcomes import CompanyOutcomeId, company_horizon_end
from oxhack2026.features.definitions import require_utc
from oxhack2026.models.contracts import Contract

LabelState = Literal["observed", "immature", "unobserved", "conflicting"]
_Identifier = Annotated[str, Field(min_length=1)]


class CompanyOutcomeLabel(Contract):
    """One company/outcome's truth at an explicit, immutable evaluation vintage.

    Attributes:
        schema_version: Company-label interchange version, separate from downloads.
        company_id: Stable company identity resolved by the source catalogue.
        family_id: Ownership-family identity for grouping and leakage checks.
        source_snapshot_id: Exact source vintage supporting the label decision.
        outcome_id: Separate operating/growth, viability or financing-event target.
        decision_at: Original assessment cutoff, not the outcome publication date.
        horizon_end: Exact calendar anniversary for the chosen outcome.
        evaluated_at: UTC cutoff for the selected evaluation/source vintage.
        label_state: Observed truth, incomplete horizon, missing or conflicting facts.
        value: Strict Boolean truth only for mature observed labels; otherwise null.
        available_at: Time all label support was knowable, including full follow-up.
        evidence_ids: Source-owned immutable evidence identifiers, never predictions.
        reason_codes: Precise observed negative reasons or missing-label exclusions.

    Raises:
        ValueError: Dates, maturity, Boolean truth or provenance are contradictory.
    """

    schema_version: Literal["company-labels-v1"] = "company-labels-v1"
    company_id: _Identifier
    family_id: _Identifier
    source_snapshot_id: _Identifier
    outcome_id: CompanyOutcomeId
    decision_at: datetime
    horizon_end: datetime
    evaluated_at: datetime
    label_state: LabelState
    value: Annotated[bool, Field(strict=True)] | None = None
    available_at: datetime | None = None
    evidence_ids: tuple[_Identifier, ...] = ()
    reason_codes: tuple[_Identifier, ...] = ()

    @field_validator("decision_at", "horizon_end", "evaluated_at", "available_at")
    @classmethod
    def _validate_utc(cls, value: datetime | None) -> datetime | None:
        return require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def _validate_label(self) -> Self:
        if self.horizon_end != company_horizon_end(self.decision_at, self.outcome_id):
            message = "Company outcome horizon must match its calendar definition"
            raise ValueError(message)
        if self.evaluated_at < self.decision_at:
            message = "Evaluation vintage cannot precede its assessment decision"
            raise ValueError(message)
        immature = self.evaluated_at < self.horizon_end
        if (self.label_state == "immature") != immature:
            message = "Label state must reflect complete calendar-horizon follow-up"
            raise ValueError(message)
        observed = self.label_state == "observed"
        if observed != (self.value is not None and self.available_at is not None):
            message = "Only observed labels have both Boolean truth and availability"
            raise ValueError(message)
        if not observed and (self.value is not None or self.available_at is not None):
            message = "Undefined company outcomes must keep truth and availability null"
            raise ValueError(message)
        if observed and not self.evidence_ids:
            message = "Observed company labels require supporting source evidence"
            raise ValueError(message)
        if not observed and not self.reason_codes:
            message = "Undefined company outcomes require an explicit reason"
            raise ValueError(message)
        if self.value is False and not self.reason_codes:
            message = "Negative company labels require a precise observed reason"
            raise ValueError(message)
        if self.available_at is not None and not (
            self.horizon_end <= self.available_at <= self.evaluated_at
        ):
            message = (
                "Label availability requires complete follow-up by evaluation time"
            )
            raise ValueError(message)
        return self
