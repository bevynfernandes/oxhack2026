"""Cited research analysis and interpreter accounting, independent of prediction."""

from typing import Literal

from pydantic import Field

from oxhack2026.api.schemas import DTO, Identifier
from oxhack2026.models.startup_outlook import SpecialistGroupId


class InterpretationStatistics(DTO):
    """Actual run accounting; cached work never becomes a new provider call."""

    mode: Literal["rules", "rules_gemini"]
    model: str | None = None
    stage: Literal["preparing", "extracting", "synthesizing", "finished"] = "preparing"
    candidates: int = Field(default=0, ge=0)
    processed: int = Field(default=0, ge=0)
    deferred: int = Field(default=0, ge=0)
    batches: int = Field(default=0, ge=0)
    failed_batches: int = Field(default=0, ge=0)
    cached_batches: int = Field(default=0, ge=0)
    provider_requests: int = Field(default=0, ge=0)
    accepted_proposals: int = Field(default=0, ge=0)
    rejected_proposals: int = Field(default=0, ge=0)
    input_tokens: int | None = None
    output_tokens: int | None = None


class AnalysisStatement(DTO):
    """One finding tied to accepted source evidence; never a forecast."""

    text: str = Field(min_length=10, max_length=1000)
    group_id: SpecialistGroupId
    kind: Literal["finding", "conflict", "gap"]
    mapping_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=8)


class ResearchAnalysis(DTO):
    """Locally validated analysis or an explicit inability to generate it."""

    state: Literal["completed", "partial", "unavailable"]
    method: Literal["gemini", "rules"]
    statements: tuple[AnalysisStatement, ...] = ()
    reason_codes: tuple[str, ...] = ()
