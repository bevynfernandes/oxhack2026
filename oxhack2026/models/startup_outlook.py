"""Local-model placeholders shared by research reports without implying forecasts."""

from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, model_validator

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.catalog.schemas import Identifier, UtcInstant
from oxhack2026.features.company_policy import company_metric_state
from oxhack2026.models.contracts import Contract

SpecialistGroupId = Literal[
    "adoption_retention",
    "attention_sentiment",
    "financial_health",
    "industry_competition",
    "team_execution",
]
SPECIALIST_GROUP_IDS: tuple[SpecialistGroupId, ...] = (
    "adoption_retention",
    "attention_sentiment",
    "financial_health",
    "industry_competition",
    "team_execution",
)
DataStatus = Literal["available", "insufficient_data", "not_applicable"]
_Reasons = Annotated[tuple[Identifier, ...], Field(min_length=1)]
ForecastOutcomeId = Literal["growth", "survival", "financial_health"]
FORECAST_HORIZONS: dict[ForecastOutcomeId, int] = {
    "growth": 24,
    "survival": 24,
    "financial_health": 12,
}


class OutcomeForecast(Contract):
    """An agreed product horizon without an approved label policy or model.

    Attributes:
        outcome_id: Product outcome, separate from specialist groups/v1 targets.
        horizon_months: Approved calendar-month horizon from the report cutoff.
        definition_status: Detailed labels/thresholds still require a data review.
        model_status: No training or inference has run for this outcome.
        prediction: Always null; no probability or score is permitted.
        reason_codes: Both label-policy and model limitations, in display order.

    Raises:
        ValueError: Horizon disagrees with the outcome or a prediction is injected.
    """

    outcome_id: ForecastOutcomeId
    horizon_months: Annotated[int, Field(strict=True, gt=0)]
    definition_status: Literal["pending_label_policy"] = "pending_label_policy"
    model_status: Literal["model_not_trained"] = "model_not_trained"
    prediction: None = None
    reason_codes: tuple[
        Literal["target_definition_pending"], Literal["model_not_trained"]
    ] = ("target_definition_pending", "model_not_trained")

    @model_validator(mode="after")
    def _validate_horizon(self) -> Self:
        if self.horizon_months != FORECAST_HORIZONS[self.outcome_id]:
            message = "Forecast horizon must match the approved product outcome"
            raise ValueError(message)
        return self


def _data_status(has_usable: bool, states: set[str]) -> DataStatus:
    if has_usable:
        return "available"
    if states == {"not_applicable"}:
        return "not_applicable"
    return "insufficient_data"


class SpecialistOutlook(Contract):
    """One group's source coverage, independent of its untrained model status.

    Attributes:
        group_id: Fundamental metric group, not a success target.
        data_status: Available means some usable observations, not training-ready.
        metric_observation_ids: All assigned source observations, including gaps.
        usable_metric_observation_ids: Fresh verified public observations only.
        evidence_ids: Supporting evidence for usable observations only.
        reason_codes: Data limitations and the absent-model reason.
        model_status: Explicitly untrained; this version never serves forecasts.
        prediction: Always null until a separately gated serving contract exists.

    Raises:
        ValueError: References repeat, usable references are absent, or coverage
            contradicts availability. Numerical forecasts are rejected.
    """

    group_id: SpecialistGroupId
    data_status: DataStatus
    metric_observation_ids: tuple[Identifier, ...] = ()
    usable_metric_observation_ids: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()
    reason_codes: _Reasons
    model_status: Literal["model_not_trained"] = "model_not_trained"
    prediction: None = None

    @model_validator(mode="after")
    def _validate_coverage(self) -> Self:
        for references in (
            self.metric_observation_ids,
            self.usable_metric_observation_ids,
            self.evidence_ids,
        ):
            if len(references) != len(set(references)):
                message = "Specialist references must be unique"
                raise ValueError(message)
        usable = set(self.usable_metric_observation_ids)
        if not usable <= set(self.metric_observation_ids):
            message = "Usable metrics must belong to the specialist inventory"
            raise ValueError(message)
        if (self.data_status == "available") != bool(usable):
            message = "Available data requires usable observations"
            raise ValueError(message)
        if bool(self.evidence_ids) != bool(usable):
            message = "Only usable observations carry public model evidence"
            raise ValueError(message)
        if "model_not_trained" not in self.reason_codes:
            message = "Untrained specialists require the model_not_trained reason"
            raise ValueError(message)
        return self


class StartupOutlook(Contract):
    """Five local-model placeholders attached to one exact company source vintage.

    Attributes:
        schema_version: Additive research payload version; v1 assessments stay intact.
        company_id: Exact source company identity, not a user-entered name.
        source_snapshot_id: Immutable source publication consumed by the builder.
        as_of: Source cutoff, never the current request clock.
        grouping_policy_version: Version of the explicit metric-to-group mapping.
        synthetic: Source fixture flag retained for API/UI consumers.
        specialists: Exactly one section per group, including unavailable groups.
        unassigned_metric_observation_ids: Observations without an approved mapping.
        inference_runtime: Intended execution location; no inference has run.
        overall_outlook: Null; this contract cannot fabricate an outlook index.
        overall_reason_codes: Why a combined prediction cannot be served.
        forecasts: Three outcome placeholders for new reports. Absent in older
            reports; omitted on serialization to preserve their original bytes.

    Raises:
        ValueError: Groups or observation assignments repeat or are incomplete.
    """

    schema_version: Literal["startup-outlook-placeholder-v1"] = (
        "startup-outlook-placeholder-v1"
    )
    company_id: Identifier
    source_snapshot_id: Identifier
    as_of: UtcInstant
    grouping_policy_version: Identifier
    synthetic: StrictBool
    specialists: tuple[SpecialistOutlook, ...]
    unassigned_metric_observation_ids: tuple[Identifier, ...] = ()
    inference_runtime: Literal["local_cpu"] = "local_cpu"
    overall_outlook: None = None
    overall_reason_codes: tuple[Literal["model_not_trained"], ...] = (
        "model_not_trained",
    )
    forecasts: tuple[OutcomeForecast, ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _validate_inventory(self) -> Self:
        if len(self.specialists) != len(SPECIALIST_GROUP_IDS) or {
            section.group_id for section in self.specialists
        } != set(SPECIALIST_GROUP_IDS):
            message = "Startup outlook requires each of the five groups exactly once"
            raise ValueError(message)
        references = list(self.unassigned_metric_observation_ids)
        for section in self.specialists:
            references.extend(section.metric_observation_ids)
        if len(references) != len(set(references)):
            message = "A source observation can be assigned only once"
            raise ValueError(message)
        if not self.overall_reason_codes:
            message = "Unavailable overall outlook requires a reason"
            raise ValueError(message)
        if self.forecasts is not None and tuple(
            row.outcome_id for row in self.forecasts
        ) != tuple(FORECAST_HORIZONS):
            message = "Forecasts require growth, survival and financial health in order"
            raise ValueError(message)
        return self


def build_untrained_outlook(
    snapshot: CompanySourceSnapshot,
    company_id: str,
    metric_groups: Mapping[str, SpecialistGroupId],
    grouping_policy_version: str,
) -> StartupOutlook:
    """Project a company into five honest model placeholders without fitting.

    Args:
        snapshot: Validated source publication with resolved cross-table references.
        company_id: Company present in this exact snapshot.
        metric_groups: Explicit metric-definition IDs mapped to fundamental groups.
            No family-based guesses: financing is not industry demand. Unmapped
            observations remain visible separately rather than being dropped.
        grouping_policy_version: Version identifying these mapping semantics.
    Returns:
        Deterministic five-group coverage payload with null predictions and score.
        Evidence usability follows the shared source/feature policy. Available
        observations, including zero, do not imply sufficient training data.
    Raises:
        ValueError: Company, metric mapping, group or policy identity is invalid.
    """
    if company_id not in {company.company_id for company in snapshot.companies}:
        message = "Company is absent from the source snapshot"
        raise ValueError(message)
    definitions = {
        definition.metric_id: definition for definition in snapshot.definitions
    }
    if not set(metric_groups) <= definitions.keys() or any(
        group not in SPECIALIST_GROUP_IDS for group in metric_groups.values()
    ):
        message = "Metric mapping requires known definitions and specialist groups"
        raise ValueError(message)
    evidence = {item.evidence_id: item for item in snapshot.evidence}
    assigned: dict[SpecialistGroupId, list[str]] = {
        group: [] for group in SPECIALIST_GROUP_IDS
    }
    usable: dict[SpecialistGroupId, list[str]] = {
        group: [] for group in SPECIALIST_GROUP_IDS
    }
    support: dict[SpecialistGroupId, set[str]] = {
        group: set() for group in SPECIALIST_GROUP_IDS
    }
    states: dict[SpecialistGroupId, set[str]] = {
        group: set() for group in SPECIALIST_GROUP_IDS
    }
    unassigned = []
    for observation in snapshot.metrics:
        if observation.company_id != company_id:
            continue
        group = metric_groups.get(observation.metric_id)
        if group is None:
            unassigned.append(observation.observation_id)
            continue
        assigned[group].append(observation.observation_id)
        state = company_metric_state(
            observation, definitions[observation.metric_id], evidence, snapshot.as_of
        )
        states[group].add(state)
        if state == "observed":
            usable[group].append(observation.observation_id)
            support[group].update(observation.evidence_ids)
    sections = []
    for group in SPECIALIST_GROUP_IDS:
        reasons = {"model_not_trained"} | (states[group] - {"observed"})
        if not assigned[group]:
            reasons.add("no_assigned_metrics")
        sections.append(
            SpecialistOutlook(
                group_id=group,
                data_status=_data_status(bool(usable[group]), states[group]),
                metric_observation_ids=tuple(sorted(assigned[group])),
                usable_metric_observation_ids=tuple(sorted(usable[group])),
                evidence_ids=tuple(sorted(support[group])),
                reason_codes=tuple(sorted(reasons)),
            )
        )
    return StartupOutlook(
        company_id=company_id,
        source_snapshot_id=snapshot.snapshot_id,
        as_of=snapshot.as_of,
        grouping_policy_version=grouping_policy_version,
        synthetic=snapshot.synthetic,
        specialists=tuple(sections),
        unassigned_metric_observation_ids=tuple(sorted(unassigned)),
        forecasts=tuple(
            OutcomeForecast(outcome_id=outcome_id, horizon_months=months)
            for outcome_id, months in FORECAST_HORIZONS.items()
        ),
    )
