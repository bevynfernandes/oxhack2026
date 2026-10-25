"""Digest-verified experimental dimension overlays for saved company sources."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from math import log, log1p
from pathlib import Path
from typing import Annotated, Literal, Self, cast
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, Field, model_validator

from oxhack2026.catalog.company import CompanySourceSnapshot, IntegerValue
from oxhack2026.catalog.schemas import Identifier, UtcInstant
from oxhack2026.features.company_policy import company_metric_state
from oxhack2026.models.contracts import Contract
from oxhack2026.models.public_dimensions import (
    EntitySentimentModel,
    NumericDimensionModel,
    dimension_percentile,
    entity_context,
    predict_entity_sentiment,
    predict_numeric_dimension,
)
from oxhack2026.models.public_training import public_dimension_recipes
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS, SpecialistGroupId

DEFAULT_DIMENSION_MODEL_ROOT = (
    Path(__file__).with_name("bundled") / "public_dimensions_v1"
)


class DimensionModelView(Contract):
    """A trained proxy's availability, company eligibility and optional index.

    Attributes:
        group_id: The dimension represented by this independent proxy model.
        model_status: Actual verified weights exist; this is not outcome validation.
        architecture: The portable baseline or validation-recommended comparator.
        target: Plain-language target, distinct from the three company forecasts.
        model_sha256: Exact fitted artifact digest, without local storage paths.
        eligibility: Whether this company's inputs support experimental inference.
        score: Descriptive proxy percentile or text valence, never success probability.
        predicted_value: Model output in the explicitly named transformed units.
        prediction_unit: Units of the raw proxy prediction.
        metric_observation_ids: Exact source inputs consumed by this inference.
        evidence_ids: Exact text excerpts used for sentiment inference.
        sample_size: Number of distinct source titles classified, when applicable.
        reason_codes: Missingness, applicability and experimental-quality reasons.
        limitations: Training population and quality restrictions.
    Raises:
        ValueError: An unavailable model carries a score or a prediction is partial.
    """

    group_id: SpecialistGroupId
    model_status: Literal["experimental_trained"] = "experimental_trained"
    architecture: str
    target: str
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    eligibility: Literal[
        "eligible", "insufficient_data", "not_applicable", "unreliable"
    ]
    score: Annotated[float, Field(ge=0, le=100)] | None = None
    predicted_value: float | None = None
    prediction_unit: str | None = None
    metric_observation_ids: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] | None = Field(
        default=None, exclude_if=lambda value: not value
    )
    sample_size: Annotated[int, Field(gt=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    reason_codes: tuple[Identifier, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_prediction(self) -> Self:
        complete = all(
            value is not None
            for value in (self.score, self.predicted_value, self.prediction_unit)
        )
        absent = all(
            value is None
            for value in (self.score, self.predicted_value, self.prediction_unit)
        )
        if (self.eligibility == "eligible" and not complete) or (
            self.eligibility != "eligible" and not absent
        ):
            message = "Experimental predictions require complete eligible inputs"
            raise ValueError(message)
        if self.eligibility == "eligible" and not (
            self.metric_observation_ids or self.evidence_ids
        ):
            message = "Experimental inference requires exact source observations"
            raise ValueError(message)
        return self


class CompanyDimensionModels(Contract):
    """Current experimental model overlay, separate from immutable assessments.

    Attributes:
        schema_version: Independent proxy-inference contract version.
        company_id: Exact company evaluated from the selected source publication.
        source_snapshot_id: Exact source whose inputs were consumed.
        as_of: Measurement cutoff, not an assertion of historical model availability.
        model_bundle_sha256: Exact training-run manifest used for this overlay.
        dimensions: Five verified trained proxies, each with its own eligibility.
    Raises:
        ValueError: The five dimensions are absent, duplicated or out of order.
    """

    schema_version: Literal["experimental-dimensions-v1"] = "experimental-dimensions-v1"
    company_id: Identifier
    source_snapshot_id: Identifier
    as_of: UtcInstant
    model_bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    dimensions: tuple[DimensionModelView, ...]

    @model_validator(mode="after")
    def _validate_groups(self) -> Self:
        if tuple(row.group_id for row in self.dimensions) != SPECIALIST_GROUP_IDS:
            message = "Experimental overlay requires each dimension in canonical order"
            raise ValueError(message)
        return self


class _Artifact(BaseModel):
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class _Run(BaseModel):
    schema_version: Literal["public-dimension-training-v1"]
    status: Literal["experimental_models_trained"]
    artifacts: dict[SpecialistGroupId, _Artifact]


def _adoption_inputs(
    snapshot: CompanySourceSnapshot, company_id: str
) -> tuple[tuple[float, ...] | None, tuple[str, ...], str]:
    definitions = {row.metric_id: row for row in snapshot.definitions}
    evidence = {row.evidence_id: row for row in snapshot.evidence}
    metrics = [
        row
        for row in snapshot.metrics
        if row.company_id == company_id
        and row.metric_id in {"npm_downloads_30d_v1", "npm_downloads_previous_30d_v1"}
    ]
    if len(metrics) != 2 or len({row.metric_id for row in metrics}) != 2:
        return None, (), "requires_complete_adjacent_npm_windows"
    selected = {row.metric_id: row for row in metrics}
    current = selected["npm_downloads_30d_v1"]
    previous = selected["npm_downloads_previous_30d_v1"]
    packages = []
    for row in (current, previous):
        definition = definitions[row.metric_id]
        if (
            definition.unit != "downloads"
            or definition.value_kind != "integer"
            or definition.scope != "product"
            or definition.currency is not None
            or company_metric_state(row, definition, evidence, snapshot.as_of)
            != "observed"
            or not isinstance(row.value, IntegerValue)
            or row.window is None
            or row.window.end - row.window.start != timedelta(days=30)
        ):
            return None, (), "incompatible_or_unusable_npm_measurements"
        package_names = set()
        for evidence_id in row.evidence_ids:
            item = evidence[evidence_id]
            if item.url is None:
                continue
            parsed = urlsplit(item.url)
            if parsed.hostname == "api.npmjs.org" and parsed.path.startswith(
                "/downloads/range/"
            ):
                package_names.add(unquote(parsed.path.split("/", 4)[-1]))
        if len(package_names) != 1:
            return None, (), "unverified_exact_npm_package"
        packages.append(package_names.pop())
    if (
        packages[0] != packages[1]
        or previous.window is None
        or current.window is None
        or previous.window.end != current.window.start
    ):
        return None, (), "npm_windows_or_package_do_not_match"
    current_value = cast(IntegerValue, current.value).value
    previous_value = cast(IntegerValue, previous.value).value
    if min(current_value, previous_value) < 1000:
        return None, (), "outside_supported_npm_volume"
    current_count, previous_count = current_value, previous_value
    return (
        (
            log1p(current_count),
            log1p(previous_count),
            log((current_count + 1) / (previous_count + 1)),
        ),
        (current.observation_id, previous.observation_id),
        "experimental_sdk_proxy_only",
    )


@dataclass(frozen=True)
class DimensionInputs:
    """Normalized source context passed by saved and fresh research adapters.

    Attributes:
        company_id: Exact verified source identity.
        source_snapshot_id: Source publication or immutable fresh report ID.
        as_of: Source measurement cutoff, distinct from training time.
        adoption: Feature values, observation IDs and eligibility reason.
        sentiment: Entity-marked contexts and their exact source evidence IDs.
    """

    company_id: str
    source_snapshot_id: str
    as_of: datetime
    adoption: tuple[tuple[float, ...] | None, tuple[str, ...], str]
    sentiment: tuple[tuple[str, str], ...] = ()


def _saved_sentiment_inputs(
    snapshot: CompanySourceSnapshot, company_id: str
) -> tuple[tuple[str, str], ...]:
    """Select verified sampled HN titles with exact company-name entity spans.

    Args:
        snapshot: Verified saved source, including the explicit title-sample metric.
        company_id: Company whose titles are being evaluated.
    Returns:
        Deduplicated entity-marked contexts and supporting source IDs, or no inputs
        for synthetic, missing, stale, unverified or inconsistent samples.
    """
    if snapshot.synthetic:
        return ()
    company = next(row for row in snapshot.companies if row.company_id == company_id)
    definition = next(
        (
            row
            for row in snapshot.definitions
            if row.metric_id == "hn_retrieved_named_titles_v1"
        ),
        None,
    )
    observation = next(
        (
            row
            for row in snapshot.metrics
            if row.company_id == company_id
            and row.metric_id == "hn_retrieved_named_titles_v1"
        ),
        None,
    )
    evidence = {row.evidence_id: row for row in snapshot.evidence}
    if (
        definition is None
        or observation is None
        or company_metric_state(observation, definition, evidence, snapshot.as_of)
        != "observed"
        or not isinstance(observation.value, IntegerValue)
        or observation.value.value != len(observation.evidence_ids)
    ):
        return ()
    pattern = re.compile(rf"(?<!\w){re.escape(company.display_name)}(?!\w)", re.I)
    contexts: dict[str, tuple[str, str]] = {}
    for key in observation.evidence_ids:
        source = evidence[key]
        parsed = urlsplit(source.url or "")
        match = pattern.search(source.assertion)
        if (
            source.provider == "hn_algolia"
            and source.kind == "platform_observed"
            and parsed.hostname == "hn.algolia.com"
            and re.fullmatch(r"/api/v1/items/[0-9]+", parsed.path)
            and match is not None
        ):
            contexts.setdefault(
                source.assertion.casefold(),
                (entity_context(source.assertion, match.start(), match.end()), key),
            )
    return tuple(contexts.values())[:30]


@dataclass(frozen=True)
class DimensionModelRegistry:
    """Verified portable models loaded once by the local API runtime.

    Attributes:
        models: All five frozen baseline artifacts; no pickle or training occurs.
        hashes: Exact artifact digests for public provenance.
        bundle_sha256: Digest of the original retained training-run manifest.
    """

    models: dict[SpecialistGroupId, NumericDimensionModel | EntitySentimentModel]
    hashes: dict[SpecialistGroupId, str]
    bundle_sha256: str

    @classmethod
    def load(cls, root: Path) -> Self:
        """Load and verify the complete portable bundle without training libraries.

        Args:
            root: Exact directory containing run.json and five named model files.
        Returns:
            Registry of digest-verified models with frozen target definitions.
        Raises:
            OSError: Artifacts are missing or unreadable.
            ValueError: Manifest, hashes, dimensions or numeric recipes disagree.
        """
        content = (root / "run.json").read_bytes()
        run = _Run.model_validate_json(content)
        if set(run.artifacts) != set(SPECIALIST_GROUP_IDS):
            message = "Dimension bundle must contain all five trained artifacts"
            raise ValueError(message)
        recipes = {row.dimension: row for row in public_dimension_recipes()}
        models: dict[
            SpecialistGroupId, NumericDimensionModel | EntitySentimentModel
        ] = {}
        hashes = {}
        for group in SPECIALIST_GROUP_IDS:
            model_bytes = (root / f"{group}.model.json").read_bytes()
            digest = sha256(model_bytes).hexdigest()
            if digest != run.artifacts[group].model_sha256:
                message = "Dimension artifact failed digest verification"
                raise ValueError(message)
            if group == "attention_sentiment":
                model: NumericDimensionModel | EntitySentimentModel = (
                    EntitySentimentModel.model_validate_json(model_bytes)
                )
            else:
                model = NumericDimensionModel.model_validate_json(model_bytes)
                if model.recipe != recipes[group]:
                    message = "Dimension model disagrees with the inference recipe"
                    raise ValueError(message)
            models[group], hashes[group] = model, digest
        return cls(models, hashes, sha256(content).hexdigest())

    def evaluate(
        self, snapshot: CompanySourceSnapshot, company_id: str
    ) -> CompanyDimensionModels:
        """Evaluate a verified saved source, excluding synthetic input scores.

        Args:
            snapshot: Exact source publication with validated observations.
            company_id: Exact company present in that publication.
        Returns:
            Trained model states and eligible experimental SDK inference.
        Raises:
            ValueError: Company is absent or input/model validation fails.
        """
        if company_id not in {row.company_id for row in snapshot.companies}:
            message = "Company is absent from the dimension input source"
            raise ValueError(message)
        adoption = (
            (None, (), "synthetic_source_not_eligible")
            if snapshot.synthetic
            else _adoption_inputs(snapshot, company_id)
        )
        return self.evaluate_inputs(
            DimensionInputs(
                company_id,
                snapshot.snapshot_id,
                snapshot.as_of,
                adoption,
                _saved_sentiment_inputs(snapshot, company_id),
            )
        )

    def evaluate_inputs(self, inputs: "DimensionInputs") -> CompanyDimensionModels:
        """Apply frozen proxies to normalized, provenance-checked source inputs.

        Args:
            inputs: Saved or fresh source context and eligible SDK feature values.
        Returns:
            All trained states, exact consumed inputs and quality restrictions.
        Raises:
            ValueError: Input values or resulting view violate model contracts.
        """
        views = []
        for group in SPECIALIST_GROUP_IDS:
            model = self.models[group]
            if isinstance(model, EntitySentimentModel):
                probabilities = predict_entity_sentiment(
                    model, tuple(context for context, _ in inputs.sentiment)
                )
                balance = (
                    sum(row["Positive"] - row["Negative"] for row in probabilities)
                    / len(probabilities)
                    if probabilities
                    else None
                )
                views.append(
                    DimensionModelView(
                        group_id=group,
                        architecture="TF-IDF and logistic regression",
                        target=(
                            "Sentiment toward the named company "
                            "in retrieved story titles"
                        ),
                        model_sha256=self.hashes[group],
                        eligibility="eligible"
                        if probabilities
                        else "insufficient_data",
                        score=50 * (1 + balance) if balance is not None else None,
                        predicted_value=balance,
                        prediction_unit="mean positive-minus-negative model probability"
                        if probabilities
                        else None,
                        evidence_ids=tuple(
                            dict.fromkeys(key for _, key in inputs.sentiment)
                        ),
                        sample_size=len(probabilities) or None,
                        reason_codes=("experimental_financial_news_to_title_transfer",)
                        if probabilities
                        else ("requires_validated_company_text_and_entity_spans",),
                        limitations=(
                            *model.limitations,
                            (
                                "Financial-news model applied to retrieved HN titles; "
                                "domain transfer is unvalidated."
                            ),
                            (
                                "Selected titles are not representative public "
                                "sentiment or business performance."
                            ),
                            "Negative recall was 1/11; do not use for risk screening.",
                        ),
                    )
                )
                continue
            eligibility: Literal[
                "eligible", "insufficient_data", "not_applicable", "unreliable"
            ] = "insufficient_data"
            reason = "requires_complete_matching_peer_cohort"
            target = "Next-30-day SDK share change within a fixed technical peer cohort"
            score: float | None = None
            prediction: float | None = None
            unit: str | None = None
            identifiers: tuple[str, ...] = ()
            if group == "team_execution":
                eligibility, reason = "unreliable", "heldout_execution_benchmark_failed"
                target = "Published stable GitHub releases in the next 90 days"
            elif group == "financial_health":
                eligibility, reason = (
                    "not_applicable",
                    "public_issuer_model_not_validated_for_private_startups",
                )
                target = (
                    "Next annual operating cash flow relative to revenue "
                    "for public software issuers"
                )
            elif group == "adoption_retention":
                target = (
                    "SDK download growth over the next 30 days, not customer retention"
                )
                values, identifiers, reason = inputs.adoption
                if values is not None:
                    prediction = predict_numeric_dimension(model, values)
                    score = dimension_percentile(model, prediction)
                    unit = "log download growth"
                    eligibility = "eligible"
            views.append(
                DimensionModelView(
                    group_id=group,
                    architecture="Ridge regression"
                    if model.recommended_predictor == "ridge"
                    else "Persistence baseline; trained Ridge challenger",
                    target=target,
                    model_sha256=self.hashes[group],
                    eligibility=eligibility,
                    score=score,
                    predicted_value=prediction,
                    prediction_unit=unit,
                    metric_observation_ids=identifiers,
                    reason_codes=(reason,),
                    limitations=(
                        *model.recipe.limitations,
                        (
                            "Experimental reconstructed benchmark; "
                            "not a validated company-success forecast."
                        ),
                    ),
                )
            )
        return CompanyDimensionModels(
            company_id=inputs.company_id,
            source_snapshot_id=inputs.source_snapshot_id,
            as_of=inputs.as_of,
            model_bundle_sha256=self.bundle_sha256,
            dimensions=tuple(views),
        )
