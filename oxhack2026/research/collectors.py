"""Bounded independent public adapters; official links are required for account
matching."""

import logging
import os
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

import orjson

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
from oxhack2026.research.documents import page_family
from oxhack2026.research.extraction import Page, company_links, evidence, parse_page
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
    support: list[ResearchEvidence] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    links: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)
    browser_pages: int = 0

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
        if not self.browser_enabled or self.browser_pages >= 3:
            self.reasons.append("browser_required_unavailable_or_budget")
            return page
        from oxhack2026.research.browser import render

        self.browser_pages += 1
        capture, content = render(self.fetcher, capture.final_url)
        return parse_page(capture, content)

    def website(self) -> None:
        """Crawl twenty relevant company pages at depth two plus linked
        feeds/sitemap."""
        domain = self.identity.canonical_domain
        queue = deque([(f"https://{domain}/", 0), (f"https://{domain}/sitemap.xml", 1)])
        seen: set[str] = set()
        families: dict[str, int] = {}
        while queue and len(seen) < 20:
            index = min(
                enumerate(queue),
                key=lambda item: families.get(page_family(item[1][0]), 0),
            )[0]
            queue.rotate(-index)
            url, depth = queue.popleft()
            queue.rotate(index)
            if url in seen:
                continue
            seen.add(url)
            family = page_family(url)
            families[family] = families.get(family, 0) + 1
            try:
                capture, content = self.fetcher.fetch(url)
                destination = (urlsplit(capture.final_url).hostname or "").removeprefix(
                    "www."
                )
                if destination != domain:
                    self.reasons.append("unconfirmed_redirect_destination")
                    continue
                page = self._website_page(capture, content)
                if page.text:
                    self.support.extend(page.evidence)
                    self.claims.extend(page.claims)
                    self.events.extend(page.events)
                self.links.update(page.links)
                if depth < 2:
                    queue.extend(
                        (link, depth + 1)
                        for link in company_links(page.links, domain)
                        if link not in seen
                    )
                    if len(queue) > 120:
                        queue = deque(list(queue)[:120])
                        self.reasons.append("website_frontier_limit")
            except CollectionError as error:
                logger.error("Website page collection failed: %s", str(error))  # noqa: TRY400
                self.reasons.append(str(error))
                if str(error) in {
                    "http_401",
                    "http_403",
                    "access_challenge_or_paywall",
                }:
                    break
        if queue:
            self.reasons.append("website_page_limit")

    def github(self) -> None:
        """Read metadata and stable releases only for repositories linked by
        official pages."""
        repositories = sorted(
            {
                "/".join(urlsplit(link).path.strip("/").split("/")[:2])
                for link in self.identity.official_links
                if urlsplit(link).hostname == "github.com"
                and re.fullmatch(
                    r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", urlsplit(link).path
                )
            }
        )
        if not repositories:
            raise CollectionError("unverified_repository_mapping")
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        for repository in repositories[:2]:
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
            releases, release_evidence = self.json(
                f"{base}/releases?per_page=20", headers
            )
            if not isinstance(releases, list):
                raise CollectionError("invalid_github_releases")
            if len(releases) == 20:
                self.reasons.append("github_release_page_limit")
            self._releases(repository, releases, release_evidence)
        if len(repositories) > 2:
            self.reasons.append("github_repository_limit")

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
        if not packages:
            raise CollectionError("unverified_package_mapping")
        today = datetime.now(UTC).date()
        start, end = today - timedelta(days=65), today - timedelta(days=1)
        for package in packages[:2]:
            data, item = self.json(
                f"https://api.npmjs.org/downloads/range/{start}:{end}/"
                f"{quote(package, safe='')}"
            )
            if not isinstance(data, dict) or not isinstance(
                data.get("downloads"), list
            ):
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
                        value=sum(daily[day] for day in window_days)
                        if complete
                        else None,
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
        if len(packages) > 2:
            self.reasons.append("npm_package_limit")

    def hn(self) -> None:
        """Retain paginated exact-domain records separately from an exhaustive-
        window count."""
        end = datetime.now(UTC)
        start = end - timedelta(days=30)
        records: dict[str, Event] = {}
        complete = False
        exhaustive = True
        items: list[ResearchEvidence] = []
        for page in range(10):
            query = urlencode(
                {
                    "query": self.identity.canonical_domain,
                    "tags": "story",
                    "hitsPerPage": 100,
                    "page": page,
                    "numericFilters": (
                        f"created_at_i>={int(start.timestamp())},"
                        f"created_at_i<{int(end.timestamp())}"
                    ),
                    "restrictSearchableAttributes": "url",
                }
            )
            data, item = self.json(
                f"https://hn.algolia.com/api/v1/search_by_date?{query}"
            )
            items.append(item)
            if not isinstance(data, dict) or not isinstance(data.get("hits"), list):
                raise CollectionError("invalid_hn_response")
            exhaustive = exhaustive and data.get("exhaustiveNbHits") is True
            for hit in data["hits"]:
                if not isinstance(hit, dict):
                    continue
                link = str(hit.get("url") or "")
                if (urlsplit(link).hostname or "").removeprefix(
                    "www."
                ).lower() != self.identity.canonical_domain:
                    continue
                identifier = str(hit.get("objectID") or "")
                published = hit.get("created_at_i")
                if (
                    not identifier.isdigit()
                    or not isinstance(published, int)
                    or not int(start.timestamp()) <= published < int(end.timestamp())
                ):
                    continue
                records[identifier] = Event(
                    event_id=f"hn-{identifier}",
                    kind="hn_exact_domain_story",
                    title=str(hit.get("title") or ""),
                    url=f"https://news.ycombinator.com/item?id={identifier}",
                    published_at=datetime.fromtimestamp(published, UTC).isoformat(),
                    evidence_ids=(item.evidence_id,),
                )
            pages = data.get("nbPages")
            if isinstance(pages, int) and page + 1 >= pages:
                complete = exhaustive
                break
        self.events.extend(records.values())
        collected = items[-1].collected_at
        for metric_id, value, missing in (
            ("hn_retrieved_exact_domain_records_30d", len(records), None),
            (
                "hn_complete_exact_domain_count_30d",
                len(records) if complete else None,
                None if complete else "non_exhaustive_or_truncated",
            ),
        ):
            self.observations.append(
                Observation(
                    observation_id=uuid4().hex,
                    metric_id=metric_id,
                    definition=(
                        "Exact-domain HN story links; retrieved records and "
                        "complete-window counts are distinct. Not users or "
                        "sentiment."
                    ),
                    unit="story_links",
                    value=value,
                    missing_reason=missing,
                    window=Window(start=start, end=end),
                    collected_at=collected,
                    evidence_ids=tuple(item.evidence_id for item in items),
                )
            )
        if not complete:
            self.reasons.append("hn_non_exhaustive_or_truncated")

    def hiring(self) -> None:
        """Read verified public ATS boards; retain official careers pages as
        evidence."""
        links = sorted(
            {
                link
                for link in self.identity.official_links
                if re.search(
                    r"career|jobs|greenhouse|lever\.co|ashbyhq", link, re.IGNORECASE
                )
            }
        )
        if not links:
            raise CollectionError("official_careers_link_unavailable")
        for link in links[:3]:
            parsed = urlsplit(link)
            parts = parsed.path.strip("/").split("/")
            board = parts[0]
            endpoint: str | None = None
            key: str | None = None
            if (
                parsed.hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"}
                and board
            ):
                endpoint, key = (
                    "https://boards-api.greenhouse.io/v1/boards/"
                    f"{quote(board, safe='')}/jobs",
                    "jobs",
                )
            elif parsed.hostname == "jobs.lever.co" and board:
                endpoint = (
                    "https://api.lever.co/v0/postings/"
                    f"{quote(board, safe='')}?mode=json"
                )
            elif parsed.hostname == "jobs.ashbyhq.com" and board:
                endpoint, key = (
                    "https://api.ashbyhq.com/posting-api/job-board/"
                    f"{quote(board, safe='')}",
                    "jobs",
                )
            if endpoint:
                data, item = self.json(endpoint)
                jobs = data.get(key) if key and isinstance(data, dict) else data
                if isinstance(jobs, list):
                    self.metric("advertised_openings", len(jobs), item)
                else:
                    self.reasons.append("unrecognized_hiring_payload")
            else:
                capture, content = self.fetcher.fetch(link)
                page = parse_page(capture, content)
                self.support.extend(page.evidence)
                self.reasons.append("careers_page_without_structured_opening_count")
        if len(links) > 3:
            self.reasons.append("hiring_board_limit")

    def news(self) -> None:
        """Discover GDELT candidates and retrieve six accessible articles for
        matching."""
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
        self.reasons.append("coverage_candidates_require_company_matching")
        for article in articles[:6]:
            if not isinstance(article, dict):
                continue
            try:
                link = public_url(str(article.get("url", "")))
                capture, content = self.fetcher.fetch(link)
                page = parse_page(capture, content)
                self.support.extend(page.evidence)
                matched = _news_domain_matches(page, self.identity.canonical_domain)
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
        if len(articles) > 6:
            self.reasons.append("news_article_limit")

    def registry(self) -> None:
        """Collect only explicitly reviewed exact-domain registry mappings from
        local config."""
        from oxhack2026.research.registry import collect_registry

        collect_registry(self)

    def collect(self) -> SourceState:
        """Run one adapter, retaining successful captures and records on
        independent failure."""
        beginning = len(self.fetcher.captures)
        state = "completed"
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
        if self.reasons and state == "completed":
            state = "partial"
        if state == "failed" and (self.support or self.events or self.observations):
            state = "partial"
        return SourceState.model_validate(
            {
                **self.source.model_dump(),
                "state": state,
                "finished_at": datetime.now(UTC),
                "reason_codes": tuple(dict.fromkeys(self.reasons)),
                "captures": tuple(self.fetcher.captures[beginning:]),
                "evidence": tuple(self.support),
                "observations": tuple(self.observations),
                "claims": tuple(self.claims),
                "events": tuple(self.events),
                "links": tuple(sorted(self.links)),
            }
        )
