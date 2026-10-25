"""Durable v2 metadata and immutable integrity-checked report publication."""

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from oxhack2026.api.evidence_mapping_schemas import MappingJob
from oxhack2026.api.research_v2_schemas import Identity, Job, Report
from oxhack2026.api.schemas import Identifier
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock

_Record = TypeVar("_Record", bound=BaseModel)
_IDENTIFIER = TypeAdapter(Identifier)
_TRANSITIONS = {
    "queued": {"running", "failed"},
    "running": {"running", "completed", "partial", "failed"},
    "completed": set(),
    "partial": set(),
    "failed": set(),
}


@dataclass(frozen=True)
class V2Store:
    """Separate v2 namespace under a caller-controlled writable artifact root.

    Args:
        root: Local persistent root; construction performs no I/O.
    """

    root: Path

    def _path(self, kind: str, identifier: str) -> Path:
        safe = _IDENTIFIER.validate_python(identifier)
        return self.root / "research-v2" / kind / f"{safe}.json"

    def _read(self, kind: str, identifier: str, model: type[_Record]) -> _Record:
        try:
            with self._path(kind, identifier).open("rb") as stream:
                content = stream.read(40 * 1024 * 1024 + 1)
        except FileNotFoundError as error:
            raise KeyError(identifier) from error
        if len(content) > 40 * 1024 * 1024:
            message = "Research metadata exceeds storage budget"
            raise ValueError(message)
        return model.model_validate_json(content)

    def identity(self, identity_id: str) -> Identity:
        """Read exact discovery state; raise KeyError if absent or ValueError if
        corrupt."""
        result = self._read("identities", identity_id, Identity)
        if result.identity_id != identity_id:
            message = "Identity disagrees with storage key"
            raise ValueError(message)
        return result

    def save_identity(self, identity: Identity) -> None:
        """Advance discovery; reject terminal mutation or identity/request changes."""
        path = self._path("identities", identity.identity_id)
        with file_lock(path.with_suffix(".lock")):
            try:
                previous = self.identity(identity.identity_id)
            except KeyError:
                if identity.state != "queued":
                    message = "Discovery must begin queued"
                    raise ValueError(message) from None
            else:
                if (
                    previous.state not in {"queued", "running"}
                    or identity.request != previous.request
                    or identity.requested_at != previous.requested_at
                    or identity.requested_domain != previous.requested_domain
                ):
                    message = "Discovery transition is invalid"
                    raise ValueError(message)
            atomic_write(path, identity.model_dump_json().encode())

    def identities(self) -> tuple[Identity, ...]:
        """Read discovery records for recovery; propagate corrupt metadata errors."""
        return tuple(
            self.identity(path.stem)
            for path in (self.root / "research-v2" / "identities").glob("*.json")
        )

    def job(self, job_id: str) -> Job:
        """Read exact durable job; raise KeyError if absent or ValueError if corrupt."""
        result = self._read("jobs", job_id, Job)
        if result.job_id != job_id:
            message = "Job disagrees with storage key"
            raise ValueError(message)
        return result

    def jobs(self) -> tuple[Job, ...]:
        """Read durable jobs for capacity checks and checkpoint recovery."""
        return tuple(
            self.job(path.stem)
            for path in (self.root / "research-v2" / "jobs").glob("*.json")
        )

    def save_job(self, job: Job) -> None:
        """Persist legal progress while preserving completed collector checkpoints.

        Raises:
            ValueError: Identity, timestamps, terminal work or transitions change.
            OSError: Durable persistence fails.
        """
        job = Job.model_validate_json(job.model_dump_json())
        path = self._path("jobs", job.job_id)
        with file_lock(path.with_suffix(".lock")):
            try:
                previous = self.job(job.job_id)
            except KeyError:
                if job.state != "queued":
                    message = "New jobs must be queued"
                    raise ValueError(message) from None
            else:
                if (
                    job.state not in _TRANSITIONS[previous.state]
                    or job.identity_id != previous.identity_id
                    or job.requested_at != previous.requested_at
                    or job.settings != previous.settings
                    or job.derived_from_report_id != previous.derived_from_report_id
                    or (previous.started_at and job.started_at != previous.started_at)
                    or any(
                        old.state in {"completed", "partial", "failed", "skipped"}
                        and old != new
                        for old, new in zip(previous.sources, job.sources, strict=True)
                    )
                ):
                    message = "Job transition or checkpoint rewrite is invalid"
                    raise ValueError(message)
            atomic_write(path, job.model_dump_json().encode())

    def publish(self, report: Report) -> None:
        """Publish once; verify every referenced capture before indexing a report."""
        report = Report.model_validate_json(report.model_dump_json())
        artifacts = FileArtifactStore(self.root)
        for capture in report.captures:
            artifacts.read(capture.artifact)
        if report.mapping:
            for reference in report.mapping.artifacts:
                artifacts.read(reference)
        path = self._path("reports", report.report_id)
        with file_lock(path.with_suffix(".lock")):
            if path.exists():
                if self.report(report.report_id) != report:
                    message = "An immutable report cannot be replaced"
                    raise ValueError(message)
                return
            reference = artifacts.write(
                report.model_dump_json().encode(), "application/json"
            )
            atomic_write(path, reference.model_dump_json().encode())

    def report(self, report_id: str) -> Report:
        """Read immutable report and verify all raw captures; fail on corruption."""
        reference = self._read("reports", report_id, ArtifactReference)
        artifacts = FileArtifactStore(self.root)
        result = Report.model_validate_json(artifacts.read(reference))
        if result.report_id != report_id:
            message = "Report disagrees with storage key"
            raise ValueError(message)
        for capture in result.captures:
            artifacts.read(capture.artifact)
        if result.mapping:
            for artifact in result.mapping.artifacts:
                artifacts.read(artifact)
        return result

    def mapping_job(self, job_id: str) -> MappingJob:
        """Read a mapping job; raise KeyError if absent or ValueError if corrupt."""
        result = self._read("mapping-jobs", job_id, MappingJob)
        if result.job_id != job_id:
            message = "Mapping job disagrees with storage key"
            raise ValueError(message)
        return result

    def mapping_jobs(self) -> tuple[MappingJob, ...]:
        """Read re-mapping work for shared queue accounting and recovery."""
        return tuple(
            self.mapping_job(path.stem)
            for path in (self.root / "research-v2" / "mapping-jobs").glob("*.json")
        )

    def save_mapping_job(self, job: MappingJob) -> None:
        """Persist monotonic progress; reject terminal rewrites and source changes."""
        job = MappingJob.model_validate_json(job.model_dump_json())
        path = self._path("mapping-jobs", job.job_id)
        with file_lock(path.with_suffix(".lock")):
            try:
                previous = self.mapping_job(job.job_id)
            except KeyError:
                if job.progress.state != "pending":
                    message = "Mapping jobs must begin pending"
                    raise ValueError(message) from None
            else:
                if (
                    previous.progress.state not in {"pending", "running"}
                    or (
                        previous.progress.state == "running"
                        and job.progress.state == "pending"
                    )
                    or previous.source_report_id != job.source_report_id
                    or previous.requested_at != job.requested_at
                    or job.progress.completed_batches
                    < previous.progress.completed_batches
                    or (
                        previous.progress.started_at is not None
                        and job.progress.started_at != previous.progress.started_at
                    )
                ):
                    message = "Mapping job transition or checkpoint rewrite is invalid"
                    raise ValueError(message)
            atomic_write(path, job.model_dump_json().encode())
