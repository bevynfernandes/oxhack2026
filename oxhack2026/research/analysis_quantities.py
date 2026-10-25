"""Compare complete cited quantities without pooling amounts across metrics."""

import re
from dataclasses import dataclass
from decimal import Decimal

from oxhack2026.api.evidence_mapping_schemas import MappedRecord

_CURRENCY = r"USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY|dollars?|euros?|pounds?|[$€£¥]"
_SCALE = r"trillion|billion|million|thousand|bn|[kmb]"
_QUANTITY = re.compile(
    rf"(?<![\w.])(?P<sign>[+\-\u2212]?)\s*(?P<currency>{_CURRENCY})?\s*"
    r"(?P<number>[+\-\u2212]?\d+(?:,\d{3})*(?:\.\d+)?)"
    rf"(?:\s*(?P<scale>{_SCALE})\b)?"
    rf"(?:\s*(?P<unit>{_CURRENCY}|%|percent\b|percentage points?\b|"
    r"users?\b|customers?\b|employees?\b|subscribers?\b|countries\b|"
    r"country\b|downloads?\b|stars?\b|repositories\b|openings?\b|"
    r"seconds?\b|minutes?\b|hours?\b|days?\b|weeks?\b|months?\b|years?\b|"
    r"bytes?\b|[KMGT]i?B\b))?",
    re.I,
)
_METRIC = re.compile(
    r"\b(revenue|ARR|MRR|funding|valuation|profit|loss|retention|churn|"
    r"users?|customers?|employees?|subscribers?|countries|downloads?|stars?|"
    r"repositories|openings?|runway)\b",
    re.I,
)
_RATE = re.compile(
    r"\b(?:per|a|each)\s+(second|minute|hour|day|week|month|quarter|year|annum)\b|"
    r"/\s*(second|minute|hour|day|week|month|quarter|year|mo|yr)\b|"
    r"\b(monthly|annually|annual|yearly|daily|weekly|quarterly|hourly)\b",
    re.I,
)
_DATE = r"(?:Q[1-4]\s*)?\d{4}(?:-\d{2}-\d{2})?"
_WINDOW = re.compile(
    rf"\b(?:from|between)\s+{_DATE}\s+(?:to|and|through)\s+{_DATE}|"
    rf"\b(?:as of|during|in|for|FY|fiscal year|year ended|period ending)\s*{_DATE}",
    re.I,
)
_RATE_NAMES = {
    "mo": "month",
    "monthly": "month",
    "yr": "year",
    "annum": "year",
    "annual": "year",
    "annually": "year",
    "yearly": "year",
    "daily": "day",
    "weekly": "week",
    "quarterly": "quarter",
    "hourly": "hour",
}
_SCALES = {
    "k": 3,
    "thousand": 3,
    "m": 6,
    "million": 6,
    "b": 9,
    "bn": 9,
    "billion": 9,
    "trillion": 12,
}
_CURRENCIES = {
    "$": "dollar",
    "dollar": "dollar",
    "dollars": "dollar",
    "€": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "£": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "¥": "yen",
}


@dataclass(frozen=True)
class _Quantity:
    value: Decimal
    currency: str
    unit: str
    metric: str
    rate: str = ""
    window: tuple[str, ...] = ()


def _nearby(
    pattern: re.Pattern[str], text: str, start: int, end: int
) -> list[re.Match[str]]:
    """Keep context in this clause without crossing another numerical expression."""
    matches = []
    for match in pattern.finditer(text):
        gap = (
            text[match.end() : start]
            if match.end() <= start
            else text[end : match.start()]
        )
        if not re.search(r"[.;!?\n]|\d", gap):
            matches.append(match)
    return matches


def _metric(text: str, start: int, end: int) -> str:
    """Find the nearest metric in the same clause as this amount."""
    candidates = []
    for match in _nearby(_METRIC, text, start, end):
        gap = (
            text[match.end() : start]
            if match.end() <= start
            else text[end : match.start()]
        )
        candidates.append((len(gap), match.group().casefold().rstrip("s")))
    return min(candidates)[1] if candidates else ""


def _quantities(text: str) -> list[_Quantity]:
    """Normalize explicit English quantities; unsupported forms remain unsupported."""
    quantities = []
    matches = list(_QUANTITY.finditer(text))
    if re.search(r"\d", _QUANTITY.sub("", text)):
        return [_Quantity(Decimal("NaN"), "", "", "")]
    for match in matches:
        number = match["number"].replace(",", "").replace("\u2212", "-")
        sign = match["sign"].replace("\u2212", "-")
        if sign and number.startswith(("-", "+")):
            return [_Quantity(Decimal("NaN"), "", "", "")]
        exponent = _SCALES.get((match["scale"] or "").casefold(), 0)
        value = Decimal(f"{sign}{number}e{exponent}")
        unit = (match["unit"] or "").casefold()
        currency = (match["currency"] or "").casefold()
        if re.fullmatch(_CURRENCY, unit, re.I):
            currency, unit = unit, ""
        currency = _CURRENCIES.get(currency, currency.upper())
        if currency:
            unit = "currency"
        elif unit in {"%", "percent"}:
            unit = "percent"
        else:
            unit = unit.rstrip("s")
        rates = _nearby(_RATE, text, match.start(), match.end())
        rate_names = {
            _RATE_NAMES.get(name.casefold(), name.casefold())
            for rate in rates
            for name in rate.groups()
            if name
        }
        windows = _nearby(_WINDOW, text, match.start(), match.end())
        quantities.append(
            _Quantity(
                value,
                currency,
                unit,
                _metric(text, match.start(), match.end()),
                "/".join(sorted(rate_names)),
                tuple(
                    date.casefold()
                    for window in windows
                    for date in re.findall(_DATE, window.group(), re.I)
                ),
            )
        )
    return quantities


def supported_quantities(text: str, records: list[MappedRecord]) -> bool:
    """Require every amount to retain its cited sign, magnitude, unit and metric.

    Args:
        text: Untrusted synthesized finding in English.
        records: Only the mappings explicitly cited by that finding.
    Returns:
        Whether every complete numerical expression has matching cited support.
        Scalar observations without quotes use their normalized metric context.
    """
    support = []
    for record in records:
        quoted = [
            quantity for quote in record.quotes for quantity in _quantities(quote.exact)
        ]
        support.extend(quoted)
        if not quoted and record.exact_decimal is not None:
            context = record.numerical_context
            support.append(
                _Quantity(
                    Decimal(record.exact_decimal),
                    context.currency or "" if context else "",
                    context.unit if context and context.unit != "count" else "",
                    _metric(record.concept.replace("_", " "), 0, 0),
                    "",
                    tuple(
                        date.isoformat()
                        for date in (
                            context.measurement_start,
                            context.measurement_end,
                            context.measurement_instant,
                        )
                        if date
                    )
                    if context
                    else (),
                )
            )
    return all(
        any(
            quantity.value == candidate.value
            and quantity.currency == candidate.currency
            and quantity.unit == candidate.unit
            and quantity.rate == candidate.rate
            and quantity.window == candidate.window
            and (not quantity.metric or quantity.metric == candidate.metric)
            for candidate in support
        )
        for quantity in _quantities(text)
    )
