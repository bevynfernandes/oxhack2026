"""Bounded independent public adapters; official links are required for account
matching."""

import base64
import logging
import os
import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

import orjson

from oxhack2026.api.research_configuration import (
    AccountAssociation,
    CrawlTarget,
    ResearchSettings,
    SourceDetails,
    profile_settings,
)
from oxhack2026.api.research_discovery import SearchDiscovery
from oxhack2026.api.research_v2_schemas import (
    Capture,
    Claim,
    Event,
    Identity,
    Observation,
    ResearchEvidence,
    SourceState,
)
from oxhack2026.api.schemas import Window
from oxhack2026.models.financial_inference import CashFlowResearchEstimate
from oxhack2026.research.extraction import Page, company_links, evidence, parse_page
from oxhack2026.research.frontier import (
    NPM_ASSOCIATION_VERIFIED,
    crawl_family,
    official_host,
    source_issue,
)
from oxhack2026.research.network import CollectionError, Fetcher, public_url

logger = logging.getLogger(__name__)


def _news_domain_matches(page: Page, domain: str) -> bool:
    if any(
        (urlsplit(url).hostname or "").removeprefix("www.") == domain
        for url in page.links
    ):
        return True
    return (
        re.search(
            rf"(?<![\w.-])(?:www\.)?{re.escape(domain)}(?![\w.-])",
            page.text,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _package_repository_matches(metadata: object, name: str, api_url: str) -> bool:
    if not isinstance(metadata, dict) or metadata.get("name") != name:
        return False
    repository = metadata.get("repository")
    url = repository.get("url") if isinstance(repository, dict) else repository
    if not isinstance(url, str):
        return False
    normalized = re.sub(r"^(?:git\+)?https://github\.com/|^git@github\.com:", "", url)
    normalized = normalized.removesuffix(".git").rstrip("/").casefold()
    return normalized == urlsplit(api_url).path.removeprefix("/repos/").casefold()


def _package_homepage_matches(homepage: object, domain: str) -> bool:
    """Verify a registry homepage points to the confirmed company's public host."""
    if not isinstance(homepage, str):
        return False
    try:
        host = (urlsplit(public_url(homepage)).hostname or "").removeprefix("www.")
    except CollectionError:
        logger.error("Invalid public package homepage metadata")  # noqa: TRY400
        return False
    return official_host(host, domain)


@dataclass
class Collector:
    """Accumulate successful records even if a later request fails.

    Args:
        fetcher: Job-scoped budgets and capture persistence.
        identity: Explicitly confirmed identity preview.
        source: Running source checkpoint.
        browser_enabled: Operator opted into the isolated local renderer.
    """

    fetcher: Fetcher
    identity: Identity
    source: SourceState
    browser_enabled: bool = False
    settings: ResearchSettings | None = None
    checkpoint: Callable[[SourceState], None] | None = None
    frontier: tuple[CrawlTarget, ...] = ()
    visited: set[str] = field(default_factory=set)
    accounts: list[AccountAssociation] = field(default_factory=list)
    cursor: str | None = None
    support: list[ResearchEvidence] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    links: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)
    browser_pages: int = 0
    execution_failed: bool = False
    cash_flow_research: CashFlowResearchEstimate | None = None
    discovery: SearchDiscovery | None = None
    run_id: str | None = None
    known_urls: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Restore successful source records when continuing a durable checkpoint."""
        self.support.extend(self.source.evidence)
        self.discovery = self.source.discovery
        if (
            self.source.provider != "npm"
            or NPM_ASSOCIATION_VERIFIED in self.source.reason_codes
        ):
            self.observations.extend(self.source.observations)
        self.claims.extend(self.source.claims)
        self.events.extend(self.source.events)
        self.links.update(self.source.links)
        if self.source.details:
            self.frontier = self.source.details.frontier
            self.visited.update(self.source.details.visited)
            self.accounts.extend(
                account
                for account in self.source.details.accounts
                if account.kind != "npm"
                or self.source.provider == "github"
                or NPM_ASSOCIATION_VERIFIED in self.source.reason_codes
            )
            self.cursor = self.source.details.cursor
        resumed_limits = (
            {"website_page_limit", "google_search_page_limit"}
            if self.frontier
            else set()
        )
        if self.cursor:
            resumed_limits.update(
                {
                    "hn_non_exhaustive_or_truncated",
                    "github_repository_limit",
                    "npm_package_limit",
                    "hiring_board_limit",
                }
            )
        if self.frontier or self.cursor:
            resumed_limits.update(
                {
                    "collection_deadline",
                    "request_limit",
                    "capture_size_limit",
                }
            )
        self.reasons.extend(
            reason
            for reason in self.source.reason_codes
            if reason not in resumed_limits
        )

    @property
    def limits(self) -> ResearchSettings:
        """Use snapshotted limits, retaining legacy limits for direct adapters."""
        return self.settings or profile_settings("fast")

    def _association(self, kind: str, resource: str, item: ResearchEvidence) -> None:
        association = AccountAssociation.model_validate(
            {
                "kind": kind,
                "resource": resource,
                "evidence_ids": (item.evidence_id,),
                "discovered_on": item.url,
            }
        )
        if not any(a.kind == kind and a.resource == resource for a in self.accounts):
            self.accounts.append(association)

    def _snapshot(
        self,
        state: Literal[
            "pending", "running", "completed", "partial", "failed", "skipped"
        ],
        beginning: int = 0,
    ) -> SourceState:
        issues = tuple(source_issue(code) for code in dict.fromkeys(self.reasons))
        details = SourceDetails(
            execution="failed"
            if self.execution_failed
            else "completed"
            if state == "partial"
            else state,
            applicability="unknown" if state == "skipped" else "applicable",
            scope="planned_sample"
            if self.source.provider in {"website", "news", "hiring", "google_search"}
            else "provider_window",
            coverage="limited"
            if any(i.severity != "info" for i in issues)
            else "unknown"
            if state == "skipped"
            else "complete",
            collected=len(self.support),
            outstanding=len(self.frontier) + bool(self.cursor),
            issues=issues,
            frontier=self.frontier,
            visited=tuple(sorted(self.visited)),
            cursor=self.cursor,
            accounts=tuple(self.accounts),
            retained_capture_ids=self.source.details.retained_capture_ids
            if self.source.details
            else (),
        )
        captures = {
            c.capture_id: c
            for c in (*self.source.captures, *self.fetcher.captures[beginning:])
        }
        return SourceState.model_validate(
            {
                **self.source.model_dump(),
                "state": state,
                "details": details,
                "finished_at": None if state == "running" else datetime.now(UTC),
                "reason_codes": tuple(dict.fromkeys(self.reasons)),
                "captures": tuple(captures.values()),
                "evidence": tuple(self.support),
                "observations": tuple(self.observations),
                "claims": tuple(self.claims),
                "events": tuple(self.events),
                "links": tuple(sorted(self.links)),
                "cash_flow_research": self.cash_flow_research,
                "discovery": self.discovery,
            }
        )

    def _save_progress(self) -> None:
        if self.checkpoint:
            self.checkpoint(self._snapshot("running"))

    def json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> tuple[object, ResearchEvidence]:
        """Fetch retained JSON and create an evidence location; propagate parse
        failures."""
        capture, content = self.fetcher.fetch(url, headers)
        value: object = orjson.loads(content)
        item = evidence(capture, content[:3000].decode(errors="replace"), "json:$")
        self.support.append(item)
        return value, item

    def metric(
        self, metric_id: str, value: float | None, item: ResearchEvidence
    ) -> None:
        """Append an evidenced platform measurement, never a success score."""
        self.observations.append(
            Observation(
                observation_id=uuid4().hex,
                metric_id=metric_id,
                definition={
                    "github_stars": (
                        "Public repository stars; developer interest, not customers."
                    ),
                    "github_open_issues": (
                        "Open issues reported by GitHub, including pull requests."
                    ),
                    "advertised_openings": (
                        "Publicly advertised positions, not headcount or "
                        "realized hiring."
                    ),
                }.get(metric_id, metric_id),
                unit="count",
                value=value,
                collected_at=item.collected_at,
                evidence_ids=(item.evidence_id,),
                missing_reason="provider_incomplete" if value is None else None,
            )
        )

    def _website_page(self, capture: Capture, content: bytes) -> Page:
        page = parse_page(capture, content)
        if not page.needs_browser:
            return page
        if not self.browser_enabled or self.browser_pages >= self.limits.browser_pages:
            self.reasons.append("browser_required_unavailable_or_budget")
            return page
        from oxhack2026.research.browser import render

        self.browser_pages += 1
        try:
            rendered, body = render(self.fetcher, capture.final_url)
            return parse_page(rendered, body)
        except CollectionError as error:
            logger.error("Browser fallback failed: %s", str(error))  # noqa: TRY400
            self.reasons.append(str(error))
            return page

    def _official_page(self, target: CrawlTarget) -> tuple[Capture, Page] | None:
        try:
            capture, content = self.fetcher.fetch(target.url)
            domain = self.identity.canonical_domain
            destination = (urlsplit(capture.final_url).hostname or "").removeprefix(
                "www."
            )
            if not official_host(destination, domain):
                self.reasons.append("unconfirmed_redirect_destination")
                return None
            page = self._website_page(capture, content)
            if page.evidence and page.evidence[0].capture_id != capture.capture_id:
                capture = next(
                    row
                    for row in reversed(self.fetcher.captures)
                    if row.capture_id == page.evidence[0].capture_id
                )
        except CollectionError as error:
            from oxhack2026.research.network import BudgetExceeded

            if isinstance(error, BudgetExceeded):
                raise
            logger.error("Website page unavailable: %s", str(error))  # noqa: TRY400
            self.reasons.append(str(error))
            return None
        else:
            return capture, page

    def _documentation_seeds(self) -> tuple[CrawlTarget, ...]:
        if self.frontier:
            return ()
        return tuple(
            CrawlTarget(url=url, depth=1)
            for url in company_links(
                self.identity.official_links,
                self.identity.canonical_domain,
            )
        )

    def _official_accounts(self, capture: Capture, page: Page) -> None:
        """Retain repository links; npm candidates require independent verification."""
        account_evidence = dict(page.account_evidence)
        for link in page.links:
            host = urlsplit(link).hostname
            if host == "github.com":
                item = account_evidence.get(link) or evidence(
                    capture, link, "link:href"
                )
                if link not in account_evidence:
                    self.support.append(item)
                kind = (
                    "github_repo"
                    if len(urlsplit(link).path.strip("/").split("/")) >= 2
                    else "github_org"
                )
                self._association(kind, link, item)

    def website(self) -> None:
        """Crawl balanced official pages within the selected profile and checkpoints."""
        domain = self.identity.canonical_domain
        queue = deque(
            self.frontier
            or (
                CrawlTarget(url=f"https://{domain}/"),
                CrawlTarget(url=f"https://{domain}/sitemap.xml", depth=1),
            )
        )
        queue.extend(self._documentation_seeds())
        seen = set(self.visited)
        families: dict[str, int] = {}
        processed = 0
        try:
            while queue and processed < self.limits.company_pages:
                target = min(
                    queue,
                    key=lambda item: (
                        families.get(crawl_family(item.url), 0),
                        item.depth,
                        0
                        if crawl_family(item.url)
                        in {"documentation", "hiring", "legal"}
                        else 1,
                        len(item.url),
                        item.url,
                    ),
                )
                queue.remove(target)
                if target.url in seen:
                    continue
                result = self._official_page(target)
                if result is None:
                    seen.add(target.url)
                    continue
                capture, page = result
                seen.add(target.url)
                processed += 1
                family = crawl_family(target.url)
                families[family] = families.get(family, 0) + 1
                self.support.extend(page.evidence)
                self.claims.extend(page.claims)
                self.events.extend(page.events)
                self.links.update(page.links)
                self._official_accounts(capture, page)
                if target.depth < 3:
                    queued = {item.url for item in queue}
                    queue.extend(
                        CrawlTarget(url=link, depth=target.depth + 1)
                        for link in company_links(page.links, domain)
                        if link not in seen and link not in queued
                    )
                if len(queue) > 2000:
                    queue = deque(
                        sorted(queue, key=lambda t: (t.depth, len(t.url), t.url))[:2000]
                    )
                    self.reasons.append("website_frontier_limit")
                self.frontier = tuple(queue)
                self.visited = seen
                self._save_progress()
        except CollectionError as error:
            logger.error("Website collection interrupted: %s", str(error))  # noqa: TRY400
            queue.appendleft(target)
            self.reasons.append(str(error))
        finally:
            self.frontier = tuple(queue)
            self.visited = seen
        if queue:
            self.reasons.append("website_page_limit")

    def _organization_repositories(
        self,
        organizations: set[str],
        headers: dict[str, str] | None,
    ) -> list[str]:
        discovered: list[str] = []
        for organization in sorted(organizations)[:2]:
            for page in range(1, 3):
                payload, listing = self.json(
                    f"https://api.github.com/orgs/{organization}/repos?type=public&sort=updated&per_page=100&page={page}",
                    headers,
                )
                if not isinstance(payload, list):
                    raise CollectionError("invalid_github_organization_response")
                for row in payload:
                    if (
                        not isinstance(row, dict)
                        or row.get("fork")
                        or row.get("archived")
                    ):
                        continue
                    full_name = row.get("full_name")
                    if (
                        isinstance(full_name, str)
                        and full_name.split("/")[0].casefold() == organization
                    ):
                        discovered.append(full_name)
                        self._association(
                            "github_repo", f"https://github.com/{full_name}", listing
                        )
                if len(payload) < 100:
                    break
                if page == 2:
                    self.reasons.append("github_organization_page_limit")
        return discovered

    def _repository_package(self, base: str, headers: dict[str, str] | None) -> None:
        try:
            manifest, manifest_evidence = self.json(
                f"{base}/contents/package.json", headers
            )
            if isinstance(manifest, dict) and isinstance(manifest.get("content"), str):
                package = orjson.loads(base64.b64decode(manifest["content"]))
                if isinstance(package, dict) and not package.get("private"):
                    name = package.get("name")
                    if isinstance(name, str) and re.fullmatch(
                        r"(?:@[a-z0-9_.-]+/)?[a-z0-9_.-]+", name
                    ):
                        url = f"https://www.npmjs.com/package/{name}"
                        metadata, _registry_evidence = self.json(
                            f"https://registry.npmjs.org/{quote(name, safe='')}/latest"
                        )
                        if _package_repository_matches(metadata, name, base):
                            self.links.add(url)
                            self._association("npm", url, manifest_evidence)
                        else:
                            self.reasons.append("npm_repository_association_conflict")
        except (CollectionError, orjson.JSONDecodeError, ValueError) as error:
            logger.error(  # noqa: TRY400
                "Repository package manifest unavailable: %s", type(error).__name__
            )

    def _resource_queue(self, resources: list[str]) -> list[str]:
        """Restore a provider's retained resource queue without guessing accounts."""
        if not self.cursor:
            return resources
        value = orjson.loads(self.cursor)
        if not isinstance(value, list) or not all(
            isinstance(row, str) for row in value
        ):
            raise CollectionError("invalid_provider_checkpoint")
        return value

    def _checkpoint_resources(self, remaining: list[str]) -> None:
        """Persist unprocessed resources beside successful provider evidence."""
        self.cursor = orjson.dumps(remaining).decode() if remaining else None
        self._save_progress()

    def github(self) -> None:
        """Read metadata and stable releases only for repositories linked by
        official pages."""
        organizations = {
            urlsplit(link).path.strip("/").casefold()
            for link in self.identity.official_links
            if urlsplit(link).hostname == "github.com"
            and re.fullmatch(r"/[A-Za-z0-9_.-]+/?", urlsplit(link).path)
        }
        repositories = sorted(
            {
                "/".join(urlsplit(link).path.strip("/").split("/")[:2])
                for link in self.identity.official_links
                if urlsplit(link).hostname == "github.com"
                and re.fullmatch(
                    r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", urlsplit(link).path
                )
                and (
                    not organizations
                    or urlsplit(link).path.strip("/").split("/")[0].casefold()
                    in organizations
                )
            }
        )
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        discovered = (
            []
            if self.cursor
            else self._organization_repositories(organizations, headers)
        )
        repositories = self._resource_queue(
            list(dict.fromkeys((*repositories, *discovered)))
        )
        if not repositories:
            raise CollectionError("unverified_repository_mapping")
        repository_limit = {"fast": 2, "thorough": 6, "deep": 12}[self.limits.profile]
        remaining = list(repositories)
        self._checkpoint_resources(remaining)
        for repository in repositories[:repository_limit]:
            self._github_repository(repository, headers)
            remaining.remove(repository)
            self._checkpoint_resources(remaining)
        if len(repositories) > repository_limit:
            self.reasons.append("github_repository_limit")

    def _github_repository(
        self, repository: str, headers: dict[str, str] | None
    ) -> None:
        """Collect one verified repository's metadata, package and stable releases."""
        base = f"https://api.github.com/repos/{repository}"
        value, item = self.json(base, headers)
        if not isinstance(value, dict):
            raise CollectionError("invalid_github_response")
        for key, metric_id in (
            ("stargazers_count", "github_stars"),
            ("open_issues_count", "github_open_issues"),
        ):
            count = value.get(key)
            if isinstance(count, int):
                self.metric(metric_id, count, item)
        self.links.add(f"https://github.com/{repository}")
        self._association("github_repo", f"https://github.com/{repository}", item)
        self._repository_package(base, headers)
        pushed = value.get("pushed_at")
        if isinstance(pushed, str):
            self.events.append(
                Event(
                    event_id=uuid4().hex,
                    kind="repository_push",
                    title=repository,
                    url=f"https://github.com/{repository}",
                    published_at=pushed,
                    evidence_ids=(item.evidence_id,),
                )
            )
        releases, release_evidence = self.json(f"{base}/releases?per_page=20", headers)
        if not isinstance(releases, list):
            raise CollectionError("invalid_github_releases")
        if len(releases) == 20:
            self.reasons.append("github_release_page_limit")
        self._releases(repository, releases, release_evidence)

    def _releases(
        self, repository: str, releases: list[object], item: ResearchEvidence
    ) -> None:
        for release in releases:
            if (
                not isinstance(release, dict)
                or release.get("prerelease")
                or release.get("draft")
            ):
                continue
            self.events.append(
                Event(
                    event_id=uuid4().hex,
                    kind="stable_release",
                    title=str(release.get("tag_name", "")),
                    url=public_url(
                        str(release.get("html_url", f"https://github.com/{repository}"))
                    ),
                    published_at=str(release.get("published_at") or "") or None,
                    evidence_ids=(item.evidence_id,),
                )
            )

    def _daily_downloads(
        self, rows: list[object], start: date, end: date
    ) -> dict[date, int]:
        daily: dict[date, int] = {}
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("downloads"), int):
                day = date.fromisoformat(str(row.get("day", "")))
                count = row["downloads"]
                if count < 0 or (day in daily and daily[day] != count):
                    raise CollectionError("conflicting_or_negative_npm_daily_downloads")
                if start <= day <= end:
                    daily[day] = count
        return daily

    def npm(self) -> None:
        """Measure linked packages over the latest available sixty complete daily
        buckets."""
        packages = sorted(
            {
                urlsplit(link).path.removeprefix("/package/").strip("/")
                for link in self.identity.official_links
                if urlsplit(link).hostname in {"npmjs.com", "www.npmjs.com"}
                and urlsplit(link).path.startswith("/package/")
            }
        )
        packages = self._resource_queue(packages)
        if not packages:
            raise CollectionError("unverified_package_mapping")
        limit = {"fast": 2, "thorough": 6, "deep": 12}[self.limits.profile]
        remaining = list(packages)
        self._checkpoint_resources(remaining)
        verified = 0
        for package in packages[:limit]:
            if self._verified_package(package):
                self._npm_package(package)
                self.reasons.append(NPM_ASSOCIATION_VERIFIED)
                verified += 1
            else:
                self.reasons.append("unverified_package_ownership")
            remaining.remove(package)
            self._checkpoint_resources(remaining)
        if not verified:
            raise CollectionError("unverified_package_mapping")
        if len(packages) > {"fast": 2, "thorough": 6, "deep": 12}[self.limits.profile]:
            self.reasons.append("npm_package_limit")

    def _verified_package(self, package: str) -> bool:
        """Require a reciprocal company homepage or verified repository manifest."""
        metadata, registry = self.json(
            f"https://registry.npmjs.org/{quote(package, safe='')}/latest"
        )
        if not isinstance(metadata, dict) or metadata.get("name") != package:
            return False
        if _package_homepage_matches(
            metadata.get("homepage"), self.identity.canonical_domain
        ):
            self._association(
                "npm", f"https://www.npmjs.com/package/{package}", registry
            )
            return True
        for link in self.identity.official_links:
            parsed = urlsplit(link)
            if parsed.hostname != "github.com" or not re.fullmatch(
                r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", parsed.path
            ):
                continue
            base = f"https://api.github.com/repos/{parsed.path.strip('/')}"
            if not _package_repository_matches(metadata, package, base):
                continue
            token = os.environ.get("GITHUB_TOKEN", "")
            manifest, _ = self.json(
                f"{base}/contents/package.json",
                {"Authorization": f"Bearer {token}"} if token else None,
            )
            if not isinstance(manifest, dict) or not isinstance(
                manifest.get("content"), str
            ):
                continue
            payload = orjson.loads(base64.b64decode(manifest["content"]))
            if (
                isinstance(payload, dict)
                and payload.get("name") == package
                and not payload.get("private")
            ):
                self._association(
                    "npm", f"https://www.npmjs.com/package/{package}", registry
                )
                return True
        return False

    def _npm_package(self, package: str) -> None:
        """Retain adjacent complete windows for an independently verified package."""
        today = datetime.now(UTC).date()
        start, end = today - timedelta(days=65), today - timedelta(days=1)
        data, item = self.json(
            f"https://api.npmjs.org/downloads/range/{start}:{end}/"
            f"{quote(package, safe='')}"
        )
        if not isinstance(data, dict) or not isinstance(data.get("downloads"), list):
            raise CollectionError("invalid_npm_response")
        daily = self._daily_downloads(data["downloads"], start, end)
        latest = max(daily) if daily else end
        days = [latest - timedelta(days=index) for index in range(59, -1, -1)]
        for offset, label in ((0, "previous"), (30, "latest")):
            window_days = days[offset : offset + 30]
            complete = all(day in daily for day in window_days)
            if not complete:
                self.reasons.append("incomplete_npm_daily_window")
            self.observations.append(
                Observation(
                    observation_id=uuid4().hex,
                    metric_id=f"npm_downloads_{label}_30d",
                    definition=(
                        f"Daily npm downloads for {package}; "
                        "package adoption proxy, not users."
                    ),
                    unit="downloads",
                    value=sum(daily[day] for day in window_days) if complete else None,
                    window=Window(
                        start=datetime.combine(
                            window_days[0], datetime.min.time(), UTC
                        ),
                        end=datetime.combine(
                            window_days[-1] + timedelta(days=1),
                            datetime.min.time(),
                            UTC,
                        ),
                    ),
                    collected_at=item.collected_at,
                    evidence_ids=(item.evidence_id,),
                    missing_reason=None if complete else "incomplete_daily_window",
                )
            )

    def _hn_title_evidence(
        self, title: str, index: int, fallback: ResearchEvidence
    ) -> ResearchEvidence:
        if not title:
            return fallback
        item = evidence(self.fetcher.captures[-1], title, f"json:$.hits[{index}].title")
        self.support.append(item)
        return item

    def hn(self) -> None:
        """Collect exact-domain records with durable provider-window pagination."""
        from oxhack2026.research.hn import collect_hn

        collect_hn(self)

    def hiring(self) -> None:
        """Follow linked careers pages and collect verified public postings."""
        from oxhack2026.research.hiring import collect_hiring

        collect_hiring(self)

    def news(self) -> None:
        """Discover news candidates within the profile and retain company matching."""
        query = urlencode(
            {
                "query": f'"{self.identity.canonical_domain}"',
                "mode": "artlist",
                "format": "json",
                "maxrecords": 20,
                "timespan": "3months",
            }
        )
        data, item = self.json(f"https://api.gdeltproject.org/api/v2/doc/doc?{query}")
        articles = data.get("articles", []) if isinstance(data, dict) else []
        if not isinstance(articles, list):
            raise CollectionError("invalid_news_response")
        for article in articles[: self.limits.article_pages]:
            if not isinstance(article, dict):
                continue
            try:
                link = public_url(str(article.get("url", "")))
                capture, content = self.fetcher.fetch(link)
                page = parse_page(capture, content)
                self.support.extend(page.evidence)
                matched = _news_domain_matches(page, self.identity.canonical_domain)
                if not matched:
                    self.reasons.append("news_unmatched_candidates")
                self.events.append(
                    Event(
                        event_id=uuid4().hex,
                        kind="news_domain_matched"
                        if matched
                        else "news_unverified_candidate",
                        title=str(article.get("title") or ""),
                        url=link,
                        published_at=str(article.get("seendate") or "") or None,
                        evidence_ids=(item.evidence_id, page.evidence[0].evidence_id),
                    )
                )
            except CollectionError as error:
                logger.error("News article collection failed: %s", str(error))  # noqa: TRY400
                self.reasons.append(str(error))
        if len(articles) > self.limits.article_pages:
            self.reasons.append("news_article_limit")

    def registry(self) -> None:
        """Collect only explicitly reviewed exact-domain registry mappings from
        local config."""
        from oxhack2026.research.registry import collect_registry

        collect_registry(self)

    def google_search(self) -> None:
        """Discover public pages separately from captured-evidence interpretation."""
        from oxhack2026.research.search import collect_search

        collect_search(self)

    def collect(self) -> SourceState:
        """Run one adapter, retaining successful captures and records on
        independent failure."""
        self.execution_failed = False
        beginning = len(self.fetcher.captures)
        state: Literal["completed", "partial", "failed", "skipped"] = "completed"
        try:
            adapter = (
                self.registry
                if self.source.provider in {"sec", "companies_house"}
                else getattr(self, self.source.provider)
            )
            adapter()
        except (CollectionError, orjson.JSONDecodeError, ValueError) as error:
            logger.error(  # noqa: TRY400
                "Research collector %s failed: %s",
                self.source.provider,
                type(error).__name__,
            )
            reason = (
                str(error)
                if isinstance(error, CollectionError)
                else "invalid_provider_payload"
            )
            self.reasons.append(reason)
            state = (
                "skipped"
                if reason.startswith(("unverified_", "missing_", "official_careers"))
                else "failed"
            )
        self.execution_failed = state == "failed"
        if (
            any(source_issue(code).severity != "info" for code in self.reasons)
            and state == "completed"
        ):
            state = "partial"
        if state == "failed" and (self.support or self.events or self.observations):
            state = "partial"
        return self._snapshot(state, beginning)
