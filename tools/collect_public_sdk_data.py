"""Capture the declared public SDK cohort with raw hashes; never infer missing data."""

import argparse
import logging
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from urllib.parse import quote, urlsplit

import httpx
import orjson
from pydantic import BaseModel, Field

_REQUEST_LOCK = Lock()
_LAST_NPM_REQUEST = 0.0


class Subject(BaseModel):
    """Declared SDK identity and technical peer group.

    Attributes:
        subject_id: Stable cohort identity.
        package: Exact npm package name.
        segment: Declared technical peer group, not a company-success label.
    """

    subject_id: str
    package: str
    segment: str


class Cohort(BaseModel):
    """Bounded SDK collection recipe.

    Attributes:
        subjects: Predeclared subjects, independent of subsequent download counts.
    """

    subjects: tuple[Subject, ...]


class Repository(BaseModel):
    """Repository URL reported by npm.

    Attributes:
        url: Public repository URL; legal ownership is not established by it.
    """

    url: str = ""


class PackageMetadata(BaseModel):
    """Small public npm version response.

    Attributes:
        repository: Repository linkage supplied by the package publisher.
    """

    repository: Repository | str | None = None


class Release(BaseModel):
    """Only the release fields needed to stop historical pagination.

    Attributes:
        published_at: Actual public release time, absent for unpublished drafts.
    """

    published_at: str | None = None


class Capture(BaseModel):
    """Raw-byte download lineage.

    Attributes:
        url: Public source location, containing no credentials.
        captured_at: UTC capture time.
        sha256: Exact response byte digest.
        byte_size: Raw response size.
    """

    url: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha256: str
    byte_size: int


def capture(
    path: Path,
    url: str,
    github_cli: str | None = None,
    client: httpx.Client | None = None,
) -> bytes:
    """Retain one verified cached response or a newly downloaded raw response.

    Args:
        path: Destination retained between runs.
        url: Public HTTP URL, or GitHub API path when github_cli is supplied.
        github_cli: Resolved gh executable; authentication is handled by gh.
        client: Shared connection pool, required for new HTTP captures.
    Returns:
        Exact response bytes with adjacent capture metadata.
    Raises:
        ValueError: An existing cache fails its retained digest.
        httpx.HTTPError: HTTP capture fails.
        subprocess.CalledProcessError: GitHub capture fails.
        OSError: Capture storage or process execution fails.
    """
    metadata_path = path.with_suffix(path.suffix + ".capture.json")
    if path.exists() and metadata_path.exists():
        content = path.read_bytes()
        metadata = Capture.model_validate_json(metadata_path.read_bytes())
        if (
            sha256(content).hexdigest() != metadata.sha256
            or len(content) != metadata.byte_size
            or metadata.url != url
        ):
            message = f"Public capture cache integrity failed: {path.name}"
            raise ValueError(message)
        return content
    if github_cli is not None:
        content = subprocess.run(  # noqa: S603
            [github_cli, "api", url], capture_output=True, check=True, timeout=90
        ).stdout
    else:
        if client is None:
            message = "New HTTP captures require a managed HTTP client"
            raise ValueError(message)
        global _LAST_NPM_REQUEST
        for attempt in range(3):
            if urlsplit(url).hostname == "api.npmjs.org":
                with _REQUEST_LOCK:
                    sleep(max(0, 1.5 - (monotonic() - _LAST_NPM_REQUEST)))
                    _LAST_NPM_REQUEST = monotonic()
            response = client.get(url)
            if response.status_code == 429 and attempt < 2:
                delay = max(float(response.headers.get("Retry-After", "30")), 30)
                logging.warning(
                    "npm rate limit; respecting %.0f-second retry delay", delay
                )
                sleep(max(delay, 1))
                continue
            response.raise_for_status()
            content = response.content
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    metadata_path.write_text(
        Capture(
            url=url, sha256=sha256(content).hexdigest(), byte_size=len(content)
        ).model_dump_json(indent=2)
    )
    return content


def collect_subject(
    subject: Subject, root: Path, github_cli: str, client: httpx.Client
) -> None:
    """Capture four years of daily downloads and bounded stable-release history.

    Args:
        subject: Exact predeclared package and peer group.
        root: Retained raw-capture directory.
        github_cli: Resolved gh executable for the public release API.
        client: Shared managed HTTP connection pool.
    Returns:
        None; writes raw captures and a per-subject collection status.
    Raises:
        OSError: Output status cannot be retained.
    """
    destination = root / "sdk" / subject.subject_id
    destination.mkdir(parents=True, exist_ok=True)
    status: dict[str, object] = {"subject": subject.model_dump(), "errors": []}
    errors: list[str] = []
    try:
        metadata = PackageMetadata.model_validate_json(
            capture(
                destination / "package.json",
                f"https://registry.npmjs.org/{quote(subject.package, safe='')}/latest",
                client=client,
            )
        )
        for year in range(2022, 2026):
            capture(
                destination / f"downloads-{year}.json",
                "https://api.npmjs.org/downloads/range/"
                f"{year}-01-01:{year}-12-31/{subject.package}",
                client=client,
            )
        repository_url = (
            metadata.repository.url
            if isinstance(metadata.repository, Repository)
            else metadata.repository or ""
        )
        normalized = repository_url.removeprefix("git+")
        if normalized.startswith("git@github.com:"):
            normalized = normalized.replace("git@github.com:", "https://github.com/", 1)
        parsed = urlsplit(normalized)
        parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if parsed.hostname != "github.com" or len(parts) < 2:
            logging.error(
                "npm metadata has no public GitHub repository: %s", subject.subject_id
            )
            status["errors"] = ["unresolved_repository"]
            (destination / "status.json").write_bytes(orjson.dumps(status))
            return
        repository = "/".join(parts[:2])
        status["repository"] = repository
        capture(destination / "repository.json", f"repos/{repository}", github_cli)
        complete = False
        for page in range(1, 11):
            raw = capture(
                destination / f"releases-{page}.json",
                f"repos/{repository}/releases?per_page=100&page={page}",
                github_cli,
            )
            releases = [Release.model_validate(row) for row in orjson.loads(raw)]
            if len(releases) < 100:
                complete = True
                break
        status["release_pagination_complete"] = complete
    except (
        httpx.HTTPError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        OSError,
    ) as error:
        logging.error(
            "Public SDK capture failed for %s: %s",
            subject.subject_id,
            type(error).__name__,
            exc_info=True,
        )
        errors.append(type(error).__name__)
    status["errors"] = errors
    (destination / "status.json").write_bytes(
        orjson.dumps(status, option=orjson.OPT_INDENT_2)
    )


def main() -> None:
    """Collect a frozen cohort with two bounded concurrent source workers.

    Returns:
        None; retains raw captures and status for every declared subject.
    Raises:
        ValueError: gh is unavailable or the cohort is invalid.
        OSError: Cohort input or capture storage fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cohort", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    github_cli = shutil.which("gh")
    if github_cli is None:
        bundled = Path(".cache/tools/gh_2.103.2_macOS_arm64/bin/gh")
        if not bundled.is_file():
            message = "Install GitHub CLI to collect public release metadata"
            raise ValueError(message)
        github_cli = str(bundled.resolve())
    cohort = Cohort.model_validate_json(arguments.cohort.read_bytes())
    with (
        httpx.Client(timeout=45, follow_redirects=True) as client,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        futures = [
            executor.submit(
                collect_subject, subject, arguments.output, github_cli, client
            )
            for subject in cohort.subjects
        ]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
