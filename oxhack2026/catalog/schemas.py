"""C1 identities and effective mappings; imports perform no I/O."""

import re
from datetime import datetime, timedelta
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[
    str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$", strict=True)
]
Name = Annotated[str, Field(min_length=1, max_length=256, strict=True)]
Count = Annotated[int, Field(ge=0, le=9223372036854775807, strict=True)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Ecosystem = Literal["npm", "pypi"]


def require_utc(value: datetime) -> datetime:
    """Return an aware UTC instant, rejecting absent/nonzero timezone offsets.

    Args:
        value: Timestamp to validate.
    Returns:
        The supplied UTC timestamp.
    Raises:
        ValueError: If timezone information is absent or not UTC.
    """
    if value.utcoffset() != timedelta(0):
        message = "Timestamps must be timezone-aware UTC"
        raise ValueError(message)
    return value


def public_url(value: str) -> str:
    """Validate a public HTTPS evidence URL without credentials or signed queries.

    Args:
        value: Evidence or official product URL.
    Returns:
        The unchanged URL.
    Raises:
        ValueError: If the URL is not public-safe HTTPS.
    """
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        message = "Evidence URLs require HTTPS without credentials, query or fragment"
        raise ValueError(message)
    return value


UtcInstant = Annotated[datetime, AfterValidator(require_utc)]
PublicUrl = Annotated[str, AfterValidator(public_url)]


class Contract(BaseModel):
    """Finite-valued, frozen interchange records rejecting unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class TimeWindow(Contract):
    """A nonempty half-open interval [start, end), always in UTC."""

    start: UtcInstant
    end: UtcInstant

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Return this window; raise ValueError unless start precedes end."""
        if self.start >= self.end:
            message = "Half-open windows require start < end"
            raise ValueError(message)
        return self


class Organization(Contract):
    """Company identity and family grouping, independent of product/package names."""

    organization_id: Identifier
    family_id: Identifier
    name: Name
    kind: Literal["company_backed", "community", "reference_platform"]


class Tool(Contract):
    """A product belonging to an organization, with explicit cohort rationale."""

    tool_id: Identifier
    organization_id: Identifier
    name: Name
    category: Identifier
    website_url: PublicUrl
    inclusion_reason: str
    earliest_eligibility_at: UtcInstant | None


class Package(Contract):
    """Canonical package identity; migrations create a new package record."""

    package_id: Identifier
    ecosystem: Ecosystem
    canonical_name: Annotated[str, Field(min_length=1, max_length=214)]

    @model_validator(mode="after")
    def validate_canonical_name(self) -> Self:
        """Return the package; raise ValueError for noncanonical registry names."""
        pattern = (
            r"(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*"
            if self.ecosystem == "npm"
            else r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
        )
        if not re.fullmatch(pattern, self.canonical_name) or (
            self.ecosystem == "pypi" and "--" in self.canonical_name
        ):
            message = "Package name must use canonical registry normalization"
            raise ValueError(message)
        return self


class Repository(Contract):
    """Stable GitHub numeric identity and its name in this catalogue snapshot."""

    repository_id: Annotated[int, Field(gt=0, strict=True)]
    full_name: Annotated[str, Field(pattern=r"^[^/\s]+/[^/\s]+$")]


class MappingEvidence(Contract):
    """Official evidence; collection does not prove earlier historical eligibility."""

    evidence_id: Identifier
    kind: Literal[
        "official_installation", "official_repository", "organization", "category"
    ]
    url: PublicUrl
    available_at: UtcInstant
    checked_at: UtcInstant
    assertion: str
    source_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def validate_evidence_time(self) -> Self:
        """Return evidence; raise ValueError for availability after its inspection."""
        if self.available_at > self.checked_at:
            message = "Evidence availability cannot follow its inspection"
            raise ValueError(message)
        return self


class ToolMapping(Contract):
    """Effective tool/package association and frozen organization representative."""

    mapping_id: Identifier
    tool_id: Identifier
    package_id: Identifier
    repository_id: Annotated[int, Field(gt=0, strict=True)] | None
    valid_from: UtcInstant
    valid_to: UtcInstant | None
    primary: bool
    organization_representative: bool
    verified: bool
    reviewer: Identifier
    evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_effective_mapping(self) -> Self:
        """Return the mapping; raise ValueError for invalid dates or verification."""
        if self.valid_to is not None and self.valid_from >= self.valid_to:
            message = "Effective mappings require valid_from < valid_to"
            raise ValueError(message)
        if self.organization_representative and not self.primary:
            message = "An organization representative must be a primary package"
            raise ValueError(message)
        if (self.primary or self.organization_representative) and not self.verified:
            message = "Unverified mappings cannot be primary or representative"
            raise ValueError(message)
        return self


class CatalogSnapshot(Contract):
    """Frozen normalized identities and dated mappings for one cohort definition."""

    schema_version: Literal["data-v1"] = "data-v1"
    catalog_version: Identifier
    mapping_version: Identifier
    recorded_at: UtcInstant
    cohort_kind: Literal["contemporary_catalogue", "historical_eligibility"]
    synthetic: bool
    organizations: tuple[Organization, ...]
    tools: tuple[Tool, ...]
    packages: tuple[Package, ...]
    repositories: tuple[Repository, ...]
    evidence: tuple[MappingEvidence, ...]
    mappings: tuple[ToolMapping, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        """Return the catalog; raise ValueError for duplicate/conflicting identities."""
        from oxhack2026.catalog.validation import validate_catalog

        validate_catalog(self)
        return self
