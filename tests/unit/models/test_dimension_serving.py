"""Experimental registry availability is independent of company input eligibility."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock, patch

import orjson
import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.models.dimension_serving import (
    DimensionInputs,
    DimensionModelRegistry,
    DimensionModelView,
)
from oxhack2026.models.public_dimensions import (
    EntitySentimentModel,
    NumericDimensionModel,
)
from oxhack2026.models.public_training import public_dimension_recipes
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS, SpecialistGroupId


@pytest.fixture
def registry() -> DimensionModelRegistry:
    """Use tiny test parameters, without accessing model storage or training."""
    models: dict[SpecialistGroupId, NumericDimensionModel | EntitySentimentModel] = {
        recipe.dimension: NumericDimensionModel(
            recipe=recipe,
            alpha=1,
            means=(0,) * len(recipe.feature_names),
            scales=(1,) * len(recipe.feature_names),
            coefficients=(0,) * len(recipe.feature_names),
            intercept=0,
            reference_targets=(-1, 0, 1),
            source_sha256="a" * 64,
            training_subjects=("test",),
        )
        for recipe in public_dimension_recipes()
    }
    models["attention_sentiment"] = EntitySentimentModel(
        classes=("Negative", "Neutral", "Positive"),
        vocabulary={"test": 0},
        idf=(1,),
        coefficients=((0,), (0,), (0,)),
        intercepts=(0, 0, 0),
        source_sha256="a" * 64,
        limitations=("Synthetic test parameters",),
    )
    return DimensionModelRegistry(
        models, dict.fromkeys(SPECIALIST_GROUP_IDS, "a" * 64), "b" * 64
    )


def test_registry_verifies_each_artifact_before_loading(
    registry: DimensionModelRegistry,
) -> None:
    """Portable model bytes must match the manifest rather than just file names."""
    content = {
        f"{name}.model.json": model.model_dump_json().encode()
        for name, model in registry.models.items()
    }
    content["run.json"] = orjson.dumps(
        {
            "schema_version": "public-dimension-training-v1",
            "status": "experimental_models_trained",
            "artifacts": {
                name: {"model_sha256": sha256(raw).hexdigest()}
                for name in SPECIALIST_GROUP_IDS
                if (raw := content[f"{name}.model.json"])
            },
        }
    )
    with patch.object(
        Path, "read_bytes", autospec=True, side_effect=lambda path: content[path.name]
    ):
        loaded = DimensionModelRegistry.load(Path("mock"))
    assert loaded.models == registry.models
    content["adoption_retention.model.json"] = b"tampered"
    with (
        patch.object(
            Path,
            "read_bytes",
            autospec=True,
            side_effect=lambda path: content[path.name],
        ),
        pytest.raises(ValueError, match="digest"),
    ):
        DimensionModelRegistry.load(Path("mock"))


def test_inference_exposes_five_trained_states_but_only_supported_score(
    registry: DimensionModelRegistry,
) -> None:
    """Missing inputs and failed validation cannot masquerade as predictions."""
    result = registry.evaluate_inputs(
        DimensionInputs(
            "test",
            "source",
            datetime(2026, 10, 24, tzinfo=UTC),
            ((1, 1, 0), ("current", "previous"), "experimental_sdk_proxy_only"),
        )
    )
    assert len(result.dimensions) == 5
    assert all(row.model_status == "experimental_trained" for row in result.dimensions)
    assert result.dimensions[0].score == 50
    assert all(row.score is None for row in result.dimensions[1:])
    assert result.dimensions[-1].eligibility == "unreliable"
    assert result.dimensions[2].eligibility == "not_applicable"
    with pytest.raises(ValueError, match="eligible"):
        DimensionModelView.model_validate(
            result.dimensions[0].model_dump() | {"eligibility": "insufficient_data"}
        )


def test_synthetic_saved_sources_never_receive_real_model_scores(
    registry: DimensionModelRegistry,
) -> None:
    """Fixtures keep trained artifact status but abstain from numerical inference."""
    path = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"
    source = CompanySourceSnapshot.model_validate_json(path.read_bytes())
    result = registry.evaluate(source, "alpha")
    assert result.dimensions[0].score is None
    assert result.dimensions[0].reason_codes == ("synthetic_source_not_eligible",)
    with pytest.raises(ValueError, match="absent"):
        registry.evaluate(source, "unknown")


def test_fresh_research_adapter_requires_matching_complete_windows() -> None:
    """Fresh npm observations use the same two counts and transformation as training."""
    from datetime import timedelta

    from oxhack2026.api.research_v2_schemas import Job
    from oxhack2026.models.startup_outlook import StartupOutlook
    from oxhack2026.research.composition import _dimension_inputs

    end = datetime(2026, 10, 24, tzinfo=UTC)
    previous = Mock(
        metric_id="npm_downloads_previous_30d",
        value=2000,
        unit="downloads",
        window=Mock(start=end - timedelta(days=60), end=end - timedelta(days=30)),
        evidence_ids=("npm",),
        missing_reason=None,
        observation_id="previous",
    )
    current = Mock(
        metric_id="npm_downloads_latest_30d",
        value=3000,
        unit="downloads",
        window=Mock(start=end - timedelta(days=30), end=end),
        evidence_ids=("npm",),
        missing_reason=None,
        observation_id="current",
    )
    job = Mock(
        spec=Job,
        sources=(
            Mock(
                observations=(previous, current),
                evidence=(
                    Mock(
                        evidence_id="npm",
                        url="https://api.npmjs.org/downloads/range/2026-08-25:2026-10-23/test-sdk",
                    ),
                ),
            ),
        ),
    )
    outlook = Mock(
        spec=StartupOutlook, company_id="test", source_snapshot_id="fresh", as_of=end
    )
    result = _dimension_inputs(job, outlook)
    assert result.adoption[0] is not None
    assert result.adoption[1] == ("current", "previous")
    current.missing_reason = "incomplete_daily_window"
    assert _dimension_inputs(job, outlook).adoption[0] is None
    current.missing_reason = None
    second_previous = Mock(
        metric_id=previous.metric_id,
        value=5000,
        unit="downloads",
        window=previous.window,
        evidence_ids=("second",),
        missing_reason=None,
        observation_id="second_previous",
    )
    second_current = Mock(
        metric_id=current.metric_id,
        value=6000,
        unit="downloads",
        window=current.window,
        evidence_ids=("second",),
        missing_reason=None,
        observation_id="second_current",
    )
    source = job.sources[0]
    source.observations = (*source.observations, second_previous, second_current)
    source.evidence = (
        *source.evidence,
        Mock(
            evidence_id="second",
            url="https://api.npmjs.org/downloads/range/2026-08-25:2026-10-23/other-sdk",
        ),
    )
    assert _dimension_inputs(job, outlook).adoption[1] == (
        "second_current",
        "second_previous",
    )
