"""Explicit concept ownership and numerical eligibility; no business scoring."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from oxhack2026.api.research_v2_schemas import Observation
from oxhack2026.models.startup_outlook import SpecialistGroupId


@dataclass(frozen=True)
class ConceptRule:
    """A concept's primary dimension and language-independent identifier."""

    concept: str
    group: SpecialistGroupId
    pattern: str


CONCEPTS = (
    ConceptRule(
        "revenue",
        "financial_health",
        r"\brevenue\b|\bchiffre d.affaires\b|\bumsatz\b|\bingresos\b",
    ),
    ConceptRule("arr", "financial_health", r"\bARR\b|annual recurring revenue"),
    ConceptRule(
        "profitability",
        "financial_health",
        r"\bprofitab|\bcash flow\b|\bcashflow\b|\boperating loss\b",
    ),
    ConceptRule(
        "funding",
        "financial_health",
        r"\braised\b|\bfunding\b|\bfinancing\b|\bseries [a-f]\b",
    ),
    ConceptRule(
        "cash",
        "financial_health",
        r"\bcash balance\b|\bcash reserves\b|\bburn rate\b|\brunway\b",
    ),
    ConceptRule(
        "retention", "adoption_retention", r"\bretention\b|\bchurn\b|\brenewal rate\b"
    ),
    ConceptRule(
        "adoption",
        "adoption_retention",
        (
            "\\b(?:paying |active )?(?:customers|users|subscribers)\\b|"
            "\\bdeploy(?:ed|ment)\\b|\\badopt(?:ed|ion)\\b|\\butilisateurs"
            "\\b|\\bnutzer\\b|\\busuarios\\b"
        ),
    ),
    ConceptRule(
        "market_position",
        "industry_competition",
        (
            "\\bcompetitor\\b|\\bmarket share\\b|\\bmarket size\\b|\\bcompet"
            "es\\b|\\balternative to\\b|\\bpositioning\\b"
        ),
    ),
    ConceptRule(
        "product",
        "industry_competition",
        (
            "\\b(?:our|the) (?:platform|product|software)\\b|\\bwe (?:bu"
            "ild|provide|offer|develop)\\b"
        ),
    ),
    ConceptRule(
        "hiring",
        "team_execution",
        r"\bhiring\b|\bopen positions\b|\bjob openings\b|\bwe are looking for\b",
    ),
    ConceptRule(
        "team",
        "team_execution",
        (
            "\\bfound(?:er|ed)\\b|\\bemployees\\b|\\bheadcount\\b|\\bchief e"
            "xecutive\\b|\\bCEO\\b|\\bour team\\b"
        ),
    ),
    ConceptRule(
        "delivery",
        "team_execution",
        r"\breleased\b|\blaunched\b|\bshipped\b|\bgenerally available\b|\bchangelog\b",
    ),
    ConceptRule(
        "coverage",
        "attention_sentiment",
        r"\bfeatured in\b|\bpress coverage\b|\bmedia coverage\b",
    ),
)
CONCEPT_LOOKUP = {rule.concept: rule for rule in CONCEPTS}
_PATTERNS = tuple((rule, re.compile(rule.pattern, re.IGNORECASE)) for rule in CONCEPTS)
_CURRENCY = r"(?:[$€£¥₹₩]|\b(?:USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY)\b)"
_AMOUNT = r"-?\d[\d.,\u00a0\u202f ]*(?:million|billion|thousand|millions|m|bn|k)?"
_MONEY = rf"(?:{_CURRENCY}\s*{_AMOUNT}|{_AMOUNT}\s*{_CURRENCY})"
_PRICE_CONTEXT = re.compile(
    r"\b(?:plans?|prices?|pricing|subscriptions?|billed|billing|costs?|charges?|"
    r"abonnements?|forfaits?|tarifs?|prix|preise?|abos?|tarifas?|suscripciones?)\b|"
    r"\b(?:per|par|pro|a|each)\s+(?:month|year|seat|user|minute|mois|monat)\b|"
    r"/\s*(?:mo|month|yr|year|seat|user|minute)\b",
    re.IGNORECASE,
)
_FINANCIAL_TERMS = (
    "(?:"
    + "|".join(rule.pattern for rule in CONCEPTS if rule.group == "financial_health")
    + r")\w*"
)
_FINANCIAL_CONNECTORS = (
    r"(?:(?:is|are|was|were|has|have|had|reached|reported|grew|rose|fell|"
    r"increased|decreased|totaled|totalled|of|at|to|about|approximately|over|"
    r"under|more|less|than|least|most|est|était|atteint|de|plus|environ|"
    r"betrug|von|etwa|fue|es|alcanzó)\s+){0,8}"
)
_FINANCIAL_ASSERTION = re.compile(
    rf"{_FINANCIAL_TERMS}\s*[:=]?\s*{_FINANCIAL_CONNECTORS}{_MONEY}|"
    rf"{_MONEY}\s+(?:in|of|de)\s+{_FINANCIAL_TERMS}|"
    r"\b(?:is|are|was|were|became|remains?)\s+(?:now\s+)?"
    r"(?:profitable|cash[- ]flow positive)\b",
    re.IGNORECASE,
)
_MONETARY_VALUE = re.compile(_MONEY, re.IGNORECASE)
_FREE_PRICE = re.compile(r"\b(?:free|gratis|gratuit|kostenlos|gratuito)\b", re.I)
METRIC_GROUPS: dict[str, SpecialistGroupId] = {
    "npm_downloads_latest_30d": "adoption_retention",
    "npm_downloads_previous_30d": "adoption_retention",
    "hn_retrieved_exact_domain_records_30d": "attention_sentiment",
    "hn_complete_exact_domain_count_30d": "attention_sentiment",
    "github_stars": "attention_sentiment",
    "github_open_issues": "team_execution",
    "advertised_openings": "team_execution",
    "revenue": "financial_health",
    "retention": "adoption_retention",
    "runway": "financial_health",
    "competitor_coverage": "industry_competition",
}
EVENT_GROUPS: dict[str, SpecialistGroupId] = {
    "hn_exact_domain_story": "attention_sentiment",
    "stable_release": "team_execution",
    "repository_push": "team_execution",
}
METRIC_PROVIDERS = {
    "npm_downloads_latest_30d": "npm",
    "npm_downloads_previous_30d": "npm",
    "hn_retrieved_exact_domain_records_30d": "hn",
    "hn_complete_exact_domain_count_30d": "hn",
    "github_stars": "github",
    "github_open_issues": "github",
    "advertised_openings": "hiring",
}


def classify(text: str) -> ConceptRule | None:
    """Find an explicit concept in a factual proposition, otherwise abstain."""
    if len(text.split()) < 5 or not re.search(
        r"\d|\b(?:is|are|was|were|has|have|had|we|our|provides|offers|uses|"
        r"deployed|raised|released|launched|built|helps|est|sont|ist|sind|es|son)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    rule = next((rule for rule, pattern in _PATTERNS if pattern.search(text)), None)
    if rule and rule.group == "financial_health" and price_only_financial_claim(text):
        return None
    return rule


def price_only_financial_claim(text: str) -> bool:
    """Identify source prices that do not assert actual financial performance.

    Args:
        text: Retained source quote, independent of any model-provided subject.
    Returns:
        Whether pricing language and a monetary/free price lack a supported
        financial assertion. Currency symbols identify a quoted price without
        guessing a normalized currency. Mixed quotes retain explicit financial
        statements; ambiguous financial interpretations remain unmapped.
    """
    monetary = _MONETARY_VALUE.search(text)
    price = _PRICE_CONTEXT.search(text) or _MONETARY_VALUE.fullmatch(
        text.strip().rstrip(".")
    )
    return bool(
        price
        and (monetary or _FREE_PRICE.search(text))
        and not _FINANCIAL_ASSERTION.search(text)
    )


def metric_eligible(row: Observation, as_of: datetime) -> tuple[bool, str]:
    """Apply definition-specific freshness to captured structured platform metrics.

    Args:
        row: Exact source observation, including measurement period and support.
        as_of: Frozen report source cutoff, never the re-mapping clock.
    Returns:
        Eligibility and an explicit quality reason; zero remains a valid value.
    """
    if row.value is None:
        return False, row.missing_reason or "missing_value"
    if row.origin != "fresh" or not row.evidence_ids:
        return False, "unverified_support"
    if row.applicability != "applicable":
        return False, row.applicability
    supported = row.metric_id in METRIC_PROVIDERS
    if not supported:
        return False, "normalization_policy_unavailable"
    instant = row.window.end if row.window else row.collected_at
    days = 14 if row.metric_id == "advertised_openings" else 7
    if instant > as_of or as_of - instant > timedelta(days=days):
        return False, "stale_or_future_measurement"
    if row.metric_id.startswith(("npm_", "hn_")) and row.window is None:
        return False, "missing_measurement_period"
    return True, "validated_platform_measurement"
