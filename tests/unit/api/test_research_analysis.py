"""Cited synthesis rejects unsupported claims rather than inventing precision."""

import orjson
import pytest

from oxhack2026.api.evidence_mapping_schemas import MappedRecord
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
