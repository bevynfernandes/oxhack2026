"""Regenerate the committed C2 JSON Schemas from their Python contracts."""

from pathlib import Path

import orjson

from oxhack2026.evaluation.contracts import (
    EvaluationReport,
    EvidenceItem,
    OutcomeDiagnostics,
    RankedCandidate,
    ShortlistScore,
)
from oxhack2026.models.company_assessments import CompanyAssessment
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.contracts import (
    FeatureManifest,
    FeatureRow,
    ForecastManifest,
    ForecastResult,
    LabelRow,
    MatureOutcome,
    ModelReference,
)

if __name__ == "__main__":
    for contract in (
        FeatureRow,
        LabelRow,
        FeatureManifest,
        ModelReference,
        ForecastManifest,
        ForecastResult,
        MatureOutcome,
        EvaluationReport,
        EvidenceItem,
        OutcomeDiagnostics,
        RankedCandidate,
        ShortlistScore,
        CompanyOutcomeLabel,
        CompanyAssessment,
    ):
        destination = Path(__file__).with_name(f"{contract.__name__}.schema.json")
        destination.write_bytes(
            orjson.dumps(contract.model_json_schema(), option=orjson.OPT_INDENT_2)
            + b"\n"
        )
