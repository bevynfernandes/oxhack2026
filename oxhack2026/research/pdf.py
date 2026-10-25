"""Bounded text-PDF extraction for public disclosures; no OCR or network access."""

from html import escape
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from oxhack2026.research.network import CollectionError


def pdf_markup(content: bytes) -> bytes:
    """Convert up to forty text pages to escaped extraction markup.

    Args:
        content: Already bounded public PDF capture bytes.
    Returns:
        UTF-8 paragraphs labelled by the original PDF page.
    Raises:
        CollectionError: Encrypted, scanned, malformed or oversized public PDF.
    """
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise CollectionError("encrypted_pdf_unsupported")
        if len(reader.pages) > 40:
            raise CollectionError("pdf_page_limit")
        pages: list[str] = []
        size = 0
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            size += len(text.encode())
            if size > 2 * 1024 * 1024:
                raise CollectionError("pdf_text_limit")
            pages.extend(
                f'<p data-pdf-page="{index}">{escape(line)}</p>'
                for line in text.splitlines()
                if line.strip()
            )
        if not pages:
            raise CollectionError("scanned_pdf_unsupported")
        return (
            "<html><body><main>" + "".join(pages) + "</main></body></html>"
        ).encode()
    except PdfReadError as error:
        raise CollectionError("invalid_public_pdf") from error
