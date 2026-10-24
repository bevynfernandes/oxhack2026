"""Lightweight experimental company predictions; public serving remains gated."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from oxhack2026.features.company_outcomes import COMPANY_OUTCOME_IDS, CompanyOutcomeId
from oxhack2026.features.definitions import require_utc


@dataclass(frozen=True)
class CompanyProbabilityForecast:
    """One experimental probability; this is not a public serving publication.

    Attributes:
        company_id: Stable identity for an exact company/origin join.
        outcome_id: One separately evaluated company endpoint.
        decision_at: UTC decision time used by the frozen experiment.
        probability: Finite probability in [0, 1], never an arbitrary success score.

    Chronological model fitting, source lineage and historical cohort validation
    are caller responsibilities. This lightweight metric input cannot prove them.
    """

    company_id: str
    outcome_id: CompanyOutcomeId
    decision_at: datetime
    probability: float

    def __post_init__(self) -> None:
        """Validate identity, endpoint, UTC time and bounded finite probability.

        Returns:
            None when this experimental input is valid.
        Raises:
            ValueError: An identity, endpoint, decision time or probability is invalid.
        """
        require_utc(self.decision_at)
        if not self.company_id or self.outcome_id not in COMPANY_OUTCOME_IDS:
            message = "Experimental probability requires company and outcome identity"
            raise ValueError(message)
        if (
            isinstance(self.probability, bool)
            or not isfinite(self.probability)
            or not 0 <= self.probability <= 1
        ):
            message = "Experimental probability must be finite and within [0, 1]"
            raise ValueError(message)
