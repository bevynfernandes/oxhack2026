"""Strict SEC identity candidates and reciprocal issuer-website evidence."""

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, urlsplit

from lxml import etree  # type: ignore[import-untyped]

_ARCHIVE = re.compile(
    r"/Archives/edgar/data/([0-9]{1,10})/[0-9]{18}/[A-Za-z0-9_.-]+\.html?"
)


def sec_filing_candidates(links: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """Normalize official SEC inline-viewer or original HTML filing links.

    Args:
        links: Links discovered on confirmed first-party company pages.
    Returns:
        Deduplicated (ten-digit CIK, original SEC document URL) candidates.
        A candidate alone never establishes the company's issuer identity.
    """
    candidates: set[tuple[str, str]] = set()
    for link in links:
        parsed = urlsplit(link)
        if parsed.scheme != "https" or parsed.netloc not in {"sec.gov", "www.sec.gov"}:
            continue
        path = parsed.path
        if path in {"/ix", "/ixviewer/doc/action"}:
            documents = parse_qs(parsed.query).get("doc", [])
            if len(documents) != 1:
                continue
            path = documents[0]
        match = _ARCHIVE.fullmatch(path)
        if match and int(match[1]) > 0:
            candidates.add((match[1].zfill(10), f"https://www.sec.gov{path}"))
    return tuple(sorted(candidates))


def sec_issuer_website_quote(content: bytes, cik: str, domain: str) -> str | None:
    """Require original 10-K identity fields and an explicit own-website statement.

    Args:
        content: Bounded original filing HTML retained by the public fetcher.
        cik: Exact ten-digit issuer identity from the filing URL.
        domain: Confirmed company hostname, without a scheme or www prefix.
    Returns:
        Literal source URL/domain quote when the issuer identifies it as its own
        website. Customer mentions, different issuers and other forms abstain.
    """
    if not content.strip():
        return None
    parser = etree.HTMLParser(no_network=True, recover=True)
    document = etree.fromstring(content, parser)
    if document is None:
        return None
    identities = {
        "".join(node.itertext()).strip().zfill(10)
        for node in document.xpath("//*[@name='dei:EntityCentralIndexKey']")
    }
    forms = {
        "".join(node.itertext()).strip()
        for node in document.xpath("//*[@name='dei:DocumentType']")
    }
    if identities != {cik} or forms != {"10-K"}:
        return None
    address = (
        rf"(?<![\w.-])(?:https?://)?(?:www\.)?{re.escape(domain)}"
        r"(?![\w-]|\.[A-Za-z0-9])"
    )
    statement = re.compile(
        rf"\b(?:our|(?:the )?(?:company|registrant)['\u2019]s)\s+"
        rf"(?:corporate\s+)?(?:website|web site|internet (?:site|address))"
        rf"[^.!?]{{0,60}}?(?P<address>{address})",
        re.IGNORECASE,
    )
    for node in document.xpath("//p | //div"):
        text = " ".join(" ".join(node.itertext()).split())
        if len(text) > 4000:
            continue
        match = statement.search(text)
        if match and match["address"].encode() in content:
            return match["address"]
    return None
