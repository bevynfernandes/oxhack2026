"""POSIX durable jobs and content-addressed immutable research reports."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from oxhack2026.api.research_schemas import ResearchJob, ResearchReport
from oxhack2026.catalog.schemas import Identifier
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock
from oxhack2026.storage.publication import PublicationIndex

_IDENTIFIER = TypeAdapter(Identifier)
_TRANSITIONS = {
    "queued": {"running", "failed"},
    "running": {"completed", "partial", "failed"},
    "completed": set(),
    "partial": set(),
    "failed": set(),
}


@dataclass(frozen=True)
class LocalResearchStore:
    """Store local jobs and immutable reports using existing locks/artifact storage.

    Args:
        root: Application-controlled root shared with source artifact storage.
    """

    root: Path

    def _job_path(self, job_id: str) -> Path:
        identifier = _IDENTIFIER.validate_python(job_id)
        return self.root / "research-jobs" / f"{identifier}.json"

    def job(self, job_id: str) -> ResearchJob:
        """Read durable state; raise KeyError if absent, ValueError if corrupt."""
        try:
            with self._job_path(job_id).open("rb") as stream:
                content = stream.read(65537)
        except FileNotFoundError as error:
            raise KeyError(job_id) from error
        if len(content) > 65536:
            message = "Research job exceeds metadata size budget"
            raise ValueError(message)
        result = ResearchJob.model_validate_json(content)
        if result.job_id != job_id:
            message = "Research job identity disagrees with its index"
            raise ValueError(message)
        return result

    def jobs(self) -> tuple[ResearchJob, ...]:
        """Read persisted jobs for recovery; propagate filesystem/integrity errors."""
        return tuple(
            self.job(path.stem)
            for path in sorted((self.root / "research-jobs").glob("*.json"))
        )

    def save_job(self, job: ResearchJob) -> None:
        """Atomically create/advance a job; reject invalid or terminal rewrites.

        Args:
            job: Validated new state retaining original request and creation time.
        Raises:
            ValueError: A transition or immutable identity changes illegally.
            OSError: Durable metadata cannot be written.
        """
        job = ResearchJob.model_validate_json(job.model_dump_json())
        path = self._job_path(job.job_id)
        with file_lock(path.with_suffix(".lock")):
            try:
                previous = self.job(job.job_id)
            except KeyError:
                if job.state != "queued":
                    message = "A new research job must be queued"
                    raise ValueError(message) from None
            else:
                if (
                    job.state not in _TRANSITIONS[previous.state]
                    or job.request != previous.request
                    or job.requested_at != previous.requested_at
                    or (
                        previous.started_at is not None
                        and job.started_at != previous.started_at
                    )
                ):
                    message = "Research job transition or identity is invalid"
                    raise ValueError(message)
            atomic_write(path, job.model_dump_json().encode())

    def _reports(self) -> PublicationIndex:
        path = self.root / "research-reports.json"
        try:
            with path.open("rb") as stream:
                content = stream.read(8 * 1024 * 1024 + 1)
        except FileNotFoundError:
            return PublicationIndex()
        if len(content) > 8 * 1024 * 1024:
            message = "Research report index exceeds metadata budget"
            raise ValueError(message)
        return PublicationIndex.model_validate_json(content)

    def publish(self, report: ResearchReport) -> None:
        """Publish exact report bytes; reject rewriting an existing report ID.

        Args:
            report: Complete report whose references were validated by the worker.
        Raises:
            ValueError: An immutable ID is reused with different content.
            OSError: Artifact/index persistence fails.
        """
        report = ResearchReport.model_validate_json(report.model_dump_json())
        self._verify_capture(report)
        reference = FileArtifactStore(self.root).write(
            report.model_dump_json().encode(), "application/json"
        )
        with file_lock(self.root / ".research-report-publication.lock"):
            index = self._reports()
            previous = index.versions.get(report.report_id)
            if previous is not None and previous != reference:
                message = "An immutable research report cannot be replaced"
                raise ValueError(message)
            updated = PublicationIndex(
                current=report.report_id,
                versions=index.versions | {report.report_id: reference},
            )
            atomic_write(
                self.root / "research-reports.json", updated.model_dump_json().encode()
            )

    def report(self, report_id: str) -> ResearchReport:
        """Read an exact report; raise KeyError if absent, ValueError if corrupt."""
        identifier = _IDENTIFIER.validate_python(report_id)
        reference = self._reports().versions[identifier]
        report = ResearchReport.model_validate_json(
            FileArtifactStore(self.root).read(reference)
        )
        if report.report_id != identifier:
            message = "Research report identity disagrees with its index"
            raise ValueError(message)
        self._verify_capture(report)
        return report

    def _verify_capture(self, report: ResearchReport) -> None:
        digest = report.inventory.capture_sha256
        FileArtifactStore(self.root).read(
            ArtifactReference(
                path=f"objects/{digest[:2]}/{digest}",
                sha256=digest,
                byte_size=report.inventory.capture_byte_size,
                media_type="application/octet-stream",
            )
        )
