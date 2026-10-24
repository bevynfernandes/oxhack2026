"""Whole-origin membership, availability-purge, and insufficient-history checks."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import orjson
import pytest

from oxhack2026.evaluation.splits import (
    OriginAvailability,
    calendar_protocol,
    origin_availability,
)
from oxhack2026.features.definitions import TargetId
from oxhack2026.models.contracts import LabelRow

_START = datetime(2020, 1, 6, tzinfo=UTC)
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/models"


def _origins(count: int = 200, horizon_days: int = 30) -> list[OriginAvailability]:
    return [
        OriginAvailability(
            decision_at=_START + timedelta(weeks=index),
            label_available_at=_START + timedelta(weeks=index, days=horizon_days + 2),
        )
        for index in range(count)
    ]


@pytest.mark.parametrize(
    ("target_id", "horizon", "calibration_start", "development_start"),
    [
        ("downloads_next_30d_v1", 30, 144, 101),
        ("downloads_trailing_28d_at_91d_v1", 91, 135, 83),
    ],
)
def test_full_backwards_protocol(
    target_id: TargetId,
    horizon: int,
    calibration_start: int,
    development_start: int,
) -> None:
    """Both targets use independent exact calendar membership with maturity gaps."""
    origins = _origins(horizon_days=horizon)
    as_of = _START + timedelta(weeks=199, days=horizon + 2)

    protocol = calendar_protocol(origins, target_id, as_of)

    assert protocol.test_origins == tuple(
        _START + timedelta(weeks=index) for index in range(174, 200)
    )
    assert protocol.calibration_origins == tuple(
        _START + timedelta(weeks=index)
        for index in range(calibration_start, calibration_start + 26)
    )
    assert [len(fold.validation_origins) for fold in protocol.development] == [
        13,
        13,
        13,
    ]
    assert protocol.development[0].fit_at == _START + timedelta(weeks=development_start)
    assert all(len(fold.training_origins) >= 52 for fold in protocol.development)
    available = {row.decision_at: row.label_available_at for row in origins}
    for fold in protocol.development:
        assert all(
            (timestamp := available[origin]) is not None and timestamp <= fold.fit_at
            for origin in fold.training_origins
        )
        assert set(fold.training_origins).isdisjoint(fold.validation_origins)
    assert set(protocol.calibration_origins).isdisjoint(protocol.final_training_origins)
    assert set(protocol.test_origins).isdisjoint(protocol.calibration_origins)
    assert all(
        (timestamp := available[origin]) is not None
        and timestamp <= protocol.test_origins[0]
        for origin in protocol.calibration_origins
    )


def test_split_membership_is_reproducible_under_row_reordering() -> None:
    """Input row order cannot change development, calibration, or test membership."""
    rows = _origins()
    as_of = _START + timedelta(weeks=199, days=32)

    assert calendar_protocol(rows, "downloads_next_30d_v1", as_of) == calendar_protocol(
        rows[::-1], "downloads_next_30d_v1", as_of
    )


def test_future_origins_do_not_change_earlier_protocol() -> None:
    """Additional labels unavailable at the frozen cutoff cannot move its test."""
    as_of = _START + timedelta(weeks=199, days=32)

    assert calendar_protocol(
        _origins(200), "downloads_next_30d_v1", as_of
    ) == calendar_protocol(_origins(250), "downloads_next_30d_v1", as_of)


def test_unavailable_training_label_is_purged() -> None:
    """Training excludes a delayed historical label even when its origin is old."""
    rows = _origins()
    as_of = _START + timedelta(weeks=199, days=32)
    rows[0] = replace(rows[0], label_available_at=as_of + timedelta(days=1))

    protocol = calendar_protocol(rows, "downloads_next_30d_v1", as_of)

    assert all(_START not in fold.training_origins for fold in protocol.development)
    assert _START not in protocol.final_training_origins


@pytest.mark.parametrize("count", [0, 20, 100, 154])
def test_insufficient_history_is_not_silently_shortened(count: int) -> None:
    """Short panels fail the full protocol instead of inheriting stronger claims."""
    with pytest.raises(ValueError):
        calendar_protocol(
            _origins(count), "downloads_next_30d_v1", _START + timedelta(weeks=210)
        )


@pytest.mark.parametrize("index", [110, 150, 180])
def test_missing_origin_in_required_block_fails(index: int) -> None:
    """Development, calibration, and final test each require consecutive weeks."""
    rows = _origins()
    rows[index] = replace(rows[index], label_available_at=None)

    with pytest.raises(ValueError, match="consecutive mature"):
        calendar_protocol(
            rows, "downloads_next_30d_v1", _START + timedelta(weeks=199, days=32)
        )


def test_duplicate_origins_fail() -> None:
    """One origin-level record prevents splitting a panel by arbitrary tool rows."""
    rows = _origins()

    with pytest.raises(ValueError, match="one aggregate"):
        calendar_protocol(
            [*rows, rows[0]], "downloads_next_30d_v1", _START + timedelta(weeks=210)
        )


def test_premature_label_rejected() -> None:
    """Availability cannot precede the end of its target window."""
    rows = _origins()
    rows[0] = replace(rows[0], label_available_at=_START + timedelta(days=29))

    with pytest.raises(ValueError, match="target completion"):
        calendar_protocol(rows, "downloads_next_30d_v1", _START + timedelta(weeks=210))


def test_naive_cutoff_rejected() -> None:
    """The experiment cutoff must carry an explicit UTC timezone."""
    with pytest.raises(ValueError, match="UTC"):
        calendar_protocol(_origins(), "downloads_next_30d_v1", datetime(2025, 1, 6))


def test_origin_aggregation_requires_every_candidate_label() -> None:
    """A missing candidate makes its origin incomplete; complete zeros stay mature."""
    payload = orjson.loads((FIXTURES / "mature-outcome.json").read_bytes())["label"]
    complete = LabelRow.model_validate(payload)
    missing = LabelRow.model_validate(
        payload
        | {
            "feature_row_id": "synthetic-missing",
            "actual_downloads": None,
            "available_at": None,
        }
    )

    assert origin_availability([complete, missing])[0].label_available_at is None
    zero = LabelRow.model_validate(payload | {"actual_downloads": 0})
    assert origin_availability([zero])[0].label_available_at == zero.available_at
    assert origin_availability([]) == ()


def test_latest_candidate_availability_controls_entire_origin() -> None:
    """One tool's slower publication purges the entire required origin consistently."""
    payload = orjson.loads((FIXTURES / "mature-outcome.json").read_bytes())["label"]
    first = LabelRow.model_validate(payload)
    latest = datetime(2025, 2, 10, tzinfo=UTC)
    second = LabelRow.model_validate(
        payload
        | {
            "feature_row_id": "synthetic-slower",
            "available_at": latest,
        }
    )

    assert origin_availability([first, second])[0].label_available_at == latest


def test_duplicate_feature_labels_rejected() -> None:
    """Revised labels must be selected by vintage, not duplicated in one experiment."""
    payload = orjson.loads((FIXTURES / "mature-outcome.json").read_bytes())["label"]
    label = LabelRow.model_validate(payload)

    with pytest.raises(ValueError, match="one label"):
        origin_availability([label, label])
