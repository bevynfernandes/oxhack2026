"""Cited synthesis rejects unsupported claims rather than inventing precision."""

import orjson
import pytest

from oxhack2026.api.evidence_mapping_schemas import MappedRecord, QuoteAnchor
from oxhack2026.research.analysis import validate_analysis


def record() -> MappedRecord:
    """Build one attributable source mapping for citation controls."""
    return MappedRecord(
        mapping_id="mapping",
        record_type="observation",
        record_id="observation",
        group_id="financial_health",
        concept="revenue",
        subject="company",
        subject_name="Example",
        attribution="company_reported",
        method="rule",
        evidence_ids=("evidence",),
        exact_decimal="10",
        reason_codes=(),
    )


@pytest.mark.parametrize(
    "text,ids,group",
    [
        ("Company reports revenue of 20.", ["mapping"], "financial_health"),
        ("Company reports revenue of 10.", ["absent"], "financial_health"),
        ("Company reports revenue of 10.", ["mapping"], "team_execution"),
        ("The company will survive.", ["mapping"], "financial_health"),
    ],
)
def test_unsupported_analysis(text: str, ids: list[str], group: str) -> None:
    """New quantities, absent references, wrong groups and forecasts are rejected."""
    response = orjson.dumps(
        {
            "proposals": [
                {"text": text, "mapping_ids": ids, "group_id": group, "kind": "finding"}
            ]
        }
    ).decode()
    result = validate_analysis(response, [record()])
    assert result.state == "unavailable"
    assert not result.statements


@pytest.mark.parametrize(
    "quote,text,accepted",
    [
        (
            "Revenue is USD 10 million.",
            "Company reports revenue of USD 10 billion.",
            False,
        ),
        ("Revenue is USD -100.", "Company reports revenue of USD 100.", False),
        ("Revenue is -$100.", "Company reports revenue of $100.", False),
        ("Revenue is $100.", "Company reports revenue of -$100.", False),
        ("Revenue is 100.", "Company reports revenue of .100.", False),
        ("Revenue is 100.", "Company reports revenue of 1e100.", False),
        ("Runway is 10 days.", "Company reports runway of 10 years.", False),
        ("Storage is 10 GB.", "Company reports storage of 10 MB.", False),
        (
            "Revenue is USD 100 per month.",
            "Company reports revenue of USD 100 per year.",
            False,
        ),
        (
            "Revenue is USD 100 per year.",
            "Company reports revenue of USD 100 per month.",
            False,
        ),
        (
            "Monthly revenue is USD 100.",
            "Company reports annual revenue of USD 100.",
            False,
        ),
        ("Revenue is USD 100 per month.", "Company reports revenue of USD 100.", False),
        (
            "Revenue is USD 100 per month.",
            "Company reports monthly revenue of USD 100.",
            True,
        ),
        (
            "Revenue is USD 100 in 2025.",
            "Company reports revenue of USD 100 in 2026.",
            False,
        ),
        ("Revenue is USD 100 in 2025.", "Company reports revenue of USD 100.", False),
        (
            "Revenue is USD 100 in 2025.",
            "Company reports revenue of USD 100 in 2025.",
            True,
        ),
        ("Revenue is EUR 100.", "Company reports revenue of USD 100.", False),
        ("Revenue is 10 dollars.", "Company reports revenue of 10 euros.", False),
        ("Retention is 10%.", "Company reports retention of 10 customers.", False),
        ("Revenue is 100 and 10 customers.", "Company reports revenue of 10.", False),
        ("Revenue is 100 and 10 customers.", "Company reports 100 customers.", False),
        ("Revenue is 100 and 10 customers.", "Company reports revenue of 100.", True),
        (
            "Revenue is USD 10 million.",
            "Company reports revenue of USD 10,000,000.",
            True,
        ),
        ("Revenue is USD -100.", "Company reports revenue of USD -100.", True),
        ("Revenue is €100.", "Company reports revenue of EUR 100.", True),
    ],
)
def test_analysis_preserves_complete_cited_quantities(
    quote: str, text: str, accepted: bool
) -> None:
    """Amounts retain sign, magnitude, currency, units and their specific metric."""
    anchor = QuoteAnchor(
        evidence_id="evidence",
        capture_id="capture",
        document_sha256="a" * 64,
        block_id="block",
        exact=quote,
        start=0,
        end=len(quote),
        location="body",
    )
    result = validate_analysis(
        orjson.dumps(
            {
                "proposals": [
                    {
                        "text": text,
                        "mapping_ids": ["mapping"],
                        "group_id": "financial_health",
                        "kind": "finding",
                    }
                ]
            }
        ).decode(),
        [record().model_copy(update={"quotes": (anchor,)})],
    )
    assert bool(result.statements) is accepted


def test_supported_analysis() -> None:
    """A valid attributable finding retains its public evidence references."""
    result = validate_analysis(
        orjson.dumps(
            {
                "proposals": [
                    {
                        "text": "Company reports revenue of 10.",
                        "mapping_ids": ["mapping"],
                        "group_id": "financial_health",
                        "kind": "finding",
                    }
                ]
            }
        ).decode(),
        [record()],
    )
    assert result.state == "completed"
    assert result.statements[0].mapping_ids == ("mapping",)


@pytest.mark.parametrize(
    "changes,text",
    [
        ({"subject": "customer"}, "Company reports revenue of 10."),
        ({"qualifier": "lower_bound"}, "Company reports revenue of 10."),
        ({"exact_decimal": "100"}, "Company reports revenue of 10."),
        ({"exact_decimal": "-100"}, "Company reports revenue of 100."),
        ({}, "Company revenue is 10."),
    ],
)
def test_analysis_preserves_subject_bounds_and_attribution(
    changes: dict[str, object], text: str
) -> None:
    """Citations cannot transfer customer outcomes or silently remove qualifiers."""
    result = validate_analysis(
        orjson.dumps(
            {
                "proposals": [
                    {
                        "text": text,
                        "mapping_ids": ["mapping"],
                        "group_id": "financial_health",
                        "kind": "finding",
                    }
                ]
            }
        ).decode(),
        [record().model_copy(update=changes)],
    )
    assert not result.statements
