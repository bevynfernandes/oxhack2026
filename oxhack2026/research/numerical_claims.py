"""Conservative decimal parsing of explicit attributed quantities and periods."""

import re
from datetime import date
from decimal import Decimal
from typing import Literal

from babel.core import UnknownLocaleError
from babel.numbers import NumberFormatError, parse_decimal

from oxhack2026.api.evidence_mapping_schemas import NumericalContext

_NUMBER = r"(?<![\w.,])-?\d(?:[\d.,\u00a0\u202f ]*\d)?"
_MONEY = re.compile(
    rf"\b(USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY)\s*({_NUMBER})"
    r"\s*(million|millions|millionen|millones|billion|thousand|m|bn|k)?\b",
    re.IGNORECASE,
)
_PERCENT = re.compile(rf"({_NUMBER})\s*(?:%|percent\b|pour cent\b)", re.I)
_COUNT = re.compile(
    rf"({_NUMBER})\s+(?:paying |active )?(?:users|customers|employees|subscribers)\b",
    re.I,
)


def normalize_quantity(text: str, language: str) -> NumericalContext | None:
    """Parse one explicitly unit-bearing quantity; abstain on ambiguous formats.

    Args:
        text: Exact attributed source quote, never model-generated paraphrase.
        language: Declared locale; unknown locales cannot disambiguate separators.
    Returns:
        Decimal quantity and explicit source dates, or None for ambiguous expressions.
        A missing period remains missing and cannot establish current metric readiness.
    """
    money = list(_MONEY.finditer(text))
    percentages = list(_PERCENT.finditer(text))
    counts = list(_COUNT.finditer(text))
    matches = [*money, *percentages, *counts]
    if re.search(r"[\u066b\u066c\u2212]", text):
        return None
    without_dates = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", text)
    if len(matches) != 1 or re.search(
        r"\bbetween\b|\bto\s+\d|\d\s*[-\u2013]\s*\d", without_dates
    ):
        return None
    match = matches[0]
    number = match.group(2) if money else match.group(1)
    if language == "und" and any(separator in number for separator in (",", ".")):
        return None
    locale = language.replace("-", "_") if language != "und" else "en"
    try:
        amount = parse_decimal(number.strip(), locale=locale, strict=True)
    except (NumberFormatError, ValueError, UnknownLocaleError):
        return None
    if counts and amount < 0:
        return None
    multiplier = _multiplier(match.group(3) or "", language) if money else Decimal(1)
    if multiplier is None:
        return None
    amount *= multiplier
    qualifier = _qualifier(text[max(0, match.start() - 25) : match.start()])
    return _dated_context(
        text,
        NumericalContext(
            value_decimal=format(amount, "f"),
            unit="currency" if money else "percent" if percentages else "count",
            currency=match.group(1).upper() if money else None,
            qualifier=qualifier,
        ),
    )


def _multiplier(suffix: str, language: str) -> Decimal | None:
    suffix = suffix.lower()
    if suffix in {"million", "millions", "millionen", "millones", "m"}:
        return Decimal(1_000_000)
    if suffix in {"billion", "bn"}:
        return Decimal(1_000_000_000) if language.startswith("en") else None
    if suffix in {"thousand", "k"}:
        return Decimal(1000)
    return Decimal(1)


def _qualifier(
    prefix: str,
) -> Literal["exact", "approximate", "lower_bound", "upper_bound"]:
    if re.search(r"over|more than|at least|plus de|mehr als", prefix, re.I):
        return "lower_bound"
    if re.search(r"under|less than|at most|moins de|weniger als", prefix, re.I):
        return "upper_bound"
    if re.search(r"about|approximately|around|environ|etwa", prefix, re.I):
        return "approximate"
    return "exact"


def _dated_context(text: str, context: NumericalContext) -> NumericalContext | None:
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    start = end = instant = None
    try:
        if len(dates) == 2 and re.search(r"from|between|period|du|von", text, re.I):
            start, end = map(date.fromisoformat, dates)
            if end < start:
                return None
        elif len(dates) == 1 and re.search(r"as of|on|au|zum", text, re.I):
            instant = date.fromisoformat(dates[0])
    except ValueError:
        return None
    return context.model_copy(
        update={
            "measurement_start": start,
            "measurement_end": end,
            "measurement_instant": instant,
        }
    )
