"""Reproducible, source-aligned logistic experiments; no public release authority."""

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from hashlib import sha256
from importlib.metadata import version
from math import copysign, exp, fsum, log1p
from typing import Annotated, Literal, Self
from warnings import catch_warnings, simplefilter

from pydantic import Field, model_validator

from oxhack2026.catalog.company import CompanySourceSnapshot, MetricDefinition
from oxhack2026.catalog.schemas import Identifier, UtcInstant
from oxhack2026.evaluation.company_labels import select_company_labels
from oxhack2026.evaluation.company_metrics import (
    CompanyProbabilityEvaluation,
    evaluate_company_probabilities,
)
from oxhack2026.features.company import company_feature_frame
from oxhack2026.features.company_outcomes import CompanyOutcomeId
from oxhack2026.models.company_contracts import CompanyOutcomeLabel
from oxhack2026.models.company_predictions import CompanyProbabilityForecast
from oxhack2026.models.contracts import Contract
from oxhack2026.models.startup_outlook import SpecialistGroupId
from oxhack2026.storage.company import resolve_family


class CompanyExperimentPlan(Contract):
    """Frozen single-group/endpoint experiment, declared before test access.

    Attributes:
        experiment_id: Versioned experiment identity.
        group_id: One specialist; a combined score needs out-of-fold specialist inputs.
        outcome_id: Existing exact label definition; survival is not financing.
        metric_ids: Ordered production metric definitions, never derived targets.
        train_snapshot_ids: Exact source vintages for historical training origins.
        test_snapshot_ids: Later source vintages for a family-disjoint holdout.
        fit_at: Training knowledge cutoff, at or before every test origin.
        evaluated_at: Label cutoff for descriptive held-out metrics.
        minimum_train_per_class: Distinct families required in each training class.
        minimum_test_per_class: Distinct families required in each test class.

    Raises:
        ValueError: Lists duplicate/overlap, times reverse, or features are empty.
    """

    experiment_id: Identifier
    group_id: SpecialistGroupId
    outcome_id: CompanyOutcomeId
    metric_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    train_snapshot_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    test_snapshot_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    fit_at: UtcInstant
    evaluated_at: UtcInstant
    minimum_train_per_class: Annotated[int, Field(strict=True, ge=2)] = 20
    minimum_test_per_class: Annotated[int, Field(strict=True, ge=2)] = 10

    @model_validator(mode="after")
    def _validate_plan(self) -> Self:
        for values in (
            self.metric_ids,
            self.train_snapshot_ids,
            self.test_snapshot_ids,
        ):
            if len(values) != len(set(values)):
                message = "Experiment lists must contain unique identities"
                raise ValueError(message)
        if set(self.train_snapshot_ids) & set(self.test_snapshot_ids):
            message = "Training and test source vintages must be separate"
            raise ValueError(message)
        if self.fit_at >= self.evaluated_at:
            message = "Evaluation must follow the training knowledge cutoff"
            raise ValueError(message)
        return self


class CompanyLogisticModel(Contract):
    """Portable L2 logistic parameters with train-only preprocessing.

    Attributes:
        plan: Exact frozen endpoint, ordered features, sources and cutoffs.
        algorithm_version: Fixed preprocessing, penalty and optimizer recipe.
        sklearn_version: Training library version retained for reproduction.
        definitions: Full production definitions, including units and freshness.
        training_sha256: Digest of exact selected features, labels and source data.
        medians: Train-only medians of sign(x) * log1p(abs(x)).
        means: Train-only means of imputed values followed by missing indicators.
        scales: Train-only positive standard deviations, with constants set to one.
        coefficients: Log-odds coefficients in the same expanded feature order.
        intercept: Unpenalized logistic intercept.
        training_prevalence: Comparator fitted on exactly the same training rows.

    Raises:
        ValueError: Dimensions, feature order or scales are inconsistent.
    """

    plan: CompanyExperimentPlan
    algorithm_version: Literal["company-logistic-signedlog-v1"] = (
        "company-logistic-signedlog-v1"
    )
    sklearn_version: Identifier
    definitions: tuple[MetricDefinition, ...]
    training_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    medians: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    training_prevalence: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def _validate_dimensions(self) -> Self:
        count = len(self.plan.metric_ids)
        if (
            tuple(row.metric_id for row in self.definitions) != self.plan.metric_ids
            or len(self.medians) != count
            or any(
                len(values) != 2 * count
                for values in (self.means, self.scales, self.coefficients)
            )
            or any(scale <= 0 for scale in self.scales)
        ):
            message = "Logistic parameters must match ordered production features"
            raise ValueError(message)
        return self


class CompanyExperimentResult(Contract):
    """Research-only result, including explicit failed training/evaluation gates.

    Attributes:
        plan: Frozen experiment declaration, including the endpoint definition.
        status: Blocked without fitting, or experimental after real-data fitting.
        reasons: Machine-readable blockers or remaining release limitations.
        counts: Eligibility, class, family, missingness and exclusion counts.
        model: Fitted portable parameters only when training gates pass.
        logistic_metrics: Held-out discrimination, loss, calibration and coverage.
        prevalence_metrics: Identical held-out rows scored with training prevalence.
        beats_prevalence: Lower Brier and log loss on supported test data; this
            descriptive comparison alone never grants public serving approval.
    """

    plan: CompanyExperimentPlan
    status: Literal["blocked", "experimental"]
    reasons: tuple[str, ...]
    counts: dict[str, int]
    model: CompanyLogisticModel | None = None
    logistic_metrics: CompanyProbabilityEvaluation | None = None
    prevalence_metrics: CompanyProbabilityEvaluation | None = None
    beats_prevalence: bool | None = None


class _FeatureRow(Contract):
    company_id: str
    family_id: str
    decision_at: UtcInstant
    values: tuple[float | None, ...]


def _project(
    snapshots: Sequence[CompanySourceSnapshot], metric_ids: tuple[str, ...]
) -> tuple[dict[tuple[str, datetime], _FeatureRow], Counter[str]]:
    rows: dict[tuple[str, datetime], _FeatureRow] = {}
    seen: set[tuple[str, datetime]] = set()
    exclusions: Counter[str] = Counter()
    for snapshot in snapshots:
        values: dict[str, dict[str, float | None]] = {}
        frame = company_feature_frame(snapshot)
        for batch in frame.iter_slices(n_rows=10):
            for row in batch.iter_rows(named=True):
                values.setdefault(row["company_id"], {})[row["metric_id"]] = row[
                    "value"
                ]
        for company in snapshot.companies:
            key = (company.company_id, snapshot.as_of)
            if key in seen:
                message = "Select one source vintage per company/origin"
                raise ValueError(message)
            seen.add(key)
            family = resolve_family(
                snapshot, company.company_id, snapshot.as_of, public_only=True
            )
            vector = tuple(
                values.get(company.company_id, {}).get(metric_id)
                for metric_id in metric_ids
            )
            if family.family_id is None:
                exclusions["unresolved_family"] += 1
            elif all(value is None for value in vector):
                exclusions["no_usable_features"] += 1
            else:
                rows[key] = _FeatureRow(
                    company_id=company.company_id,
                    family_id=family.family_id,
                    decision_at=snapshot.as_of,
                    values=vector,
                )
    return rows, exclusions


def _definitions(
    snapshots: Sequence[CompanySourceSnapshot], metric_ids: tuple[str, ...]
) -> tuple[MetricDefinition, ...]:
    definitions: dict[str, MetricDefinition] = {}
    for snapshot in snapshots:
        current = {row.metric_id: row for row in snapshot.definitions}
        for metric_id in metric_ids:
            if metric_id not in current:
                message = f"Source lacks production metric definition: {metric_id}"
                raise ValueError(message)
            if (
                metric_id in definitions
                and definitions[metric_id] != current[metric_id]
            ):
                message = f"Production metric definition changed: {metric_id}"
                raise ValueError(message)
            definitions[metric_id] = current[metric_id]
    return tuple(definitions[key] for key in metric_ids)


def _fit(
    rows: Sequence[_FeatureRow],
    labels: Sequence[CompanyOutcomeLabel],
    plan: CompanyExperimentPlan,
    definitions: tuple[MetricDefinition, ...],
    digest: str,
) -> CompanyLogisticModel:
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]
    from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
    from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

    matrix = np.array([row.values for row in rows], dtype=np.float64)
    missing = np.isnan(matrix)
    logged = np.sign(matrix) * np.log1p(np.abs(matrix))
    medians = np.nanmedian(logged, axis=0)
    expanded = np.concatenate((np.where(missing, medians, logged), missing), axis=1)
    scaler = StandardScaler()
    features = scaler.fit_transform(expanded)
    truth = np.array([label.value for label in labels], dtype=np.int64)
    with catch_warnings():
        simplefilter("error", ConvergenceWarning)
        classifier = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
        classifier.fit(features, truth)
    return CompanyLogisticModel(
        plan=plan,
        sklearn_version=version("scikit-learn"),
        definitions=definitions,
        training_sha256=digest,
        medians=tuple(medians.tolist()),
        means=tuple(scaler.mean_.tolist()),
        scales=tuple(scaler.scale_.tolist()),
        coefficients=tuple(classifier.coef_[0].tolist()),
        intercept=float(classifier.intercept_[0]),
        training_prevalence=float(truth.mean()),
    )


def predict_company_logistic(
    model: CompanyLogisticModel, snapshot: CompanySourceSnapshot
) -> tuple[CompanyProbabilityForecast, ...]:
    """Apply frozen preprocessing to the same production source projection.

    Args:
        model: Validated portable experimental model, loaded from JSON.
        snapshot: Exact non-synthetic source, at/after fit, with identical definitions.
    Returns:
        Experimental probabilities for resolved companies with usable predictors.
        Entirely missing companies abstain instead of receiving a spurious score.
    Raises:
        ValueError: Source is synthetic, predates fit, or changes feature semantics.
    """
    if snapshot.synthetic or snapshot.as_of < model.plan.fit_at:
        message = "Prediction requires a real source at or after model fitting"
        raise ValueError(message)
    if _definitions((snapshot,), model.plan.metric_ids) != model.definitions:
        message = "Prediction definitions differ from the trained model"
        raise ValueError(message)
    rows, _ = _project((snapshot,), model.plan.metric_ids)
    forecasts = []
    for key in sorted(rows):
        row = rows[key]
        transformed = tuple(
            median if value is None else copysign(log1p(abs(value)), value)
            for value, median in zip(row.values, model.medians, strict=True)
        ) + tuple(float(value is None) for value in row.values)
        log_odds = model.intercept + fsum(
            weight * ((value - mean) / scale)
            for value, mean, scale, weight in zip(
                transformed, model.means, model.scales, model.coefficients, strict=True
            )
        )
        probability = (
            1 / (1 + exp(-log_odds))
            if log_odds >= 0
            else exp(log_odds) / (1 + exp(log_odds))
        )
        forecasts.append(
            CompanyProbabilityForecast(
                row.company_id, model.plan.outcome_id, row.decision_at, probability
            )
        )
    return tuple(forecasts)


def _support(
    selected: Sequence[CompanyOutcomeLabel], partition: str, minimum: int
) -> tuple[dict[str, int], list[str]]:
    counts = {}
    reasons = []
    for truth, name in ((False, "negative"), (True, "positive")):
        families = {row.family_id for row in selected if row.value is truth}
        counts[f"{partition}_{name}_families"] = len(families)
        if len(families) < minimum:
            reasons.append(f"{partition}_insufficient_{name}_families")
    return counts, reasons


def _partition_sources(
    plan: CompanyExperimentPlan, snapshots: Sequence[CompanySourceSnapshot]
) -> tuple[tuple[CompanySourceSnapshot, ...], tuple[CompanySourceSnapshot, ...]]:
    sources = {row.snapshot_id: row for row in snapshots}
    expected = set(plan.train_snapshot_ids + plan.test_snapshot_ids)
    if len(sources) != len(snapshots) or set(sources) != expected:
        message = "Supply exactly the unique source vintages frozen in the plan"
        raise ValueError(message)
    training = tuple(sources[key] for key in plan.train_snapshot_ids)
    test = tuple(sources[key] for key in plan.test_snapshot_ids)
    if any(row.as_of >= plan.fit_at for row in training) or any(
        not plan.fit_at <= row.as_of < plan.evaluated_at for row in test
    ):
        message = "Source origins violate chronological train/test boundaries"
        raise ValueError(message)
    return training, test


def run_company_experiment(
    plan: CompanyExperimentPlan,
    snapshots: Sequence[CompanySourceSnapshot],
    labels: Sequence[CompanyOutcomeLabel],
) -> CompanyExperimentResult:
    """Fit an interpretable endpoint model only after source and label gates pass.

    Args:
        plan: Predeclared ordered metrics, endpoint, snapshots and support gates.
        snapshots: Exact validated publications, with raw hashes verified by caller.
        labels: Adjudicated immutable label vintages with reviewed source evidence.
    Returns:
        Explicit readiness failures, or a research-only model and baseline comparison.
        Synthetic sources never train. Held-out families are excluded before fitting;
        label availability and full calendar horizons are enforced at the fit cutoff.
        Support thresholds are safeguards, not claims of adequate statistical power.
    Raises:
        ValueError: Sources, cutoffs, label joins, units or selected vintages conflict.
        sklearn.exceptions.ConvergenceWarning: Optimizer fails to converge.
    """
    training_sources, test_sources = _partition_sources(plan, snapshots)
    if any(row.synthetic for row in snapshots):
        return CompanyExperimentResult(
            plan=plan,
            status="blocked",
            reasons=("synthetic_sources_forbidden",),
            counts={},
        )
    definitions = _definitions(snapshots, plan.metric_ids)
    training, train_exclusions = _project(training_sources, plan.metric_ids)
    test, test_exclusions = _project(test_sources, plan.metric_ids)
    test_companies = {
        row.company_id for source in test_sources for row in source.companies
    }
    training = {
        key: row
        for key, row in training.items()
        if row.company_id not in test_companies
    }
    # Reserve every resolved test family, even when that company has no predictors.
    held_out = frozenset(
        family.family_id
        for source in test_sources
        for company in source.companies
        if (
            family := resolve_family(
                source, company.company_id, source.as_of, public_only=True
            )
        ).family_id
        is not None
    )
    scoped = [label for label in labels if label.outcome_id == plan.outcome_id]
    for label in scoped:
        feature = training.get((label.company_id, label.decision_at)) or test.get(
            (label.company_id, label.decision_at)
        )
        if feature is not None and feature.family_id != label.family_id:
            message = "Label family conflicts with dated source family resolution"
            raise ValueError(message)
    train_selection = select_company_labels(
        [row for row in scoped if (row.company_id, row.decision_at) in training],
        plan.outcome_id,
        plan.fit_at,
        held_out,
    )
    test_selection = select_company_labels(
        [row for row in scoped if (row.company_id, row.decision_at) in test],
        plan.outcome_id,
        plan.evaluated_at,
    )
    counts = {
        "training_feature_rows": len(training),
        "test_feature_rows": len(test),
        "training_labels": len(train_selection.labels),
        "test_labels": len(test_selection.labels),
        **{f"training_{key}": value for key, value in train_exclusions.items()},
        **{f"test_{key}": value for key, value in test_exclusions.items()},
        **{
            f"training_label_{key}": value
            for key, value in train_selection.excluded_counts
        },
        **{f"test_label_{key}": value for key, value in test_selection.excluded_counts},
    }
    reasons = []
    for partition, selected, minimum in (
        ("training", train_selection.labels, plan.minimum_train_per_class),
        ("test", test_selection.labels, plan.minimum_test_per_class),
    ):
        support_counts, support_reasons = _support(selected, partition, minimum)
        counts.update(support_counts)
        reasons.extend(support_reasons)
    train_rows = [
        training[(row.company_id, row.decision_at)] for row in train_selection.labels
    ]
    for index, metric_id in enumerate(plan.metric_ids):
        observed = sum(row.values[index] is not None for row in train_rows)
        counts[f"training_observed_{metric_id}"] = observed
        if not observed:
            reasons.append(f"training_metric_unobserved:{metric_id}")
    if reasons:
        return CompanyExperimentResult(
            plan=plan, status="blocked", reasons=tuple(reasons), counts=counts
        )
    digest = sha256()
    for source in sorted(training_sources, key=lambda row: row.snapshot_id):
        digest.update(source.model_dump_json().encode())
    for label in train_selection.labels:
        digest.update(label.model_dump_json().encode())
    model = _fit(
        train_rows, train_selection.labels, plan, definitions, digest.hexdigest()
    )
    predictions = tuple(
        row
        for source in test_sources
        for row in predict_company_logistic(model, source)
    )
    baseline = tuple(
        CompanyProbabilityForecast(
            row.company_id, row.outcome_id, row.decision_at, model.training_prevalence
        )
        for row in predictions
    )
    logistic_metrics = evaluate_company_probabilities(
        predictions, test_selection.labels, plan.outcome_id, plan.evaluated_at
    )
    prevalence_metrics = evaluate_company_probabilities(
        baseline, test_selection.labels, plan.outcome_id, plan.evaluated_at
    )
    beats = (
        logistic_metrics.brier_score is not None
        and prevalence_metrics.brier_score is not None
        and logistic_metrics.log_loss is not None
        and prevalence_metrics.log_loss is not None
        and logistic_metrics.brier_score < prevalence_metrics.brier_score
        and logistic_metrics.log_loss < prevalence_metrics.log_loss
    )
    return CompanyExperimentResult(
        plan=plan,
        status="experimental",
        counts=counts,
        model=model,
        logistic_metrics=logistic_metrics,
        prevalence_metrics=prevalence_metrics,
        beats_prevalence=beats,
        reasons=("public_release_not_validated", "overall_utility_not_defined"),
    )
