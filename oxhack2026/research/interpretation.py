"""Stable per-document chunks, balanced across pages for resumable interpretation."""

from collections import deque
from dataclasses import dataclass

from oxhack2026.explanations.gemini import proposal_prompt
from oxhack2026.research.documents import DocumentBlock, EvidenceDocument


@dataclass(frozen=True)
class EvidenceChunk:
    """One deterministic prompt and its exact local source lookup."""

    prompt: str
    lookup: dict[str, tuple[EvidenceDocument, DocumentBlock]]


def evidence_chunks(
    candidates: list[tuple[EvidenceDocument, DocumentBlock]],
    company: str,
    live: bool,
    max_blocks: int = 24,
) -> list[EvidenceChunk]:
    """Build stable bounded chunks and interleave documents without mixing them.

    Args:
        candidates: Prioritized public evidence; duplicate boilerplate is removed.
        company: Confirmed company name, used as data rather than an instruction.
        live: Compact classification submissions for the configured Live model.
        max_blocks: Maximum sentences per request, between one and 24.
    Returns:
        Deterministic page chunks, preserving cache keys when more pages arrive.
    Raises:
        ValueError: The requested sentence count is outside the supported range.
    """
    if not 1 <= max_blocks <= 24:
        message = "max_blocks must be between one and 24"
        raise ValueError(message)
    documents: dict[str, list[tuple[EvidenceDocument, DocumentBlock]]] = {}
    seen: set[str] = set()
    for document, block in candidates:
        key = block.text.casefold()
        if key in seen:
            continue
        seen.add(key)
        documents.setdefault(document.capture_id, []).append((document, block))
    queues: deque[deque[EvidenceChunk]] = deque()
    for rows in documents.values():
        chunks: deque[EvidenceChunk] = deque()
        group: list[tuple[EvidenceDocument, DocumentBlock]] = []
        size = 0
        for row in rows:
            required = len(row[1].text[:1200].encode()) + 900
            if group and (len(group) >= max_blocks or size + required > 16_000):
                chunks.append(_chunk(group, company, live))
                group, size = [], 0
            group.append(row)
            size += required
        if group:
            chunks.append(_chunk(group, company, live))
        queues.append(chunks)
    result = []
    while queues:
        queue = queues.popleft()
        result.append(queue.popleft())
        if queue:
            queues.append(queue)
    return result


def _chunk(
    rows: list[tuple[EvidenceDocument, DocumentBlock]], company: str, live: bool
) -> EvidenceChunk:
    lookup = {
        f"b{index}" if live else block.block_id: (document, block)
        for index, (document, block) in enumerate(rows)
    }
    blocks: list[dict[str, str]] = [
        {
            "block_id": key,
            "text": block.text[:1200],
            "heading": block.heading[:300],
            "title": document.title[:300],
            "language": document.language,
        }
        for key, (document, block) in lookup.items()
    ]
    return EvidenceChunk(proposal_prompt(company, blocks, compact=live), lookup)
