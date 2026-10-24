"""Whole-origin chronological evaluation with explicit label-availability purges."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from oxhack2026.features.definitions import (
    TargetId,
    require_decision,
    require_utc,
    target_windows,
)
from oxhack2026.models.contracts import LabelRow

_WEEK = timedelta(weeks=1)


@dataclass(frozen=True)
class OriginAvailability:
    """Eligibility and latest required label availability for an entire origin.

    Attributes:
        decision_at: Feature-eligible Monday origin after the 84-day lookback.
        label_available_at: Latest required availability, or None if incomplete.
    """

    decision_at: datetime
    label_available_at: datetime | None


@dataclass(frozen=True)
class DevelopmentFold:
    """Whole-origin training and one chronological validation block.

    Attributes:
        fit_at: First validation decision and training-label availability boundary.
        training_origins: Entire earlier origins whose required labels are available.
        validation_origins: Thirteen consecutive weekly origins.
    """

    fit_at: datetime
    training_origins: tuple[datetime, ...]
    validation_origins: tuple[datetime, ...]


@dataclass(frozen=True)
class CalendarProtocol:
    """Full membership for the predeclared frozen-model/calibrator experiment.

    Attributes:
        development: Three separate 13-origin validation folds.
        final_training_origins: Training labels available by calibration start.
        calibration_origins: Twenty-six origins with labels available by test start.
        test_origins: Twenty-six consecutive fully mature final-test origins.
    """

    development: tuple[DevelopmentFold, ...]
    final_training_origins: tuple[datetime, ...]
    calibration_origins: tuple[datetime, ...]
    test_origins: tuple[datetime, ...]


def origin_availability(labels: Sequence[LabelRow]) -> tuple[OriginAvailability, ...]:
    """Aggregate all required candidate labels without dropping incomplete rows.

    Args:
        labels: One C2 label row for every expected eligible feature row, including
            explicit missing labels, for one ecosystem/target experiment.
    Returns:
        Chronological origins with latest availability, or None if any label is
        incomplete. Callers must supply all expected candidates, not complete cases.
    Raises:
        ValueError: If targets are mixed or feature-row IDs are duplicated.
    """
    grouped: dict[datetime, datetime | None] = {}
    seen: set[str] = set()
    target_ids = {label.windows.target_id for label in labels}
    if len(target_ids) > 1:
        message = "Availability aggregation requires one target experiment"
        raise ValueError(message)
    for label in labels:
        if label.feature_row_id in seen:
            message = "Expected one label per immutable feature-row ID"
            raise ValueError(message)
        seen.add(label.feature_row_id)
        origin = label.windows.decision_at
        if origin not in grouped:
            grouped[origin] = label.available_at
        elif (previous := grouped[origin]) is None or label.available_at is None:
            grouped[origin] = None
        else:
            grouped[origin] = max(previous, label.available_at)
    return tuple(
        OriginAvailability(
            decision_at=origin,
            label_available_at=available_at,
        )
        for origin, available_at in sorted(grouped.items())
    )


def _validate_origins(
    origins: Sequence[OriginAvailability], target_id: TargetId
) -> dict[datetime, datetime | None]:
    available: dict[datetime, datetime | None] = {}
    for origin in origins:
        decision = require_decision(origin.decision_at)
        if decision in available:
            message = "Each weekly origin must have one aggregate availability record"
            raise ValueError(message)
        if origin.label_available_at is not None:
            require_utc(origin.label_available_at)
            if (
                origin.label_available_at
                < target_windows(decision, target_id).target_end
            ):
                message = "Labels cannot be available before target completion"
                raise ValueError(message)
        available[decision] = origin.label_available_at
    return dict(sorted(available.items()))


def _block(
    end: datetime,
    count: int,
    available: dict[datetime, datetime | None],
    fit_at: datetime,
) -> tuple[datetime, ...]:
    block = tuple(end - offset * _WEEK for offset in range(count - 1, -1, -1))
    if any(
        (timestamp := available.get(origin)) is None or timestamp > fit_at
        for origin in block
    ):
        message = (
            "Insufficient consecutive mature origins for the full calendar protocol"
        )
        raise ValueError(message)
    return block


def _latest_available(
    available: dict[datetime, datetime | None], fit_at: datetime
) -> datetime:
    latest = max(
        (
            origin
            for origin, timestamp in available.items()
            if timestamp is not None and timestamp <= fit_at
        ),
        default=None,
    )
    if latest is None:
        message = "No fully mature eligible origins at the requested fit boundary"
        raise ValueError(message)
    return latest


def _training(
    available: dict[datetime, datetime | None], fit_at: datetime
) -> tuple[datetime, ...]:
    origins = tuple(
        origin
        for origin, timestamp in available.items()
        if origin < fit_at and timestamp is not None and timestamp <= fit_at
    )
    if len(origins) < 52:
        message = (
            "Full validation requires at least 52 earlier eligible training origins"
        )
        raise ValueError(message)
    return origins


def calendar_protocol(
    origins: Sequence[OriginAvailability], target_id: TargetId, as_of: datetime
) -> CalendarProtocol:
    """Build PLAN.md's backwards calendar protocol without accessing final scores.

    Args:
        origins: One availability record per feature-eligible origin after its
            required history; missing candidate labels must remain explicit.
        target_id: Separate 30-day or 91-day aggregate prediction definition.
        as_of: UTC dataset/evaluation cutoff determining the latest mature Monday.
    Returns:
        Three development folds, frozen final training, calibration, and test
        membership. Fit the final model at calibration start, then keep its pair
        frozen through final test. Each training fold has at least 52 origins.
    Raises:
        ValueError: For invalid origins/availability, unsupported targets, gaps,
            or insufficient history. Report exploratory status rather than
            silently shortening this full protocol after an exception.
    """
    require_utc(as_of)
    if target_id not in {"downloads_next_30d_v1", "downloads_trailing_28d_at_91d_v1"}:
        message = "Unsupported target definition"
        raise ValueError(message)
    available = _validate_origins(origins, target_id)
    test = _block(_latest_available(available, as_of), 26, available, as_of)
    calibration = _block(_latest_available(available, test[0]), 26, available, test[0])
    development = _block(
        _latest_available(available, calibration[0]), 39, available, calibration[0]
    )
    folds = tuple(
        DevelopmentFold(
            fit_at=development[offset],
            training_origins=_training(available, development[offset]),
            validation_origins=development[offset : offset + 13],
        )
        for offset in (0, 13, 26)
    )
    return CalendarProtocol(
        development=folds,
        final_training_origins=_training(available, calibration[0]),
        calibration_origins=calibration,
        test_origins=test,
    )
