"""Reconstructed public SDK and software-issuer dimension datasets."""

from bisect import bisect_right
from calendar import monthrange
from collections import Counter
from datetime import date, timedelta
from math import asinh, log, log1p
from pathlib import Path

import orjson
import polars as pl
from pydantic import BaseModel

from oxhack2026.models.public_dimensions import DimensionRow
from oxhack2026.models.startup_outlook import SpecialistGroupId

_START = date(2022, 1, 1)
_END = date(2025, 12, 31)


class SdkSubject(BaseModel):
    """One predeclared public package and peer segment.

    Attributes:
        subject_id: Public SDK identity, not an audited legal company.
        package: Exact npm name.
        segment: Frozen technical peer group.
    """

    subject_id: str
    package: str
    segment: str


class SdkCohort(BaseModel):
    """SDK sampling declaration.

    Attributes:
        subjects: Subjects declared before their measured performance.
    """

    subjects: tuple[SdkSubject, ...]


class DailyDownload(BaseModel):
    """One npm daily count.

    Attributes:
        day: UTC day.
        downloads: Observed nonnegative count.
    """

    day: date
    downloads: int


class DownloadCapture(BaseModel):
    """Exact public npm response.

    Attributes:
        package: Source-owned package identity.
        downloads: Daily observations; absent days are never filled with zero.
    """

    package: str
    downloads: tuple[DailyDownload, ...]


class ReleaseCapture(BaseModel):
    """Fields required by the production stable-release filter.

    Attributes:
        id: Stable release identity for deduplication.
        draft: Whether the release is unpublished.
        prerelease: Whether the release is a prerelease.
        published_at: Publication timestamp; missing releases are ineligible.
    """

    id: int
    draft: bool
    prerelease: bool
    published_at: str | None


def _download_history(directory: Path, package: str) -> tuple[int, ...] | None:
    files = [directory / f"downloads-{year}.json" for year in range(2022, 2026)]
    if not all(path.is_file() for path in files):
        return None
    counts: dict[date, int] = {}
    for path in files:
        capture = DownloadCapture.model_validate_json(path.read_bytes())
        if capture.package != package:
            message = "SDK capture package differs from declared cohort identity"
            raise ValueError(message)
        for row in capture.downloads:
            if row.downloads < 0 or row.day in counts:
                message = "SDK histories require unique, nonnegative daily observations"
                raise ValueError(message)
            counts[row.day] = row.downloads
    days = (_END - _START).days + 1
    if set(counts) != {_START + timedelta(days=index) for index in range(days)}:
        return None
    return tuple(counts[_START + timedelta(days=index)] for index in range(days))


def _release_dates(directory: Path) -> tuple[date, ...] | None:
    files = sorted(
        (
            path
            for path in directory.glob("releases-*.json")
            if path.stem.removeprefix("releases-").isdigit()
        ),
        key=lambda path: int(path.stem.split("-")[-1]),
    )
    if not files:
        return None
    dates: dict[int, date] = {}
    complete = False
    for expected_page, path in enumerate(files, start=1):
        if path.stem != f"releases-{expected_page}":
            return None
        payload = orjson.loads(path.read_bytes())
        for value in payload:
            release = ReleaseCapture.model_validate(value)
            if not release.draft and not release.prerelease and release.published_at:
                dates[release.id] = date.fromisoformat(release.published_at[:10])
        if len(payload) < 100:
            complete = True
            break
    return tuple(sorted(dates.values())) if complete else None


def build_sdk_datasets(
    root: Path, cohort_path: Path
) -> tuple[dict[SpecialistGroupId, tuple[DimensionRow, ...]], dict[str, object]]:
    """Build measured future SDK demand, peer share and stable-release outcomes.

    Args:
        root: Retained raw-capture root, containing sdk/<subject>/ directories.
        cohort_path: Predeclared public SDK cohort and technical peer segments.
    Returns:
        Three reconstructed dimension datasets and explicit coverage/exclusion counts.
        All windows are disjoint; missing histories and incomplete releases abstain.
    Raises:
        ValueError: Captures conflict with package identities or daily-count rules.
        OSError: Retained captures cannot be read.
    """
    import numpy as np

    cohort = SdkCohort.model_validate_json(cohort_path.read_bytes())
    histories = {
        subject.subject_id: history
        for subject in cohort.subjects
        if (
            history := _download_history(
                root / "sdk" / subject.subject_id, subject.package
            )
        )
        is not None
    }
    prefix = {
        key: np.concatenate(([0], np.cumsum(values, dtype=np.int64)))
        for key, values in histories.items()
    }
    segments: dict[str, list[str]] = {}
    for subject in cohort.subjects:
        if subject.subject_id in histories:
            segments.setdefault(subject.segment, []).append(subject.subject_id)
    peer_prefix = {
        name: np.sum([prefix[key] for key in members], axis=0)
        for name, members in segments.items()
    }
    rows: dict[SpecialistGroupId, list[DimensionRow]] = {
        "adoption_retention": [],
        "industry_competition": [],
        "team_execution": [],
    }
    exclusions: Counter[str] = Counter()
    origins = [
        date(year, month, monthrange(year, month)[1])
        for year in range(2022, 2026)
        for month in range(1, 13)
    ]
    release_subjects = []
    for subject in cohort.subjects:
        releases = _release_dates(root / "sdk" / subject.subject_id)
        split_group = (
            "twilio" if subject.subject_id == "sendgrid" else subject.subject_id
        )
        if releases is not None:
            release_subjects.append(subject.subject_id)
        else:
            exclusions["missing_or_incomplete_release_history"] += 1
        values = prefix.get(subject.subject_id)
        peers = peer_prefix[subject.segment] - values if values is not None else None
        for origin in origins:
            end = (origin - _START).days + 1
            if (
                releases is not None
                and end >= 90
                and origin + timedelta(days=90) <= _END
            ):
                middle = bisect_right(releases, origin)
                previous = middle - bisect_right(releases, origin - timedelta(days=90))
                future = bisect_right(releases, origin + timedelta(days=90)) - middle
                rows["team_execution"].append(
                    DimensionRow(
                        subject.subject_id,
                        split_group,
                        origin,
                        origin + timedelta(days=90),
                        (log1p(previous),),
                        log1p(future),
                    )
                )
            if values is None or end < 60 or origin + timedelta(days=30) > _END:
                continue
            previous, current, future = (
                int(values[end - 30] - values[end - 60]),
                int(values[end] - values[end - 30]),
                int(values[end + 30] - values[end]),
            )
            if min(previous, current) < 1000:
                exclusions["sdk_origin_below_1000_downloads"] += 1
                continue
            growth = log((current + 1) / (previous + 1))
            rows["adoption_retention"].append(
                DimensionRow(
                    subject.subject_id,
                    split_group,
                    origin,
                    origin + timedelta(days=30),
                    (log1p(current), log1p(previous), growth),
                    log((future + 1) / (current + 1)),
                )
            )
            if peers is None or len(segments[subject.segment]) < 3:
                exclusions["peer_segment_fewer_than_three_sdks"] += 1
                continue
            peer_previous, peer_current, peer_future = (
                int(peers[end - 30] - peers[end - 60]),
                int(peers[end] - peers[end - 30]),
                int(peers[end + 30] - peers[end]),
            )
            share_change = log((current + 1) / (current + peer_current + 1)) - log(
                (previous + 1) / (previous + peer_previous + 1)
            )
            target = log((future + 1) / (future + peer_future + 1)) - log(
                (current + 1) / (current + peer_current + 1)
            )
            rows["industry_competition"].append(
                DimensionRow(
                    subject.subject_id,
                    split_group,
                    origin,
                    origin + timedelta(days=30),
                    (
                        log1p(current),
                        log1p(previous),
                        growth,
                        log1p(peer_current),
                        log1p(peer_previous),
                        log((peer_current + 1) / (peer_previous + 1)),
                        share_change,
                    ),
                    target,
                )
            )
    return {name: tuple(values) for name, values in rows.items()}, {
        "declared_subjects": len(cohort.subjects),
        "complete_npm_subjects": sorted(histories),
        "complete_release_subjects": release_subjects,
        "fixed_available_peer_membership": segments,
        "exclusions": dict(exclusions),
    }


def build_financial_dataset(
    root: Path,
) -> tuple[tuple[DimensionRow, ...], dict[str, object]]:
    """Build a software-issuer next-annual cash-generation benchmark.

    Args:
        root: Captured SequelSEC fundamentals and issuer tables.
    Returns:
        Annual revenue/OCF predictors and next-annual asinh(OCF/revenue) outcomes.
        This latest-restated panel cannot establish historical as-filed accuracy.
    Raises:
        OSError: Raw captured data cannot be read.
        polars.exceptions.PolarsError: Source schemas or numeric data are invalid.
    """
    issuers = (
        pl.scan_csv(root / "companies.csv.gz", infer_schema_length=0)
        .filter(pl.col("sic").cast(pl.Int64, strict=False).is_between(7370, 7379))
        .select("cik")
    )
    data = (
        pl.scan_csv(root / "fundamentals.csv.gz", infer_schema_length=0)
        .filter(
            pl.col("fiscal_period").eq("FY")
            & pl.col("unit").eq("USD")
            & pl.col("quality").eq("reported")
            & pl.col("metric").is_in(["revenue", "ocf"])
        )
        .join(issuers, on="cik", how="inner")
        .with_columns(
            pl.col("value").cast(pl.Float64),
            pl.col("start_date").str.to_date(),
            pl.col("end_date").str.to_date(),
        )
        .filter(
            (pl.col("end_date") - pl.col("start_date"))
            .dt.total_days()
            .is_between(300, 400)
        )
    )
    panel = (
        data.group_by("cik", "end_date")
        .agg(
            pl.col("value")
            .filter(pl.col("metric").eq("revenue"))
            .first()
            .alias("revenue"),
            pl.col("value").filter(pl.col("metric").eq("ocf")).first().alias("ocf"),
            pl.col("value")
            .filter(pl.col("metric").eq("revenue"))
            .n_unique()
            .alias("revenue_versions"),
            pl.col("value")
            .filter(pl.col("metric").eq("ocf"))
            .n_unique()
            .alias("ocf_versions"),
        )
        .filter(
            pl.col("revenue").gt(100000)
            & pl.col("ocf").is_not_null()
            & pl.col("revenue_versions").eq(1)
            & pl.col("ocf_versions").eq(1)
        )
        .sort("cik", "end_date")
        .with_columns(
            pl.col("revenue").shift(-1).over("cik").alias("future_revenue"),
            pl.col("ocf").shift(-1).over("cik").alias("future_ocf"),
            pl.col("end_date").shift(-1).over("cik").alias("future_end"),
        )
        .filter(
            (pl.col("future_end") - pl.col("end_date"))
            .dt.total_days()
            .is_between(330, 400)
        )
        .collect()
    )
    rows = []
    for batch in panel.iter_slices(n_rows=10):
        for row in batch.iter_rows(named=True):
            rows.append(
                DimensionRow(
                    row["cik"],
                    row["cik"],
                    row["end_date"],
                    row["future_end"],
                    (log1p(row["revenue"]), asinh(row["ocf"] / row["revenue"])),
                    asinh(row["future_ocf"] / row["future_revenue"]),
                )
            )
    return tuple(rows), {
        "eligible_rows": len(rows),
        "eligible_issuers": len({row.subject_id for row in rows}),
        "sic_filter": "7370-7379",
        "quality_filter": "reported FY USD only",
        "availability": "latest restated values; original filing availability unknown",
        "sampling": "current public software issuers; not early private startups",
    }
