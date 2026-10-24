"""C1-backed daily snapshots preserve vintages, missingness, and time boundaries."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import orjson
import polars as pl
import pytest

from oxhack2026.features.snapshots import daily_snapshot, observation_frame
from oxhack2026.storage.contracts import ObservationRevision

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/data"


def _revision(state: str = "complete") -> ObservationRevision:
    payload = orjson.loads((FIXTURES / "observation-states.json").read_bytes())
    return ObservationRevision.model_validate(payload["states"][state])


def _requests(cutoff: datetime, series_id: str | None = None) -> pl.LazyFrame:
    return pl.DataFrame(
        {
            "request_id": ["synthetic-feature"],
            "series_id": [series_id or _revision().series_id],
            "window_start": [datetime(2025, 1, 1, tzinfo=UTC)],
            "window_end": [datetime(2025, 1, 3, tzinfo=UTC)],
            "query_at": [cutoff],
        }
    ).lazy()


def test_reconstructed_uses_latest_permitted_frozen_revision() -> None:
    """Retrospective revision use is explicit and remains within the chosen bundle."""
    frame = observation_frame([_revision(), _revision("revised")])

    snapshot = (
        daily_snapshot(
            frame.lazy(), _requests(datetime(2025, 1, 6, tzinfo=UTC)), "reconstructed"
        )
        .collect()
        .sort("day")
    )

    assert snapshot["downloads"].to_list() == [120, None]
    assert snapshot["revision_id"].to_list() == ["synthetic-revised", None]


def test_prospective_uses_actual_collection_cutoff_and_vintage() -> None:
    """A later revision cannot change a prospective snapshot recorded before it."""
    frame = observation_frame([_revision(), _revision("revised")]).lazy()
    cutoff = datetime(2026, 10, 24, 10, tzinfo=UTC)

    snapshot = daily_snapshot(frame, _requests(cutoff), "prospective").collect()
    later = daily_snapshot(
        frame, _requests(cutoff + timedelta(days=1)), "prospective"
    ).collect()

    assert snapshot["downloads"].drop_nulls().to_list() == [100]
    assert later["downloads"].drop_nulls().to_list() == [120]


def test_collected_at_boundary_is_inclusive() -> None:
    """Collection by cutoff permits equality but never the following microsecond."""
    cutoff = datetime(2026, 10, 24, 10, tzinfo=UTC)
    frame = observation_frame([_revision()]).lazy()

    before = daily_snapshot(
        frame, _requests(cutoff - timedelta(microseconds=1)), "prospective"
    ).collect()
    exact = daily_snapshot(frame, _requests(cutoff), "prospective").collect()

    assert before["downloads"].null_count() == 2
    assert exact["downloads"].drop_nulls().to_list() == [100]


def test_historical_assumption_is_not_actual_early_collection() -> None:
    """Assumed old availability does not authorize a retrospective prospective claim."""
    frame = observation_frame([_revision()]).lazy()

    snapshot = daily_snapshot(
        frame, _requests(datetime(2025, 1, 6, tzinfo=UTC)), "prospective"
    ).collect()

    assert snapshot["downloads"].null_count() == snapshot.height == 2


def test_future_available_revision_cannot_change_past_snapshot() -> None:
    """Both modes reject records whose justified availability exceeds the cutoff."""
    original = _revision()
    future = ObservationRevision.model_validate(
        original.model_dump()
        | {
            "revision_id": "synthetic-future",
            "value": 99999,
            "availability_basis": "vendor_published",
            "assumed_available_at": None,
            "published_at": datetime(2025, 1, 7, tzinfo=UTC),
            "available_at": datetime(2025, 1, 7, tzinfo=UTC),
        }
    )
    requests = _requests(datetime(2025, 1, 6, tzinfo=UTC))

    before = (
        daily_snapshot(observation_frame([original]).lazy(), requests, "reconstructed")
        .collect()
        .sort("day")
    )
    after = (
        daily_snapshot(
            observation_frame([original, future]).lazy(), requests, "reconstructed"
        )
        .collect()
        .sort("day")
    )

    assert before.equals(after)


@pytest.mark.parametrize(
    ("state", "expected"), [("zero", 0), ("missing", None), ("partial", None)]
)
def test_complete_zero_differs_from_partial_or_missing(
    state: str, expected: int | None
) -> None:
    """All expected days remain present and incomplete values never become zero."""
    frame = observation_frame([_revision(state)]).lazy()

    snapshot = (
        daily_snapshot(
            frame, _requests(datetime(2025, 1, 6, tzinfo=UTC)), "reconstructed"
        )
        .collect()
        .sort("day")
    )

    assert snapshot["downloads"].to_list() == [expected, None]
    assert snapshot["completeness"][0] == (state if state != "zero" else "complete")


def test_empty_observations_preserve_typed_missing_grid() -> None:
    """An empty source still exposes every requested date and nullable Int64 counts."""
    frame = observation_frame([])

    snapshot = daily_snapshot(
        frame.lazy(), _requests(datetime(2025, 1, 6, tzinfo=UTC)), "reconstructed"
    ).collect()

    assert frame.schema["value"] == pl.Int64
    assert snapshot["downloads"].dtype == pl.Int64
    assert snapshot["downloads"].null_count() == snapshot.height == 2


def test_window_end_is_exclusive_and_series_are_separate() -> None:
    """A row at the exclusive end or from another series cannot enter the window."""
    original = _revision()
    outside = ObservationRevision.model_validate(
        original.model_dump()
        | {
            "revision_id": "synthetic-after-window",
            "value": 99999,
            "window": {
                "start": datetime(2025, 1, 3, tzinfo=UTC),
                "end": datetime(2025, 1, 4, tzinfo=UTC),
            },
            "assumed_available_at": datetime(2025, 1, 6, tzinfo=UTC),
            "available_at": datetime(2025, 1, 6, tzinfo=UTC),
        }
    )
    frame = observation_frame([original, outside]).lazy()
    cutoff = datetime(2025, 1, 6, tzinfo=UTC)

    snapshot = (
        daily_snapshot(frame, _requests(cutoff), "reconstructed").collect().sort("day")
    )
    other = daily_snapshot(
        frame, _requests(cutoff, "synthetic-other"), "reconstructed"
    ).collect()

    assert snapshot["downloads"].to_list() == [100, None]
    assert other["downloads"].null_count() == 2


def test_duplicate_revision_ids_rejected() -> None:
    """One frozen revision cannot appear twice and distort provenance selection."""
    with pytest.raises(ValueError, match="unique immutable"):
        observation_frame([_revision(), _revision()])


def test_empty_requests_cannot_create_phantom_days() -> None:
    """No eligible forecast requests must produce no analytical observations."""
    requests = _requests(datetime(2025, 1, 6, tzinfo=UTC)).filter(pl.lit(False))

    snapshot = daily_snapshot(
        observation_frame([_revision()]).lazy(), requests, "reconstructed"
    ).collect()

    assert snapshot.height == 0
