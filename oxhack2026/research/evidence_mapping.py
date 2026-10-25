"""Domain-independent, source-anchored rules and optional Gemini mapping."""

import logging
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import orjson
from pydantic import BaseModel, ValidationError

from oxhack2026.api.evidence_mapping_schemas import (
    MAPPING_DEADLINE_SECONDS,
    DimensionCoverage,
    MappedRecord,
    MappingBundle,
    MappingDisposition,
    MappingProgress,
    NumericalContext,
    QuoteAnchor,
    SubjectKind,
)
from oxhack2026.api.research_analysis import InterpretationStatistics, ResearchAnalysis
from oxhack2026.api.research_configuration import ResearchSettings
from oxhack2026.api.research_v2_schemas import (
    Capture,
    Claim,
    Observation,
    Report,
    ResearchEvidence,
)
from oxhack2026.explanations.config import mapping_mode as mapping_mode
from oxhack2026.explanations.gemini import (
    LIVE_BATCH_LIMIT,
    BlockClassification,
    CachedInterpretation,
    EvidenceProposal,
    GeminiInterpreter,
    MappingUnavailable,
    proposal_prompt,
)
from oxhack2026.models.startup_outlook import (
    SPECIALIST_GROUP_IDS,
    SpecialistOutlook,
    StartupOutlook,
)
from oxhack2026.research.analysis import AnalysisBatch, synthesize
from oxhack2026.research.documents import (
    PARSER_VERSION,
    DocumentBlock,
    EvidenceDocument,
    document_bytes,
    extract_document,
    page_family,
)
from oxhack2026.research.interpretation import EvidenceChunk, evidence_chunks
from oxhack2026.research.mapping_policy import (
    CONCEPT_LOOKUP,
    EVENT_GROUPS,
    METRIC_GROUPS,
    METRIC_PROVIDERS,
    classify,
    metric_eligible,
    price_only_financial_claim,
)
from oxhack2026.research.network import CollectionError
from oxhack2026.research.numerical_claims import normalize_quantity
from oxhack2026.storage.artifacts import FileArtifactStore
from oxhack2026.storage.contracts import ArtifactReference
from oxhack2026.storage.local import atomic_write, file_lock

logger = logging.getLogger(__name__)


@dataclass
class MappingWork:
    """Indexed run-local records; lookups never scan the full evidence inventory."""

    records: list[MappedRecord] = field(default_factory=list)
    dispositions: list[MappingDisposition] = field(default_factory=list)
    claims: dict[str, Claim] = field(default_factory=dict)
    support: dict[str, ResearchEvidence] = field(default_factory=dict)
    seen: dict[str, int] = field(default_factory=dict)
    capture_times: dict[str, datetime] = field(default_factory=dict)
    accepted_blocks: set[str] = field(default_factory=set)
    quote_bytes: int = 0
    quote_count: int = 0


@dataclass(frozen=True)
class ClaimCandidate:
    """One bounded grounded interpretation before acceptance."""

    document: EvidenceDocument
    block: DocumentBlock
    concept: str
    subject: SubjectKind
    method: Literal["rule", "gemini"] = "rule"


def _identifier(*values: str) -> str:
    return sha256("\x00".join(values).encode()).hexdigest()


def _observation_quantity(row: Observation) -> NumericalContext | None:
    """Retain supported measured units and periods for cited synthesis."""
    if row.value is None or row.unit not in {"count", "downloads", "USD"}:
        return None
    return NumericalContext(
        value_decimal=format(Decimal(str(row.value)), "f"),
        unit="currency" if row.unit == "USD" else "count",
        currency="USD" if row.unit == "USD" else None,
        measurement_start=row.window.start.date() if row.window else None,
        measurement_end=row.window.end.date() if row.window else None,
        qualifier="exact",
    )


def _subject(text: str, document: EvidenceDocument, company: str) -> SubjectKind:
    if re.search(
        r"\b(?:our customers?|their customers?)\s+"
        r"(?:increased|grew|achieved|generated|reduced|saved)\b|"
        r"\b(?:shoppers|client.s|customer.s)\b",
        text,
        re.I,
    ):
        return "customer"
    company_match = re.search(rf"(?<!\w){re.escape(company)}(?!\w)", text, re.I)
    if page_family(document.url) == "customer" or any(
        word in document.title.lower() for word in ("case study", "customer story")
    ):
        return "customer"
    if (company_match and company_match.start() < 5) or re.search(
        r"\b(?:we|our|nous|notre|wir|unser|nosotros|nuestro)\b", text, re.I
    ):
        return "company"
    return "unresolved"


def _coverage(records: list[MappedRecord]) -> tuple[DimensionCoverage, ...]:
    result = []
    for group in SPECIALIST_GROUP_IDS:
        rows = [row for row in records if row.group_id == group]
        usable = any(row.metric_eligible for row in rows)
        reported = any(
            row.record_type != "observation" and row.subject != "unresolved"
            for row in rows
        )
        result.append(
            DimensionCoverage(
                group_id=group,
                status="measured" if usable else "reported" if reported else "missing",
                mapping_ids=tuple(row.mapping_id for row in rows),
                observation_ids=tuple(
                    row.record_id for row in rows if row.record_type == "observation"
                ),
                claim_ids=tuple(
                    row.record_id for row in rows if row.record_type == "claim"
                ),
                event_ids=tuple(
                    row.record_id for row in rows if row.record_type == "event"
                ),
                reason_codes=()
                if usable
                else ("attributed_evidence_only",)
                if reported
                else ("no_supported_evidence",),
            )
        )
    return tuple(result)


def mapped_outlook(report: Report, bundle: MappingBundle) -> StartupOutlook:
    """Project validated metric assignments without promoting prose into model data."""
    specialists = []
    assigned: set[str] = set()
    for group in SPECIALIST_GROUP_IDS:
        rows = [
            row
            for row in bundle.records
            if row.group_id == group and row.record_type == "observation"
        ]
        usable = [row for row in rows if row.metric_eligible]
        assigned.update(row.record_id for row in rows)
        specialists.append(
            SpecialistOutlook(
                group_id=group,
                data_status="available" if usable else "insufficient_data",
                metric_observation_ids=tuple(row.record_id for row in rows),
                usable_metric_observation_ids=tuple(row.record_id for row in usable),
                evidence_ids=tuple(
                    sorted({key for row in usable for key in row.evidence_ids})
                ),
                reason_codes=("model_not_trained",)
                if usable
                else ("model_not_trained", "no_eligible_measurements"),
            )
        )
    return report.outlook.model_copy(
        update={
            "grouping_policy_version": bundle.policy_version,
            "specialists": tuple(specialists),
            "unassigned_metric_observation_ids": tuple(
                row.observation_id
                for row in report.observations
                if row.observation_id not in assigned
            ),
        }
    )


@dataclass
class MappingEngine:
    """Interpret verified captures with independent per-record acceptance.

    Args:
        root: Existing artifact root, never a website or model-controlled path.
        checkpoint: Optional durable callback invoked after completed batches.
        interpreter: Injected bounded client for deterministic tests.
    """

    root: Path
    checkpoint: Callable[[MappingProgress], None] | None = None
    interpreter: GeminiInterpreter | None = None
    cache_policy: Literal["reuse", "bypass"] = "reuse"
    deadline: float | None = None
    prior_requests: int = 0
    prior_input: int = 0
    _extended: bool = False
    _statistics: InterpretationStatistics | None = None
    _artifacts: list[ArtifactReference] = field(default_factory=list)
    _reasons: list[str] = field(default_factory=list)

    def map(self, report: Report, source_report_id: str | None = None) -> Report:
        """Return a new mapped value; callers publish it under a new immutable ID.

        Args:
            report: Source report whose captures will all be integrity-verified.
            source_report_id: Original immutable report when explicitly re-mapping.
        Returns:
            Report with source-grounded claims, dimension coverage and null forecasts.
        Raises:
            OSError: Artifacts or checkpoints cannot be persisted.
            ValueError: Captured artifacts are corrupt or configuration is invalid.
        """
        started = datetime.now(UTC)
        settings = report.settings
        self._extended = settings is not None
        deadline = self.deadline or (
            time.monotonic()
            + (
                settings.deadline_seconds * 0.3
                if settings
                else MAPPING_DEADLINE_SECONDS
            )
            - 2
        )
        mode = settings.mapping_mode if settings else mapping_mode()
        self._statistics = InterpretationStatistics(mode=mode)
        self._artifacts = []
        self._reasons = []
        store = FileArtifactStore(self.root)
        records, dispositions = self._structured(report)
        work = MappingWork(
            records=records,
            dispositions=dispositions,
            claims={item.claim_id: item for item in report.claims},
            support={item.evidence_id: item for item in report.evidence},
            capture_times={
                item.capture_id: item.collected_at for item in report.captures
            },
        )
        candidates: list[tuple[EvidenceDocument, DocumentBlock]] = []
        excluded = {
            candidate.capture_id
            for source in report.sources
            if source.discovery
            for candidate in source.discovery.candidates
            if candidate.state != "matched" and candidate.capture_id
        }
        for capture in report.captures:
            content = store.read(capture.artifact)
            if capture.capture_id in excluded:
                work.dispositions.append(
                    MappingDisposition(
                        candidate_id=capture.capture_id,
                        state="unmapped",
                        reason="unverified_search_candidate",
                    )
                )
                continue
            if time.monotonic() >= deadline:
                self._reasons.append("mapping_deadline")
                break
            try:
                document = self._document(capture, content)
            except CollectionError as error:
                logger.error("Captured document extraction failed: %s", str(error))  # noqa: TRY400
                self._reasons.append(str(error))
                work.dispositions.append(
                    MappingDisposition(
                        candidate_id=capture.capture_id,
                        state="unmapped",
                        reason=str(error),
                    )
                )
                continue
            if document is None:
                work.dispositions.append(
                    MappingDisposition(
                        candidate_id=capture.capture_id,
                        state="unmapped",
                        reason="not_a_supported_html_document",
                    )
                )
                continue
            self._map_document(report, document, work, candidates)
        self._progress(started, 0)
        interpreter = self._interpreter(settings, deadline)
        analysis = None
        if mode == "rules_gemini":
            analysis = self._run_interpreter(
                report, candidates, work, interpreter, started
            )
        self._sync_statistics(interpreter)
        self._set_statistics(stage="finished")
        bundle = MappingBundle(
            schema_version="evidence-mapping-v2"
            if self._extended
            else "evidence-mapping-v1",
            statistics=self._statistics,
            analysis=analysis,
            mapped_at=datetime.now(UTC),
            source_as_of=report.outlook.as_of,
            derived_from_report_id=source_report_id,
            state="partial" if self._reasons else "completed",
            mode=mode,
            records=tuple(records),
            dimensions=_coverage(records),
            dispositions=tuple(
                row
                for row in work.dispositions
                if row.state != "unmapped"
                or row.candidate_id not in work.accepted_blocks
            ),
            artifacts=tuple(self._artifacts),
            model=interpreter.model if mode == "rules_gemini" else None,
            model_version=interpreter.model_version,
            input_tokens=interpreter.input_tokens,
            output_tokens=interpreter.output_tokens,
            generation_attempts=interpreter.attempts,
            reason_codes=tuple(dict.fromkeys(self._reasons)),
        )
        self._conflicts(work)
        limitations = tuple(
            reason
            for reason in report.limitations
            if reason
            != "Numerical forecasts remain null; no models were trained or run."
        )
        result = report.model_copy(
            update={
                "mapping": bundle,
                "claims": tuple(work.claims.values()),
                "evidence": tuple(work.support.values()),
                "outlook": mapped_outlook(report, bundle),
                "limitations": (
                    *limitations,
                    (
                        "Forecasting models remain untrained; evidence interpreta"
                        "tion is separate from prediction."
                    ),
                    *bundle.reason_codes,
                ),
            }
        )
        return Report.model_validate_json(result.model_dump_json())

    def _run_interpreter(
        self,
        report: Report,
        candidates: list[tuple[EvidenceDocument, DocumentBlock]],
        work: MappingWork,
        interpreter: GeminiInterpreter,
        started: datetime,
    ) -> ResearchAnalysis | None:
        interpreter.open_session()
        try:
            analysis = None
            if self._extended:
                self._extract_with_reserve(
                    report, candidates, work, interpreter, started
                )
                self._sync_statistics(interpreter)
                self._set_statistics(stage="synthesizing")
                self._progress(
                    started, self._statistics.batches if self._statistics else 0
                )
                analysis = synthesize(
                    work.records,
                    lambda prompt: self._bounded_response(
                        prompt, interpreter, AnalysisBatch
                    ),
                )
                self._reasons.extend(analysis.reason_codes)
            else:
                self._interpret(report, candidates, work, interpreter, started)
            self._reasons.extend(interpreter.reason_codes)
            return analysis
        finally:
            interpreter.close_session()

    def _extract_with_reserve(
        self,
        report: Report,
        candidates: list[tuple[EvidenceDocument, DocumentBlock]],
        work: MappingWork,
        interpreter: GeminiInterpreter,
        started: datetime,
    ) -> None:
        """Reserve time, one provider request and input capacity for cited synthesis."""
        deadline, requests, input_budget = (
            interpreter.deadline,
            interpreter.max_requests,
            interpreter.max_input,
        )
        thinking_level = interpreter.thinking_level
        if interpreter.model.startswith("gemma-4-"):
            interpreter.thinking_level = "minimal"
        remaining = max(0, deadline - time.monotonic())
        interpreter.deadline -= (
            min(90, remaining * 0.4)
            if "-live" not in interpreter.model
            else min(120, remaining * 0.3)
        )
        interpreter.max_requests -= min(2, requests)
        interpreter.max_input -= min(32_000, int(input_budget * 0.4))
        try:
            self._interpret_extended(report, candidates, work, interpreter, started)
        finally:
            interpreter.deadline = deadline
            interpreter.max_requests = requests
            interpreter.max_input = input_budget
            interpreter.thinking_level = thinking_level

    def _interpreter(
        self, settings: ResearchSettings | None, deadline: float
    ) -> GeminiInterpreter:
        interpreter = self.interpreter or (
            GeminiInterpreter(deadline, model=settings.model)
            if settings
            else GeminiInterpreter(deadline)
        )
        interpreter.thinking_level = (
            settings.thinking_level if settings and settings.thinking_level else "high"
        )
        if settings:
            interpreter.max_requests = max(
                0, settings.model_requests - self.prior_requests
            )
            interpreter.max_input = max(
                0, settings.input_reservation - self.prior_input
            )
        return interpreter

    def _map_document(
        self,
        report: Report,
        document: EvidenceDocument,
        work: MappingWork,
        candidates: list[tuple[EvidenceDocument, DocumentBlock]],
    ) -> None:
        for block in document.blocks:
            rule = classify(block.text)
            if self._extended:
                candidates.append((document, block))
            if rule is None:
                if not self._extended:
                    candidates.append((document, block))
                work.dispositions.append(
                    MappingDisposition(
                        candidate_id=block.block_id,
                        state="unmapped",
                        reason="no_explicit_concept_or_proposition",
                    )
                )
                continue
            subject = _subject(block.text, document, report.identity.company_name)
            if block.role == "quotation":
                subject = "customer" if subject == "customer" else "unresolved"
            candidate = ClaimCandidate(document, block, rule.concept, subject)
            mapped = self._claim(report, candidate)
            self._accept(mapped, candidate, work, _claim_key(mapped, block.text))

    def _structured(
        self, report: Report
    ) -> tuple[list[MappedRecord], list[MappingDisposition]]:
        records = []
        dispositions = []
        owners = {
            item.observation_id: source.provider
            for source in report.sources
            for item in source.observations
        }
        evidence = {item.evidence_id: item for item in report.evidence}
        for row in report.observations:
            group = METRIC_GROUPS.get(row.metric_id)
            if group is None:
                dispositions.append(
                    MappingDisposition(
                        candidate_id=row.observation_id,
                        state="unmapped",
                        reason="unknown_metric_definition",
                    )
                )
                continue
            eligible, reason = metric_eligible(row, report.outlook.as_of)
            if eligible and owners.get(row.observation_id) != METRIC_PROVIDERS.get(
                row.metric_id
            ):
                eligible, reason = False, "unverified_provider_scope"
            quantity = _observation_quantity(row)
            records.append(
                MappedRecord(
                    mapping_id=_identifier("metric", row.observation_id),
                    record_type="observation",
                    record_id=row.observation_id,
                    group_id=group,
                    concept=row.metric_id,
                    subject="product"
                    if row.metric_id.startswith(("npm", "github"))
                    else "company",
                    subject_name=report.identity.company_name,
                    attribution="company_reported"
                    if owners.get(row.observation_id) == "sec"
                    else "platform_measured",
                    method="rule",
                    evidence_ids=row.evidence_ids,
                    resource=evidence[row.evidence_ids[0]].url
                    if row.evidence_ids
                    else None,
                    metric_eligible=eligible,
                    exact_decimal=quantity.value_decimal if quantity else None,
                    numerical_context=quantity,
                    reason_codes=(reason,),
                    qualifier="exact" if row.value is not None else "unknown",
                )
            )
        for event in report.events:
            group = EVENT_GROUPS.get(event.kind)
            if group:
                records.append(
                    MappedRecord(
                        mapping_id=_identifier("event", event.event_id),
                        record_type="event",
                        record_id=event.event_id,
                        group_id=group,
                        concept=event.kind,
                        subject="product"
                        if event.kind != "hn_exact_domain_story"
                        else "company",
                        subject_name=report.identity.company_name,
                        resource=event.url,
                        attribution="platform_measured",
                        method="rule",
                        evidence_ids=event.evidence_ids,
                        published_on=event.published_at,
                        reason_codes=("retrieved_event_not_business_outcome",),
                    )
                )
        return records, dispositions

    def _document(self, capture: Capture, content: bytes) -> EvidenceDocument | None:
        store = FileArtifactStore(self.root)
        key = _identifier(capture.capture_id, capture.artifact.sha256, PARSER_VERSION)
        path = self.root / "research-v2" / "mapping-documents" / f"{key}.json"
        with file_lock(path.with_suffix(".lock")):
            if path.exists():
                reference = ArtifactReference.model_validate_json(path.read_bytes())
                cached = EvidenceDocument.model_validate_json(store.read(reference))
                self._artifacts.append(reference)
                return cached
            else:
                document = extract_document(capture, content)
                if document is None:
                    return None
                reference = store.write(document_bytes(document), "application/json")
                atomic_write(path, reference.model_dump_json().encode())
        self._artifacts.append(reference)
        return document

    def _claim(self, report: Report, candidate: ClaimCandidate) -> MappedRecord:
        document, block = candidate.document, candidate.block
        concept, subject = candidate.concept, candidate.subject
        quote = block.text[:2000]
        evidence_id = _identifier(document.capture_id, block.block_id, quote)
        anchor = QuoteAnchor(
            evidence_id=evidence_id,
            capture_id=document.capture_id,
            document_sha256=document.sha256,
            block_id=block.block_id,
            exact=quote,
            start=block.start,
            end=block.start + len(quote),
            location=block.location,
            prefix=document.text[max(0, block.start - 80) : block.start],
            suffix=document.text[
                block.start + len(quote) : block.start + len(quote) + 80
            ],
        )
        quantity = normalize_quantity(quote, document.language)
        official = (urlsplit(document.url).hostname or "").removeprefix(
            "www."
        ) == report.identity.canonical_domain
        return MappedRecord(
            mapping_id=_identifier("claim", evidence_id, concept),
            record_type="claim",
            record_id=_identifier("assertion", evidence_id, concept),
            group_id="adoption_retention"
            if subject == "customer"
            else CONCEPT_LOOKUP[concept].group,
            concept=concept,
            subject=subject,
            subject_name=report.identity.company_name
            if subject == "company"
            else "Subject retained in quoted context",
            attribution="company_reported" if official else "coverage_candidate",
            method=candidate.method,
            evidence_ids=(evidence_id,),
            quotes=(anchor,),
            language=document.language,
            published_on=document.published_on,
            numerical_context=quantity,
            exact_decimal=quantity.value_decimal if quantity else None,
            qualifier=quantity.qualifier if quantity else "unknown",
            reason_codes=(
                "source_attribution_not_independent_verification",
                "customer_context"
                if subject == "customer"
                else "subject_unresolved"
                if subject == "unresolved"
                else "explicit_subject",
            ),
        )

    def _conflicts(self, work: MappingWork) -> None:
        groups: dict[tuple[str, ...], list[MappedRecord]] = {}
        for row in work.records:
            quantity = row.numerical_context
            if (
                row.record_type != "claim"
                or row.subject != "company"
                or not quantity
                or quantity.qualifier != "exact"
            ):
                continue
            period = (
                str(quantity.measurement_start),
                str(quantity.measurement_end),
                str(quantity.measurement_instant),
            )
            if period == ("None", "None", "None"):
                continue
            key = (
                row.subject_name,
                row.concept,
                quantity.unit,
                quantity.currency or "",
                *period,
            )
            groups.setdefault(key, []).append(row)
        for rows in groups.values():
            for row in rows:
                conflicts = tuple(
                    other.record_id
                    for other in rows
                    if other.exact_decimal != row.exact_decimal
                )
                if conflicts:
                    work.claims[row.record_id] = work.claims[row.record_id].model_copy(
                        update={"conflicts_with": conflicts}
                    )

    def _accept(
        self,
        mapped: MappedRecord,
        candidate: ClaimCandidate,
        work: MappingWork,
        key: str,
    ) -> None:
        document, text = candidate.document, candidate.block.text
        required = len(mapped.quotes[0].exact.encode())
        if work.quote_count >= 1000 or work.quote_bytes + required > 2 * 1024 * 1024:
            self._reasons.append("mapping_claim_budget")
            return
        work.quote_count += 1
        work.quote_bytes += required
        if key in work.seen:
            index = work.seen[key]
            previous = work.records[index]
            work.records[index] = previous.model_copy(
                update={
                    "evidence_ids": tuple(
                        dict.fromkeys((*previous.evidence_ids, *mapped.evidence_ids))
                    ),
                    "quotes": (*previous.quotes, *mapped.quotes),
                }
            )
            original = work.claims[previous.record_id]
            work.claims[previous.record_id] = original.model_copy(
                update={"evidence_ids": work.records[index].evidence_ids}
            )
        else:
            work.seen[key] = len(work.records)
            work.records.append(mapped)
            work.claims[mapped.record_id] = Claim(
                claim_id=mapped.record_id,
                text=text[:2000],
                category=mapped.concept,
                attribution="company_reported"
                if mapped.attribution == "company_reported"
                else "coverage_candidate",
                evidence_ids=mapped.evidence_ids,
                published_on=document.published_on,
            )
        anchor = mapped.quotes[0]
        work.accepted_blocks.add(anchor.block_id)
        work.support[anchor.evidence_id] = ResearchEvidence(
            evidence_id=anchor.evidence_id,
            capture_id=document.capture_id,
            url=document.url,
            excerpt=anchor.exact,
            location=anchor.location,
            collected_at=work.capture_times[document.capture_id],
        )

    def _progress(self, started: datetime, batches: int) -> None:
        if self.checkpoint:
            self.checkpoint(
                MappingProgress(
                    state="running",
                    started_at=started,
                    completed_batches=batches,
                    statistics=self._statistics,
                )
            )

    def _set_statistics(self, **updates: object) -> None:
        if self._statistics:
            self._statistics = self._statistics.model_copy(update=updates)

    def _sync_statistics(self, interpreter: GeminiInterpreter) -> None:
        known = getattr(interpreter, "usage_available", False) is True
        self._set_statistics(
            provider_requests=interpreter.attempts,
            input_tokens=interpreter.input_tokens if known else None,
            output_tokens=interpreter.output_tokens if known else None,
        )

    def _cache_key(
        self,
        prompt: str,
        interpreter: GeminiInterpreter,
        schema: type[BaseModel] | None = None,
    ) -> str:
        from oxhack2026.explanations.gemini import proposal_schema

        version = (
            "research-analysis-v2"
            if schema
            else "evidence-proposals-v3"
            if self._extended
            else "evidence-proposals-v1"
        )
        compact = "-live" in interpreter.model or interpreter.model.startswith(
            "gemma-4-"
        )
        fingerprint = orjson.dumps(
            proposal_schema(compact=compact, output=schema), option=orjson.OPT_SORT_KEYS
        ).decode()
        return _identifier(
            prompt,
            interpreter.model,
            version,
            fingerprint,
            getattr(interpreter, "thinking_level", "high"),
        )

    def _interpret_extended(
        self,
        report: Report,
        candidates: list[tuple[EvidenceDocument, DocumentBlock]],
        work: MappingWork,
        interpreter: GeminiInterpreter,
        started: datetime,
    ) -> None:
        candidates.sort(
            key=lambda item: (
                not bool(re.search(r"\d", item[1].text)),
                page_family(item[0].url),
            )
        )
        chunks = evidence_chunks(
            candidates,
            report.identity.company_name,
            "-live" in interpreter.model or interpreter.model.startswith("gemma-4-"),
            6 if interpreter.model.startswith("gemma-4-") else 24,
        )
        # Existing completed chunks are cheap to replay before spending on new work.
        chunks.sort(
            key=lambda chunk: (
                not (
                    self.root
                    / "research-v2"
                    / "mapping-cache"
                    / f"{self._cache_key(chunk.prompt, interpreter)}.json"
                ).exists()
            )
        )
        count = sum(len(chunk.lookup) for chunk in chunks)
        self._set_statistics(
            candidates=count,
            deferred=count,
            stage="extracting",
            model=interpreter.model,
        )
        for chunk in chunks:
            if (
                interpreter.attempts >= interpreter.max_requests
                or time.monotonic() >= interpreter.deadline
            ):
                self._reasons.append("gemini_candidate_budget")
                break
            if not self._interpret_chunk(report, chunk, work, interpreter):
                self._sync_statistics(interpreter)
                self._progress(
                    started, self._statistics.batches if self._statistics else 0
                )
                if self._reasons[-1] in {
                    "gemini_credentials_missing",
                    "gemini_authentication_failed",
                    "gemini_invalid_request",
                    "gemini_model_unavailable",
                    "gemini_token_or_call_budget",
                    "gemini_deadline",
                }:
                    break
                continue
            if self._statistics:
                processed = self._statistics.processed + len(chunk.lookup)
                self._set_statistics(
                    processed=processed,
                    deferred=count - processed,
                    batches=self._statistics.batches + 1,
                )
                self._sync_statistics(interpreter)
                self._progress(started, self._statistics.batches)
        if self._statistics and self._statistics.deferred:
            self._reasons.append("gemini_candidate_budget")

    def _chunk_response(
        self, prompt: str, interpreter: GeminiInterpreter
    ) -> list[object]:
        return _proposal_values(self._bounded_response(prompt, interpreter))

    def _bounded_response(
        self,
        prompt: str,
        interpreter: GeminiInterpreter,
        schema: type[BaseModel] | None = None,
    ) -> str:
        for attempt in range(2):
            try:
                return self._response(prompt, interpreter, schema)
            except MappingUnavailable as error:
                retryable = str(error) in {
                    "gemini_rate_limited",
                    "gemini_provider_unavailable",
                    "gemini_provider_internal_error",
                    "gemini_provider_bad_gateway",
                    "gemini_provider_overloaded",
                    "gemini_provider_timeout",
                    "gemini_request_timeout",
                    "gemini_connection_failed",
                    "gemini_live_provider_unavailable",
                    "gemini_invalid_output",
                    "gemini_incomplete_response",
                }
                if (
                    attempt
                    or not retryable
                    or interpreter.attempts >= interpreter.max_requests
                    or time.monotonic() + 2 >= interpreter.deadline
                ):
                    raise
                logger.error("Retrying bounded interpretation after %s", str(error))  # noqa: TRY400
                interpreter.close_session()
                interpreter.open_session()
                time.sleep(1)
        raise MappingUnavailable("gemini_invalid_output")

    def _interpret_chunk(
        self,
        report: Report,
        chunk: EvidenceChunk,
        work: MappingWork,
        interpreter: GeminiInterpreter,
    ) -> bool:
        try:
            values = self._chunk_response(chunk.prompt, interpreter)
        except (
            MappingUnavailable,
            ValidationError,
            orjson.JSONDecodeError,
            ImportError,
        ) as error:
            logger.error("Evidence chunk unavailable: %s", type(error).__name__)  # noqa: TRY400
            self._reasons.append(
                str(error)
                if isinstance(error, MappingUnavailable)
                else "gemini_invalid_or_unavailable"
            )
            if self._statistics:
                self._set_statistics(failed_batches=self._statistics.failed_batches + 1)
            return False
        self._apply_proposals(report, values, chunk.lookup, work)
        return True

    def _apply_proposals(
        self,
        report: Report,
        values: list[object],
        lookup: dict[str, tuple[EvidenceDocument, DocumentBlock]],
        work: MappingWork,
    ) -> None:
        for value in values:
            before = len(work.dispositions)
            try:
                proposal = _validated_proposal(value, lookup)
                self._proposal(report, proposal, lookup, work)
            except (ValidationError, MappingUnavailable):
                logger.error("Rejected malformed evidence proposal")  # noqa: TRY400
                work.dispositions.append(
                    MappingDisposition(
                        candidate_id=_identifier(str(value)),
                        state="rejected",
                        reason="gemini_invalid_proposal",
                    )
                )
            if self._statistics:
                rejected = any(
                    row.state == "rejected" for row in work.dispositions[before:]
                )
                self._set_statistics(
                    accepted_proposals=self._statistics.accepted_proposals
                    + (not rejected),
                    rejected_proposals=self._statistics.rejected_proposals + rejected,
                )

    def _interpret(
        self,
        report: Report,
        candidates: list[tuple[EvidenceDocument, DocumentBlock]],
        work: MappingWork,
        interpreter: GeminiInterpreter,
        started: datetime,
    ) -> None:
        candidates.sort(
            key=lambda item: (
                not bool(re.search(r"\d", item[1].text)),
                page_family(item[0].url),
            )
        )
        batches: list[list[tuple[EvidenceDocument, DocumentBlock]]] = []
        live = "-live" in interpreter.model or interpreter.model.startswith("gemma-4-")
        candidate_limit = LIVE_BATCH_LIMIT if live else 120
        batch_bytes = 24_000 if live else 6500
        batch_limit = 1 if live else 6
        selected = (
            _live_candidates(candidates, candidate_limit)
            if live
            else candidates[:candidate_limit]
        )
        size = 0
        for candidate in selected:
            required = len(candidate[1].text[:1200].encode()) + 900
            if not batches or size + required > batch_bytes:
                batches.append([])
                size = 0
            batches[-1].append(candidate)
            size += required
        completed_batches = 0
        for batch in batches[:batch_limit]:
            lookup = {
                f"b{index}" if live else block.block_id: (document, block)
                for index, (document, block) in enumerate(batch)
            }
            blocks = [
                {
                    "block_id": block_id,
                    "text": block.text[:1200],
                    "heading": block.heading[:300],
                    "title": document.title[:300],
                    "language": document.language,
                }
                for block_id, (document, block) in lookup.items()
            ]
            prompt = proposal_prompt(
                report.identity.company_name,
                blocks,
                compact=live,
            )
            try:
                response = self._response(prompt, interpreter)
                proposals = _proposal_values(response)
            except (
                MappingUnavailable,
                ValidationError,
                orjson.JSONDecodeError,
                ImportError,
            ) as error:
                logger.error(  # noqa: TRY400
                    "Evidence interpretation batch unavailable: %s",
                    type(error).__name__,
                )
                self._reasons.append(
                    str(error)
                    if isinstance(error, MappingUnavailable)
                    else "gemini_invalid_or_unavailable"
                )
                if isinstance(error, (MappingUnavailable, ImportError)):
                    break
                continue
            self._apply_proposals(report, proposals, lookup, work)
            completed_batches += 1
            self._progress(started, completed_batches)
        if len(candidates) > candidate_limit or len(batches) > batch_limit:
            self._reasons.append("gemini_candidate_budget")

    def _response(
        self,
        prompt: str,
        interpreter: GeminiInterpreter,
        schema: type[BaseModel] | None = None,
    ) -> str:
        store = FileArtifactStore(self.root)
        key = self._cache_key(prompt, interpreter, schema)
        path = self.root / "research-v2" / "mapping-cache" / f"{key}.json"
        with file_lock(path.with_suffix(".lock")):
            if path.exists() and self.cache_policy == "reuse":
                if self._statistics:
                    self._set_statistics(
                        cached_batches=self._statistics.cached_batches + 1
                    )
                reference = ArtifactReference.model_validate_json(path.read_bytes())
                captured = CachedInterpretation.model_validate_json(
                    store.read(reference)
                )
                interpreter.model_version = captured.model_version
                interpreter.reason_codes.extend(
                    code
                    for code in captured.reason_codes
                    if code not in interpreter.reason_codes
                )
            else:
                before_input, before_output = (
                    interpreter.input_tokens,
                    interpreter.output_tokens,
                )
                prior_reasons = len(interpreter.reason_codes)
                response = (
                    interpreter.generate(prompt, schema)
                    if schema
                    else interpreter.generate(prompt)
                )
                captured = CachedInterpretation(
                    response=response,
                    prompt_sha256=sha256(prompt.encode()).hexdigest(),
                    model=interpreter.model,
                    model_version=interpreter.model_version,
                    input_tokens=interpreter.input_tokens - before_input,
                    output_tokens=interpreter.output_tokens - before_output,
                    reason_codes=tuple(interpreter.reason_codes[prior_reasons:]),
                )
                reference = store.write(
                    captured.model_dump_json().encode(), "application/json"
                )
                try:
                    if schema:
                        schema.model_validate_json(response)
                    else:
                        _proposal_values(response)
                except (
                    ValidationError,
                    MappingUnavailable,
                    orjson.JSONDecodeError,
                ) as error:
                    self._artifacts.append(reference)
                    raise MappingUnavailable("gemini_invalid_output") from error
                interruptions = {
                    "gemini_live_background_incomplete",
                    "gemini_live_background_interrupted",
                }
                if not captured.reason_codes or (
                    set(captured.reason_codes) <= interruptions
                    and orjson.loads(response).get("proposals")
                ):
                    atomic_write(path, reference.model_dump_json().encode())
        self._artifacts.append(reference)
        return captured.response

    def _proposal(
        self,
        report: Report,
        proposal: EvidenceProposal,
        lookup: dict[str, tuple[EvidenceDocument, DocumentBlock]],
        work: MappingWork,
    ) -> None:
        entry = lookup.get(proposal.block_id)
        if entry is None or proposal.concept not in CONCEPT_LOOKUP:
            work.dispositions.append(
                MappingDisposition(
                    candidate_id=_identifier(proposal.block_id),
                    state="rejected",
                    reason="gemini_unknown_block_or_concept",
                )
            )
            return
        document, block = entry
        position = block.text.find(proposal.exact_quote)
        if position < 0:
            work.dispositions.append(
                MappingDisposition(
                    candidate_id=block.block_id,
                    state="rejected",
                    reason="gemini_quote_not_in_capture",
                )
            )
            return
        rule_subject = _subject(
            proposal.exact_quote, document, report.identity.company_name
        )
        subject = proposal.subject
        if subject == "company" and rule_subject != "company":
            subject = rule_subject
        if block.role == "quotation":
            subject = "customer" if rule_subject == "customer" else "unresolved"
        financial = CONCEPT_LOOKUP[proposal.concept].group == "financial_health"
        price_only = financial and price_only_financial_claim(proposal.exact_quote)
        if price_only or (subject == "product" and financial):
            work.dispositions.append(
                MappingDisposition(
                    candidate_id=block.block_id,
                    state="rejected",
                    reason="gemini_price_not_financial_performance"
                    if price_only
                    else "gemini_subject_concept_mismatch",
                )
            )
            return
        selected = block.model_copy(
            update={
                "text": proposal.exact_quote,
                "start": block.start + position,
                "end": block.start + position + len(proposal.exact_quote),
            }
        )
        candidate = ClaimCandidate(
            document, selected, proposal.concept, subject, "gemini"
        )
        mapped = self._claim(report, candidate)
        if mapped.numerical_context is None:
            mapped = mapped.model_copy(update={"qualifier": proposal.qualifier})
        key = _claim_key(mapped, proposal.exact_quote)
        self._accept(mapped, candidate, work, key)


def _claim_key(mapped: MappedRecord, text: str) -> str:
    return _identifier(
        mapped.subject,
        mapped.subject_name,
        mapped.attribution,
        mapped.concept,
        text.casefold(),
    )


def _live_candidates(
    candidates: list[tuple[EvidenceDocument, DocumentBlock]], limit: int
) -> list[tuple[EvidenceDocument, DocumentBlock]]:
    """Select source blocks round-robin so one long page cannot fill the request.

    Args:
        candidates: Prioritized, source-anchored candidate blocks.
        limit: Maximum number of blocks to select.
    Returns:
        Bounded candidates retaining priority within each captured document.
    """
    by_capture: dict[str, deque[tuple[EvidenceDocument, DocumentBlock]]] = {}
    for document, block in candidates:
        by_capture.setdefault(document.capture_id, deque()).append((document, block))
    queues = deque(by_capture.values())
    selected: list[tuple[EvidenceDocument, DocumentBlock]] = []
    while queues and len(selected) < limit:
        queue = queues.popleft()
        selected.append(queue.popleft())
        if queue:
            queues.append(queue)
    return selected


def _proposal_values(response: str) -> list[object]:
    parsed = orjson.loads(response)
    if (
        not isinstance(parsed, dict)
        or not isinstance(parsed.get("proposals"), list)
        or len(parsed["proposals"]) > 30
    ):
        raise MappingUnavailable("gemini_invalid_batch_shape")
    values: list[object] = parsed["proposals"]
    return values


def _validated_proposal(
    value: object, lookup: dict[str, tuple[EvidenceDocument, DocumentBlock]]
) -> EvidenceProposal:
    if isinstance(value, dict) and set(value) == {"block_id", "concept", "subject"}:
        classified = BlockClassification.model_validate(value)
        entry = lookup.get(classified.block_id)
        if entry is None:
            raise MappingUnavailable("gemini_unknown_source_sentence")
        _, block = entry
        return EvidenceProposal(
            block_id=classified.block_id,
            exact_quote=block.text[:1200],
            concept=classified.concept,
            subject=classified.subject,
            subject_name="Subject retained in quoted context",
            qualifier="unknown",
        )
    return EvidenceProposal.model_validate(value)
