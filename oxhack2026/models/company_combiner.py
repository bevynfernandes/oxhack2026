"""Three-period specialist blending with portable, experimental AScore parameters."""

from collections.abc import Sequence
from datetime import datetime
from hashlib import sha256
from math import exp, fsum, log, log1p
from typing import Annotated, Literal, Self
from warnings import catch_warnings, simplefilter

from pydantic import Field, model_validator

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.catalog.schemas import Identifier, UtcInstant
from oxhack2026.evaluation.company_labels import select_company_labels
from oxhack2026.evaluation.company_metrics import (
    CompanyProbabilityEvaluation,
    evaluate_company_probabilities,
)
from oxhack2026.features.company_outcomes import CompanyOutcomeId
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.company_predictions import CompanyProbabilityForecast
from oxhack2026.models.company_training import (
    CompanyExperimentPlan,
    CompanyExperimentResult,
    CompanyLogisticModel,
    predict_company_logistic,
    run_company_experiment,
)
from oxhack2026.models.contracts import Contract
from oxhack2026.models.startup_outlook import SPECIALIST_GROUP_IDS, SpecialistGroupId
from oxhack2026.storage.company import resolve_family

_NonemptyIds = Annotated[tuple[Identifier, ...], Field(min_length=1)]
_Minimum = Annotated[int, Field(strict=True, ge=2)]
_Key = tuple[str, datetime]
_LOGIT_EPSILON = 1e-6


class CompanyCombinerPlan(Contract):
    """Frozen three-way experiment for one endpoint shared by all five groups.

    Attributes:
        experiment_id: Stable experiment identity.
        outcome_id: One exact outcome and horizon, never a mixture of targets.
        group_metrics: Ordered production metric IDs for every specialist.
        base_snapshot_ids: Sources for fitting the five specialists.
        blend_snapshot_ids: Later, family-disjoint sources for fitting the combiner.
        test_snapshot_ids: Final later sources, unused by either fitting stage.
        base_fit_at: Specialists' label-knowledge cutoff, before blend origins.
        fit_at: Combiner's label-knowledge cutoff, before final-test origins.
        evaluated_at: Final-test label cutoff.
        minimum_base_per_class: Distinct families per class for base fitting.
        minimum_blend_per_class: Complete five-group families per class for blending.
        minimum_test_per_class: Complete five-group families per test class.

    Raises:
        ValueError: Groups, identities, partitions or cutoffs are inconsistent.
    """

    experiment_id: Identifier
    outcome_id: CompanyOutcomeId
    group_metrics: dict[SpecialistGroupId, _NonemptyIds]
    base_snapshot_ids: _NonemptyIds
    blend_snapshot_ids: _NonemptyIds
    test_snapshot_ids: _NonemptyIds
    base_fit_at: UtcInstant
    fit_at: UtcInstant
    evaluated_at: UtcInstant
    minimum_base_per_class: _Minimum = 20
    minimum_blend_per_class: _Minimum = 10
    minimum_test_per_class: _Minimum = 10

    @model_validator(mode="after")
    def _validate_plan(self) -> Self:
        identities = (
            self.base_snapshot_ids + self.blend_snapshot_ids + self.test_snapshot_ids
        )
        if (
            set(self.group_metrics) != set(SPECIALIST_GROUP_IDS)
            or any(len(ids) != len(set(ids)) for ids in self.group_metrics.values())
            or len(identities) != len(set(identities))
            or not self.base_fit_at < self.fit_at < self.evaluated_at
        ):
            message = (
                "Combiner requires five groups, disjoint sources and ordered cutoffs"
            )
            raise ValueError(message)
        return self


class CompanyCombinerModel(Contract):
    """Five frozen specialists and logistic weights; AScore is 100 * probability.

    Attributes:
        plan: Frozen outcome, periods, group order and support requirements.
        algorithm_version: Fixed held-out logit blending and clipping recipe.
        specialists: Models in SPECIALIST_GROUP_IDS order, never refitted on blend.
        training_sha256: Digest of specialist parameters and selected blending truth.
        means: Train-only means of the five clipped specialist logits.
        scales: Train-only positive standard deviations, with constants set to one.
        coefficients: Standardized logit weights in SPECIALIST_GROUP_IDS order.
        intercept: Combiner log-odds intercept.
        training_prevalence: Prevalence on exactly the complete blending rows.

    Raises:
        ValueError: Model lineage, group order or coefficient dimensions disagree.
    """

    plan: CompanyCombinerPlan
    algorithm_version: Literal["company-heldout-logit-blend-v1"] = (
        "company-heldout-logit-blend-v1"
    )
    specialists: tuple[CompanyLogisticModel, ...]
    training_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    training_prevalence: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def _validate_parameters(self) -> Self:
        if (
            tuple(row.plan.group_id for row in self.specialists) != SPECIALIST_GROUP_IDS
            or any(
                row.plan.outcome_id != self.plan.outcome_id
                or row.plan.fit_at != self.plan.base_fit_at
                or row.plan.train_snapshot_ids != self.plan.base_snapshot_ids
                or row.plan.test_snapshot_ids != self.plan.blend_snapshot_ids
                or row.plan.metric_ids != self.plan.group_metrics[row.plan.group_id]
                for row in self.specialists
            )
            or any(
                len(values) != len(SPECIALIST_GROUP_IDS)
                for values in (self.means, self.scales, self.coefficients)
            )
            or any(value <= 0 for value in self.scales)
        ):
            message = "Combiner parameters must match frozen five-group model lineage"
            raise ValueError(message)
        return self


class CompanyCombinerResult(Contract):
    """Experimental combined-model result with coverage and matched comparators.

    Attributes:
        plan: Exact experiment declaration.
        status: Blocked without a combiner, or experimental after fitting.
        reasons: Failed gates or remaining public-release limitations.
        counts: Complete-row counts, family support and abstentions.
        specialist_results: Retained base-model experiments and source lineage.
        model: Portable fitted model, absent if any fitting gate fails.
        test_metrics: Named combiner, prevalence and five specialist comparisons on
            identical complete final-test rows, with abstention counts retained.
    """

    plan: CompanyCombinerPlan
    status: Literal["blocked", "experimental"]
    reasons: tuple[str, ...]
    counts: dict[str, int]
    specialist_results: tuple[CompanyExperimentResult, ...] = ()
    model: CompanyCombinerModel | None = None
    test_metrics: dict[str, CompanyProbabilityEvaluation] = Field(default_factory=dict)


def _logit(probability: float) -> float:
    clipped = max(_LOGIT_EPSILON, min(1 - _LOGIT_EPSILON, probability))
    return log(clipped) - log1p(-clipped)


def _vectors(
    models: Sequence[CompanyLogisticModel], sources: Sequence[CompanySourceSnapshot]
) -> dict[_Key, tuple[float, ...]]:
    forecasts = [
        {
            (row.company_id, row.decision_at): row.probability
            for source in sources
            for row in predict_company_logistic(model, source)
        }
        for model in models
    ]
    complete = set.intersection(*(set(rows) for rows in forecasts))
    return {key: tuple(rows[key] for rows in forecasts) for key in sorted(complete)}


def _partitions(
    plan: CompanyCombinerPlan, snapshots: Sequence[CompanySourceSnapshot]
) -> tuple[tuple[CompanySourceSnapshot, ...], ...]:
    sources = {row.snapshot_id: row for row in snapshots}
    partitions = (
        plan.base_snapshot_ids,
        plan.blend_snapshot_ids,
        plan.test_snapshot_ids,
    )
    if len(sources) != len(snapshots) or set(sources) != {
        identity for partition in partitions for identity in partition
    }:
        message = "Supply exactly the unique sources frozen in the combiner plan"
        raise ValueError(message)
    result = tuple(tuple(sources[key] for key in ids) for ids in partitions)
    seen_companies: set[str] = set()
    seen_families: set[str] = set()
    for index, partition in enumerate(result):
        companies = {row.company_id for source in partition for row in source.companies}
        origins = [
            (company.company_id, source.as_of)
            for source in partition
            for company in source.companies
        ]
        families = {
            family.family_id
            for source in partition
            for company in source.companies
            if (
                family := resolve_family(
                    source, company.company_id, source.as_of, public_only=True
                )
            ).family_id
            is not None
        }
        lower = (None, plan.base_fit_at, plan.fit_at)[index]
        upper = (plan.base_fit_at, plan.fit_at, plan.evaluated_at)[index]
        if (
            companies & seen_companies
            or families & seen_families
            or len(origins) != len(set(origins))
            or any(
                source.as_of >= upper or (lower is not None and source.as_of < lower)
                for source in partition
            )
        ):
            message = (
                "Combiner periods must be chronological and company/family disjoint"
            )
            raise ValueError(message)
        seen_companies.update(companies)
        seen_families.update(families)
    return result


def _selected_labels(
    plan: CompanyCombinerPlan,
    sources: Sequence[CompanySourceSnapshot],
    labels: Sequence[CompanyOutcomeLabel],
    cutoff: datetime,
) -> tuple[CompanyOutcomeLabel, ...]:
    families = {
        (company.company_id, source.as_of): resolve_family(
            source, company.company_id, source.as_of, public_only=True
        ).family_id
        for source in sources
        for company in source.companies
    }
    scoped = [
        row
        for row in labels
        if row.outcome_id == plan.outcome_id
        and (row.company_id, row.decision_at) in families
    ]
    if any(
        row.family_id != families[(row.company_id, row.decision_at)] for row in scoped
    ):
        message = "Combiner label family conflicts with dated public source resolution"
        raise ValueError(message)
    return select_company_labels(scoped, plan.outcome_id, cutoff).labels


def _fit_combiner(
    plan: CompanyCombinerPlan,
    models: tuple[CompanyLogisticModel, ...],
    vectors: dict[_Key, tuple[float, ...]],
    labels: Sequence[CompanyOutcomeLabel],
) -> CompanyCombinerModel:
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]
    from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
    from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

    matrix = np.array(
        [
            [_logit(value) for value in vectors[(row.company_id, row.decision_at)]]
            for row in labels
        ]
    )
    truth = np.array([row.value for row in labels], dtype=np.int64)
    scaler = StandardScaler()
    features = scaler.fit_transform(matrix)
    with catch_warnings():
        simplefilter("error", ConvergenceWarning)
        classifier = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
        classifier.fit(features, truth)
    digest = sha256()
    for model in models:
        digest.update(model.model_dump_json().encode())
    for row in labels:
        digest.update(row.model_dump_json().encode())
        digest.update(np.array(vectors[(row.company_id, row.decision_at)]).tobytes())
    return CompanyCombinerModel(
        plan=plan,
        specialists=models,
        training_sha256=digest.hexdigest(),
        means=tuple(scaler.mean_.tolist()),
        scales=tuple(scaler.scale_.tolist()),
        coefficients=tuple(classifier.coef_[0].tolist()),
        intercept=float(classifier.intercept_[0]),
        training_prevalence=float(truth.mean()),
    )


def predict_company_combiner(
    model: CompanyCombinerModel, snapshot: CompanySourceSnapshot
) -> tuple[CompanyProbabilityForecast, ...]:
    """Predict the shared endpoint; the experimental AScore is 100 * probability.

    Args:
        model: Frozen specialists and combiner, loaded from portable JSON.
        snapshot: Verified real source at/after combiner fitting.
    Returns:
        Probabilities only for companies with predictions from all five groups.
        Missing groups abstain; no default score or weight renormalization is used.
    Raises:
        ValueError: Source predates fitting, is synthetic or changes metric definitions.
    """
    if snapshot.as_of < model.plan.fit_at:
        message = "Combined prediction cannot precede combiner fitting"
        raise ValueError(message)
    forecasts = []
    for (company_id, decision_at), values in _vectors(
        model.specialists, (snapshot,)
    ).items():
        log_odds = model.intercept + fsum(
            weight * ((_logit(value) - mean) / scale)
            for value, mean, scale, weight in zip(
                values, model.means, model.scales, model.coefficients, strict=True
            )
        )
        probability = (
            1 / (1 + exp(-log_odds))
            if log_odds >= 0
            else exp(log_odds) / (1 + exp(log_odds))
        )
        forecasts.append(
            CompanyProbabilityForecast(
                company_id, model.plan.outcome_id, decision_at, probability
            )
        )
    return tuple(forecasts)


def run_company_combiner(
    plan: CompanyCombinerPlan,
    snapshots: Sequence[CompanySourceSnapshot],
    labels: Sequence[CompanyOutcomeLabel],
) -> CompanyCombinerResult:
    """Fit specialists, blend later held-out predictions, then evaluate untouched test.

    Args:
        plan: Predeclared three-period, five-group, single-endpoint experiment.
        snapshots: Exact source publications; caller verifies raw artifact hashes.
        labels: Selected adjudicated vintages; missing truth never becomes negative.
    Returns:
        Blocked gates or a portable experimental combiner and matched comparisons.
        This holds specialists fixed after base fitting; it is held-out blending,
        not a claim of cross-validated stacking or authorization for public serving.
    Raises:
        ValueError: Source, chronology, company/family, definitions or truth conflict.
        sklearn.exceptions.ConvergenceWarning: Either fitting stage fails to converge.
    """
    base, blend, test = _partitions(plan, snapshots)
    if any(source.synthetic for source in snapshots):
        return CompanyCombinerResult(
            plan=plan,
            status="blocked",
            reasons=("synthetic_sources_forbidden",),
            counts={},
        )
    results = tuple(
        run_company_experiment(
            CompanyExperimentPlan(
                experiment_id=f"{plan.experiment_id}-{group}",
                group_id=group,
                outcome_id=plan.outcome_id,
                metric_ids=plan.group_metrics[group],
                train_snapshot_ids=plan.base_snapshot_ids,
                test_snapshot_ids=plan.blend_snapshot_ids,
                fit_at=plan.base_fit_at,
                evaluated_at=plan.fit_at,
                minimum_train_per_class=plan.minimum_base_per_class,
                minimum_test_per_class=plan.minimum_blend_per_class,
            ),
            (*base, *blend),
            labels,
        )
        for group in SPECIALIST_GROUP_IDS
    )
    models = tuple(result.model for result in results if result.model is not None)
    if len(models) != len(SPECIALIST_GROUP_IDS):
        return CompanyCombinerResult(
            plan=plan,
            status="blocked",
            reasons=("specialist_training_gates_failed",),
            counts={},
            specialist_results=results,
        )
    blend_vectors, test_vectors = _vectors(models, blend), _vectors(models, test)
    blend_labels = _selected_labels(plan, blend, labels, plan.fit_at)
    test_labels = _selected_labels(plan, test, labels, plan.evaluated_at)
    counts = {}
    reasons = []
    for name, vectors, selected, minimum in (
        ("blend", blend_vectors, blend_labels, plan.minimum_blend_per_class),
        ("test", test_vectors, test_labels, plan.minimum_test_per_class),
    ):
        matched = [
            row for row in selected if (row.company_id, row.decision_at) in vectors
        ]
        counts[f"{name}_complete_predictions"] = len(vectors)
        counts[f"{name}_matched_labels"] = len(matched)
        counts[f"{name}_labels_without_complete_prediction"] = len(selected) - len(
            matched
        )
        for truth, state in ((False, "negative"), (True, "positive")):
            count = len({row.family_id for row in matched if row.value is truth})
            counts[f"{name}_{state}_families"] = count
            if count < minimum:
                reasons.append(f"{name}_insufficient_{state}_families")
    if reasons:
        return CompanyCombinerResult(
            plan=plan,
            status="blocked",
            reasons=tuple(reasons),
            counts=counts,
            specialist_results=results,
        )
    model = _fit_combiner(
        plan,
        models,
        blend_vectors,
        [
            row
            for row in blend_labels
            if (row.company_id, row.decision_at) in blend_vectors
        ],
    )
    forecasts = tuple(
        row for source in test for row in predict_company_combiner(model, source)
    )
    comparisons = {
        "combiner": forecasts,
        "prevalence": tuple(
            CompanyProbabilityForecast(
                row.company_id,
                row.outcome_id,
                row.decision_at,
                model.training_prevalence,
            )
            for row in forecasts
        ),
    }
    for index, group in enumerate(SPECIALIST_GROUP_IDS):
        comparisons[group] = tuple(
            CompanyProbabilityForecast(
                company_id, plan.outcome_id, decision_at, values[index]
            )
            for (company_id, decision_at), values in test_vectors.items()
        )
    return CompanyCombinerResult(
        plan=plan,
        status="experimental",
        reasons=(
            "public_release_not_validated",
            "heldout_blending_not_cross_validation",
        ),
        counts=counts,
        specialist_results=results,
        model=model,
        test_metrics={
            name: evaluate_company_probabilities(
                predictions, test_labels, plan.outcome_id, plan.evaluated_at
            )
            for name, predictions in comparisons.items()
        },
    )
