"""Automatic issuer matching needs two-way first-party links and filing identity."""

from unittest.mock import Mock

import pytest

from oxhack2026.api.research_v2_schemas import Capture
from oxhack2026.research.network import CollectionError
from oxhack2026.research.registry import _discover_sec_mapping
from oxhack2026.research.sec_identity import (
    sec_filing_candidates,
    sec_issuer_website_quote,
)

_URL = "https://www.sec.gov/Archives/edgar/data/123/000000012326000001/annual.htm"
_CIK = "0000000123"
_FILING = b"""<html><body>
<ix:nonNumeric name="dei:EntityCentralIndexKey">0000000123</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>
<p>Our website is https://www.example.com/ and contains investor information.</p>
</body></html>"""


@pytest.mark.parametrize(
    "link",
    [
        _URL,
        "https://www.sec.gov/ix?doc=/Archives/edgar/data/123/000000012326000001/annual.htm",
        "https://www.sec.gov/ixviewer/doc/action?doc=%2FArchives%2Fedgar%2Fdata%2F123%2F000000012326000001%2Fannual.htm",
    ],
)
def test_official_archive_and_inline_viewer_links_normalize(link: str) -> None:
    """Only official documents become deduplicated CIK candidates."""
    assert sec_filing_candidates((link, _URL)) == ((_CIK, _URL),)


@pytest.mark.parametrize(
    "link",
    [
        _URL.replace("www.sec.gov", "www.sec.gov.attacker.test"),
        _URL.replace("https://", "http://"),
        _URL.replace("annual.htm", "../annual.htm"),
        _URL.replace("annual.htm", "annual.pdf"),
        "https://www.sec.gov/ix?doc=https://attacker.test/annual.htm",
        "https://www.sec.gov/ix?doc=/x&doc=/y",
    ],
)
def test_untrusted_or_ambiguous_document_links_are_rejected(link: str) -> None:
    """A similar hostname or embedded remote URL never becomes issuer evidence."""
    assert sec_filing_candidates((link,)) == ()


def test_issuer_quote_requires_original_form_and_own_website() -> None:
    """Customer mentions, false hostname suffixes and other issuers abstain."""
    assert sec_issuer_website_quote(_FILING, _CIK, "example.com") == (
        "https://www.example.com"
    )
    for content in (
        _FILING.replace(b"0000000123", b"0000000124"),
        _FILING.replace(b"10-K", b"10-K/A"),
        _FILING.replace(b"10-K", b"10-Q"),
        _FILING.replace(b"Our website", b"Our customer's website"),
        _FILING.replace(b"example.com/", b"example.com.attacker.test/"),
        _FILING.replace(b"www.example.com", b"www.notexample.com"),
        b"",
    ):
        assert sec_issuer_website_quote(content, _CIK, "example.com") is None


def test_automatic_mapping_fetches_only_the_linked_issuer_and_keeps_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retained reciprocal website statement supports a non-human-reviewed map."""
    monkeypatch.setenv("SEC_USER_AGENT", "Fixture research@example.invalid")
    capture = Mock(spec=Capture)
    capture.final_url = _URL
    collector = Mock()
    collector.identity.canonical_domain = "example.com"
    collector.identity.official_links = (_URL,)
    collector.fetcher.fetch.return_value = (capture, _FILING)
    collector.reasons = []
    from unittest.mock import patch

    with patch("oxhack2026.research.extraction.evidence") as support:
        mapping, proof = _discover_sec_mapping(collector)
    assert mapping.cik == _CIK
    assert mapping.reviewed is False
    assert proof == support.return_value
    assert "Our website" in support.call_args.args[1]
    collector.fetcher.fetch.assert_called_once_with(
        _URL, {"User-Agent": "Fixture research@example.invalid"}
    )
    assert collector.reasons == ["sec_identity_verified_by_reciprocal_official_links"]


def test_automatic_mapping_rejects_multiple_linked_issuers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent/customer link cannot silently select one of two possible issuers."""
    monkeypatch.setenv("SEC_USER_AGENT", "Fixture research@example.invalid")
    collector = Mock()
    collector.identity.canonical_domain = "example.com"
    collector.identity.official_links = (_URL, _URL.replace("/123/", "/124/"))
    with pytest.raises(CollectionError, match="ambiguous"):
        _discover_sec_mapping(collector)
    collector.fetcher.fetch.assert_not_called()
