"""Offline training of public-data dimension proxies and the descriptive index."""

from datetime import date
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import orjson
from pydantic import TypeAdapter

from oxhack2026.models.dimension_datasets import (
    build_financial_dataset,
    build_sdk_datasets,
)
from oxhack2026.models.public_dimensions import (
    AnnotatedNews,
    NumericRecipe,
    fit_entity_sentiment,
    fit_numeric_dimension,
)
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS


def public_dimension_recipes() -> tuple[NumericRecipe, ...]:
    """Return predeclared targets, features, periods and limitations for four proxies.

    Returns:
        Fixed numeric experiment definitions; these are not survival/utility labels.
    """
    shared = {
        "train_end": date(2023, 6, 30),
        "validation_end": date(2024, 6, 30),
        "test_end": date(2025, 12, 31),
    }
    sdk_limitations = (
        "Current commercial SDK cohort has survivor and developer-tool selection bias.",
        "Reconstructed current API captures do not prove historical availability.",
        "SDK activity is not paying-customer retention, revenue or company survival.",
        "Public SDK projects; historical legal ownership families are unverified.",
    )
    return (
        NumericRecipe(
            dimension="adoption_retention",
            target="log((next_30d_sdk_downloads + 1) / (current_30d_downloads + 1))",
            feature_names=(
                "log1p_current_30d",
                "log1p_previous_30d",
                "previous_log_growth",
            ),
            baseline_index=2,
            limitations=sdk_limitations,
            **shared,
        ),
        NumericRecipe(
            dimension="industry_competition",
            target=(
                "Next-30-day change in log SDK download share "
                "of the frozen technical peer cohort"
            ),
            feature_names=(
                "log1p_current_30d",
                "log1p_previous_30d",
                "previous_log_growth",
                "log1p_other_peers_current_30d",
                "log1p_other_peers_previous_30d",
                "peer_log_growth",
                "previous_log_share_change",
            ),
            baseline_index=6,
            limitations=(
                *sdk_limitations,
                "Technical SDK peer share is not market share or competitive moat.",
                "Inference requires complete, identical audited peer membership.",
            ),
            **shared,
        ),
        NumericRecipe(
            dimension="team_execution",
            target=(
                "log1p(number of published stable GitHub releases in the next 90 days)"
            ),
            feature_names=("log1p_previous_90d_stable_releases",),
            baseline_index=0,
            limitations=(
                *sdk_limitations,
                "Public release cadence measures delivery, not team capability.",
                "Complete pagination required; drafts/prereleases are excluded.",
            ),
            **shared,
        ),
        NumericRecipe(
            dimension="financial_health",
            target=(
                "Next annual asinh(operating cash flow / revenue), "
                "public software issuers only"
            ),
            feature_names=("log1p_revenue_12m_usd", "asinh_operating_cashflow_margin"),
            train_end=date(2019, 12, 31),
            validation_end=date(2022, 12, 31),
            test_end=date(2025, 12, 31),
            baseline_index=1,
            limitations=(
                "Latest restated financials; original filing availability unknown.",
                "Public software issuers; not validated for early private companies.",
                "Cash-generation proxy, not liquidity, solvency or survival.",
                "Issuer CIKs are disjoint; historical ownership is not audited.",
            ),
        ),
    )


def _source_manifest(root: Path, cohort_path: Path) -> tuple[bytes, str]:
    sources = []
    for metadata_path in sorted(root.rglob("*.capture.json")):
        metadata: dict[str, object] = orjson.loads(metadata_path.read_bytes())
        if metadata.get("error") is not None or metadata.get("status", 200) != 200:
            continue
        raw_path = metadata_path.with_name(
            metadata_path.name.removesuffix(".capture.json")
        )
        if not raw_path.is_file():
            raw_path = raw_path.with_suffix(raw_path.suffix + ".json")
        content = raw_path.read_bytes()
        digest = sha256(content).hexdigest()
        if digest != metadata["sha256"] or len(content) != metadata.get(
            "byte_size", metadata.get("bytes")
        ):
            message = (
                f"Public training capture failed integrity validation: {raw_path.name}"
            )
            raise ValueError(message)
        sources.append({"raw_path": str(raw_path), **metadata})
    manifest = orjson.dumps(
        {
            "schema_version": "public-dimension-sources-v1",
            "cohort_path": str(cohort_path),
            "cohort_sha256": sha256(cohort_path.read_bytes()).hexdigest(),
            "sources": sources,
        },
        option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2,
    )
    return manifest, sha256(manifest).hexdigest()


def train_public_dimension_models(
    root: Path, cohort_path: Path, output: Path
) -> dict[str, object]:
    """Fit all five real-data dimension candidates from retained public captures.

    Args:
        root: Acquired FinEntity, SequelSEC and declared SDK raw-capture directory.
        cohort_path: Frozen SDK cohort, selected before examining model performance.
        output: Retained model, evaluation, source-manifest and index directory.
    Returns:
        Run manifest with exact artifact hashes, source/code lineage and limitations.
        The index is descriptive and equal-weighted at the user's direction; no
        combined success probability or deployment approval is claimed.
    Raises:
        ValueError: Source integrity, schema, feature completeness or support fails.
        OSError: Input reads or retained output writes fail.
    """
    manifest, source_digest = _source_manifest(root, cohort_path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "sources.json").write_bytes(manifest)
    sdk_rows, sdk_audit = build_sdk_datasets(root, cohort_path)
    financial_rows, financial_audit = build_financial_dataset(root)
    artifacts: dict[str, dict[str, str]] = {}
    for recipe in public_dimension_recipes():
        rows = (
            financial_rows
            if recipe.dimension == "financial_health"
            else sdk_rows[recipe.dimension]
        )
        model, evaluation = fit_numeric_dimension(recipe, rows, source_digest)
        evaluation["dataset"] = (
            financial_audit if recipe.dimension == "financial_health" else sdk_audit
        )
        model_bytes = model.model_dump_json().encode()
        evaluation_bytes = orjson.dumps(evaluation, option=orjson.OPT_INDENT_2)
        model_path = output / f"{recipe.dimension}.model.json"
        evaluation_path = output / f"{recipe.dimension}.evaluation.json"
        model_path.write_bytes(model_bytes)
        evaluation_path.write_bytes(evaluation_bytes)
        artifacts[recipe.dimension] = {
            "model_path": str(model_path),
            "model_sha256": sha256(model_bytes).hexdigest(),
            "evaluation_path": str(evaluation_path),
            "evaluation_sha256": sha256(evaluation_bytes).hexdigest(),
        }
    text_bytes = (root / "finentity.json").read_bytes()
    sentiment, evaluation = fit_entity_sentiment(
        TypeAdapter(tuple[AnnotatedNews, ...]).validate_json(text_bytes),
        sha256(text_bytes).hexdigest(),
    )
    model_bytes = sentiment.model_dump_json().encode()
    evaluation_bytes = orjson.dumps(evaluation, option=orjson.OPT_INDENT_2)
    (output / "attention_sentiment.model.json").write_bytes(model_bytes)
    (output / "attention_sentiment.evaluation.json").write_bytes(evaluation_bytes)
    artifacts["attention_sentiment"] = {
        "model_path": str(output / "attention_sentiment.model.json"),
        "model_sha256": sha256(model_bytes).hexdigest(),
        "evaluation_path": str(output / "attention_sentiment.evaluation.json"),
        "evaluation_sha256": sha256(evaluation_bytes).hexdigest(),
    }
    index = {
        "schema_version": "ascore-dimension-index-v1",
        "weights": dict.fromkeys(SPECIALIST_GROUP_IDS, 0.2),
        "numeric_scaling": "Midrank percentile of predicted proxy in training outcomes",
        "sentiment_scaling": "50 * (1 + P(Positive) - P(Negative))",
        "missingness": "Abstain unless all five eligible dimension scores exist",
        "interpretation": "Descriptive index, not company-success probability",
        "validation": "Overall index is not validated against company-health outcomes",
    }
    (output / "ascore.index.json").write_bytes(
        orjson.dumps(index, option=orjson.OPT_INDENT_2)
    )
    run: dict[str, object] = {
        "schema_version": "public-dimension-training-v1",
        "status": "experimental_models_trained",
        "public_serving_approved": False,
        "source_manifest_sha256": source_digest,
        "libraries": {
            name: version(name) for name in ("numpy", "scikit-learn", "polars")
        },
        "code_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                Path(__file__).with_name("public_dimensions.py"),
                Path(__file__).with_name("dimension_datasets.py"),
            )
        },
        "artifacts": artifacts,
        "ascore": index,
    }
    (output / "run.json").write_bytes(orjson.dumps(run, option=orjson.OPT_INDENT_2))
    return run
