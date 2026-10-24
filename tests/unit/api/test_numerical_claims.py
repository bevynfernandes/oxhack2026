"""Conservative source-quantity normalization across document locales."""

import pytest
from pydantic import ValidationError

from oxhack2026.api.evidence_mapping_schemas import NumericalContext
from oxhack2026.research.numerical_claims import normalize_quantity


@pytest.mark.parametrize(
    ("text", "language", "value", "unit", "qualifier"),
    [
        ("We raised USD 12 million.", "en", "12000000", "currency", "exact"),
        (
            "Nous avons plus de EUR 1,5 million.",
            "fr",
            "1500000.0",
            "currency",
            "lower_bound",
        ),
        (
            "Wir haben etwa EUR 1,5 Millionen.",
            "de",
            "1500000.0",
            "currency",
            "approximate",
        ),
        ("Our retention reached 90 percent.", "en", "90", "percent", "exact"),
        ("We have 12,000 customers.", "en", "12000", "count", "exact"),
        ("We have 0 customers.", "en", "0", "count", "exact"),
        ("Revenue fell -5%.", "en", "-5", "percent", "exact"),
    ],
)
def test_explicit_quantities(
    text: str,
    language: str,
    value: str,
    unit: str,
    qualifier: str,
) -> None:
    """Only an explicit unit and unambiguous locale permit decimal normalization."""
    result = normalize_quantity(text, language)
    assert result
    assert (result.value_decimal, result.unit, result.qualifier) == (
        value,
        unit,
        qualifier,
    )
    assert result.measurement_start is None


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Revenue was $12 million.", "en"),
        ("We have -12 customers.", "en"),
        ("Revenue was USD \u0661\u066b\u0665 million.", "ar"),
        ("Revenue fell \u22125%.", "en"),
        ("Revenue was USD 1,234.", "und"),
        ("Revenue was USD 12 million and USD 14 million.", "en"),
        ("Revenue was USD 12 million and retention was 80%.", "en"),
        ("We have between 10 and 20 customers.", "en"),
        ("We have 10-20 customers.", "en"),
        ("Revenue was EUR 2 billion.", "fr"),
        ("As of 2026-19-01 we had 12 customers.", "en"),
    ],
)
def test_ambiguous_quantities_abstain(text: str, language: str) -> None:
    """Ambiguity cannot become a fabricated metric or a guessed currency."""
    assert normalize_quantity(text, language) is None


def test_explicit_measurement_window() -> None:
    """Publication time is never substituted for a missing measurement period."""
    result = normalize_quantity(
        "Our revenue was USD 12 million from 2025-01-01 to 2025-12-31.", "en"
    )
    assert result
    assert str(result.measurement_start) == "2025-01-01"
    assert str(result.measurement_end) == "2025-12-31"
    assert (
        normalize_quantity(
            "Our revenue was USD 12 million from 2026-01-01 to 2025-12-31.", "en"
        )
        is None
    )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e100", "one"])
def test_normalized_value_must_be_decimal(value: str) -> None:
    """Public contracts reject non-finite or ambiguous serialized amounts."""
    with pytest.raises(ValidationError):
        NumericalContext(value_decimal=value, unit="count", qualifier="exact")
