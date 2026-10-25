"""Versioned research budgets, coverage and resumable source checkpoints."""

from typing import Literal

from pydantic import Field

from oxhack2026.api.schemas import DTO, Identifier, PublicURL

ResearchProfile = Literal["fast", "thorough", "deep"]


class ResearchSettings(DTO):
    """Resolved immutable limits and interpreter configuration for one job."""

    profile: ResearchProfile = "thorough"
    deadline_seconds: int = Field(default=600, ge=1)
    company_pages: int = Field(default=60, ge=1)
    article_pages: int = Field(default=12, ge=1)
    browser_pages: int = Field(default=6, ge=0)
    requests: int = Field(default=240, ge=1)
    capture_bytes: int = Field(default=64 * 1024 * 1024, ge=1)
    model_requests: int = Field(default=12, ge=1, le=24)
    input_reservation: int = Field(default=180_000, ge=1)
    mapping_mode: Literal["rules", "rules_gemini"] = "rules_gemini"
    model: str = "gemini-3.8-live-extended-thinking"


def profile_settings(profile: ResearchProfile) -> ResearchSettings:
    """Return profile ceilings; callers snapshot their effective model settings.

    Args:
        profile: Validated public research depth.
    Returns:
        A new settings value, independent of process environment and other jobs.
    """
    if profile == "fast":
        return ResearchSettings(
            profile=profile,
            deadline_seconds=300,
            company_pages=20,
            article_pages=6,
            browser_pages=3,
            requests=120,
            capture_bytes=32 * 1024 * 1024,
            model_requests=6,
            input_reservation=60_000,
        )
    if profile == "deep":
        return ResearchSettings(
            profile=profile,
            deadline_seconds=1200,
            company_pages=120,
            article_pages=24,
            browser_pages=12,
            requests=480,
            capture_bytes=128 * 1024 * 1024,
            model_requests=24,
            input_reservation=360_000,
        )
    return ResearchSettings()


class SourceIssue(DTO):
    """An actionable source explanation; information alone is not a failure."""

    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    remedy: str | None = None


class CrawlTarget(DTO):
    """A public page left to collect at a bounded discovery depth."""

    url: PublicURL
    depth: int = Field(default=0, ge=0, le=4)


class AccountAssociation(DTO):
    """A verified official-page association, never a fuzzy-name attachment."""

    kind: Literal["github_org", "github_repo", "npm", "hiring", "registry"]
    resource: str
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1)
    discovered_on: PublicURL


class SourceDetails(DTO):
    """Execution and coverage are independent; continuation retains actual work."""

    execution: Literal["pending", "running", "completed", "failed", "skipped"]
    applicability: Literal["applicable", "unknown", "not_applicable"] = "unknown"
    scope: Literal["planned_sample", "provider_window", "verified_entity"]
    coverage: Literal["complete", "limited", "unknown", "not_applicable"]
    collected: int = Field(default=0, ge=0)
    outstanding: int = Field(default=0, ge=0)
    issues: tuple[SourceIssue, ...] = ()
    frontier: tuple[CrawlTarget, ...] = ()
    visited: tuple[PublicURL, ...] = ()
    cursor: str | None = None
    accounts: tuple[AccountAssociation, ...] = ()
    retained_capture_ids: tuple[Identifier, ...] = ()


class ContinueRequest(DTO):
    """Explicitly spend one selected profile's budget on remaining work."""

    profile: ResearchProfile = Field(default_factory=lambda: "thorough")
    source_report_id: Identifier | None = None
