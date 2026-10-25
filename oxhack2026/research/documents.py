"""Capture-only document extraction with stable normalized quote locations."""

import logging
import re
from collections.abc import Iterator
from hashlib import sha256
from urllib.parse import urlsplit

import orjson
from bs4 import BeautifulSoup, Tag
from pydantic import Field

from oxhack2026.api.research_v2_schemas import Capture
from oxhack2026.api.schemas import DTO

logger = logging.getLogger(__name__)
PARSER_VERSION = "evidence-document-v2"


def normalize_text(text: str) -> str:
    """Collapse Unicode whitespace without changing words, digits or punctuation."""
    return " ".join(text.split())


class DocumentBlock(DTO):
    """A bounded source block with offsets in the exact normalized document."""

    block_id: str
    text: str = Field(max_length=4000)
    heading: str
    location: str
    start: int
    end: int
    role: str


class EvidenceDocument(DTO):
    """Versioned document artifact; extraction never fetches external resources."""

    parser_version: str = PARSER_VERSION
    capture_id: str
    url: str
    title: str
    language: str
    text: str
    sha256: str
    blocks: tuple[DocumentBlock, ...]
    published_on: str | None = None


def extract_document(capture: Capture, content: bytes) -> EvidenceDocument | None:
    """Extract HTML text and tables; return None for unsupported/API payloads.

    Args:
        capture: Metadata of the retained response.
        content: Integrity-verified raw bytes; no network access is performed.
    Returns:
        Bounded normalized document with exact locations, or None for non-HTML.
    """
    if "pdf" in capture.content_type:
        from oxhack2026.research.pdf import pdf_markup

        content = pdf_markup(content)
        capture = capture.model_copy(update={"content_type": "text/html"})
    if any(kind in capture.content_type for kind in ("json", "xml")):
        return None
    if not content.lstrip().startswith(b"<"):
        return None
    if b"<!DOCTYPE" in content.upper() and "xml" in capture.content_type:
        return None
    soup = BeautifulSoup(content, "lxml")
    title = normalize_text(soup.title.get_text(" ")) if soup.title else ""
    language = str(soup.html.get("lang", "und")) if soup.html else "und"
    published = soup.select_one('meta[property="article:published_time"]')
    published_on = str(published.get("content")) if published else None
    for hidden in soup.select(
        "script,style,noscript,template,nav,footer,aside,body>header,"
        '[role="navigation"],[role="banner"],[hidden],[aria-hidden="true"]'
    ):
        hidden.decompose()
    main_text = ""
    try:
        import trafilatura

        main_text = normalize_text(
            trafilatura.extract(content, include_tables=True, include_comments=False)
            or ""
        )
    except ImportError:
        logger.error("Main-content extractor unavailable; using anchored DOM blocks")  # noqa: TRY400
    root = soup.select_one("main,article,[role=main]") or soup.body or soup
    blocks = _body_blocks(root, main_text, capture.capture_id)
    texts = [block.text for block in blocks]
    normalized = "\n".join(texts)
    return EvidenceDocument(
        capture_id=capture.capture_id,
        url=capture.final_url,
        title=title,
        language=language,
        text=normalized,
        sha256=sha256(normalized.encode()).hexdigest(),
        blocks=tuple(blocks),
        published_on=published_on,
    )


def _body_blocks(root: Tag, main_text: str, capture_id: str) -> list[DocumentBlock]:
    heading = ""
    seen: set[str] = set()
    blocks: list[DocumentBlock] = []
    position = 0
    for index, element in enumerate(_candidate_elements(root)):
        text = normalize_text(element.get_text(" ", strip=True))[:4000]
        if not text or text in seen:
            continue
        seen.add(text)
        if element.name in {"h1", "h2", "h3", "h4"}:
            heading = text
            continue
        if (len(text) < 25 and element.name != "tr") or element.find_parent(
            ["nav", "footer", "aside"]
        ):
            continue
        if element.name != "tr" and element.find_parent(["tr", "blockquote", "li"]):
            continue
        if (
            main_text
            and len(text) > 80
            and text not in main_text
            and root.name in {"body", "html", "[document]"}
        ):
            continue
        role = "table" if element.name == "tr" else "body"
        if element.find_parent("blockquote") or element.name == "blockquote":
            role = "quotation"
        if isinstance(element, Tag) and any(
            "testimonial" in str(parent.get("class", ""))
            for parent in element.parents
            if isinstance(parent, Tag)
        ):
            role = "quotation"
        block = DocumentBlock(
            block_id=sha256(f"{capture_id}:{index}:{text}".encode()).hexdigest(),
            text=text,
            heading=heading,
            location=f"normalized_dom:{element.name}[{index}]",
            start=position,
            end=position + len(text),
            role=role,
        )
        sentences = _sentence_blocks(block, 600 - len(blocks))
        blocks.extend(sentences)
        position = blocks[-1].end + 1
        if len(blocks) >= 600:
            break
    return blocks


def _candidate_elements(root: Tag) -> Iterator[Tag]:
    selector = "h1,h2,h3,h4,p,li,tr,blockquote,div,section"
    for element in root.select(selector):
        if element.name in {"div", "section"} and element.select_one(selector):
            continue
        yield element


def _sentences(text: str, role: str) -> list[str]:
    if role == "table":
        return [text]
    return [
        match.group().strip()
        for match in re.finditer(r".+?(?:[\u3002\uff01\uff1f]|[.!?](?=\s|$)|$)", text)
        if match.group().strip()
    ]


def page_family(url: str) -> str:
    """Group discovered links for bounded fair crawling; unknown paths remain usable."""
    path = urlsplit(url).path.lower()
    for family, pattern in (
        ("company", r"about|team|company|leadership|unternehmen|equipe"),
        ("commercial", r"pricing|price|tarif|preise"),
        ("hiring", r"career|jobs|emploi|karriere"),
        ("customer", r"customer|case-stud|client|kunden"),
        ("product", r"product|platform|solution|produit"),
        ("updates", r"blog|news|changelog|release|actualit"),
    ):
        if re.search(pattern, path):
            return family
    return "other"


def document_bytes(document: EvidenceDocument) -> bytes:
    """Serialize the complete normalized document for integrity-checked replay."""
    return orjson.dumps(document.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)


def _sentence_blocks(block: DocumentBlock, limit: int) -> list[DocumentBlock]:
    result = []
    position = block.start
    for text in _sentences(block.text, block.role)[:limit]:
        identifier = sha256(f"{block.block_id}:{position}:{text}".encode()).hexdigest()
        result.append(
            block.model_copy(
                update={
                    "block_id": identifier,
                    "text": text,
                    "start": position,
                    "end": position + len(text),
                }
            )
        )
        position += len(text) + 1
    return result
