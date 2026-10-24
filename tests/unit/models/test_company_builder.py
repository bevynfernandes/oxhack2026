"""C1-to-C2 public evidence composition, with no vendors or probability shortcuts."""

from datetime import timedelta
from pathlib import Path

import pytest

from oxhack2026.catalog.company import CompanySourceSnapshot
from oxhack2026.explanations.deterministic import build_company_assessments

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/data/company-source.json"


def _source() -> CompanySourceSnapshot:
    return CompanySourceSnapshot.model_validate_json(FIXTURE.read_bytes())


def test_all_companies_keep_three_outcomes_and_observed_zero() -> None:
    """Public facts do not become commercial growth or a company-success score."""
    source = _source()

    assessments = build_company_assessments(source, source.recorded_at)

    assert [row.company_id for row in assessments] == ["alpha", "beta"]
    alpha = assessments[0]
    assert len(alpha.outcomes) == 3
    assert alpha.outcomes[0].assessment_status == "evidence_only"
    assert alpha.outcomes[1].assessment_status == "unavailable"
    assert alpha.outcomes[2].assessment_status == "evidence_only"
    zero = next(
        row
        for row in alpha.statements
        if row.statement_id == "metric-alpha-sdk_downloads_30d_v1"
    )
    assert "0 downloads" in zero.text
    assert "Product measure" in zero.text
    assert alpha.family_id == "alpha"
    assert alpha.synthetic is True
    assert alpha.source_snapshot_id == source.snapshot_id
    assert all(row.probability is None for row in alpha.outcomes)


@pytest.mark.parametrize(
    "access,review",
    [("restricted", "verified"), ("public", "unreviewed"), ("public", "disputed")],
)
def test_nonpublic_or_unverified_metric_values_never_enter_narrative(
    access: str, review: str
) -> None:
    """A source may exist while its value remains unusable for a public assessment."""
    payload = _source().model_dump(mode="json")
    source = payload["evidence"][0] | {
        "evidence_id": "alpha-metric-only-source",
        "access": access,
        "review_state": review,
        "url": None if access == "restricted" else "https://alpha.example/metric",
    }
    payload["evidence"].append(source)
    payload["metrics"][0] |= {
        "value": {"kind": "integer", "value": 987654321},
        "evidence_ids": [source["evidence_id"]],
    }
    snapshot = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(snapshot, snapshot.recorded_at)

    statement = next(
        row
        for row in alpha.statements
        if row.statement_id == "metric-alpha-sdk_downloads_30d_v1"
    )
    assert statement.role == "evidence_gap"
    assert statement.evidence_ids == ()
    assert statement.missing_metric_ids == ("sdk_downloads_30d_v1",)
    assert "987654321" not in alpha.model_dump_json()
    assert "987,654,321" not in alpha.model_dump_json()


def test_stale_measurement_does_not_become_fresh_when_assessment_is_rerun() -> None:
    """Freshness uses frozen measurement time, never the execution clock."""
    payload = _source().model_dump(mode="json")
    payload["definitions"][0]["maximum_age_days"] = 1
    payload["metrics"][0]["window"]["end"] = "2025-01-29T00:00:00Z"
    source = CompanySourceSnapshot.model_validate(payload)

    first, _ = build_company_assessments(source, source.recorded_at)
    later, _ = build_company_assessments(
        source, source.recorded_at + timedelta(days=365)
    )

    assert first.statements == later.statements
    statement = next(
        row
        for row in first.statements
        if row.statement_id == "metric-alpha-sdk_downloads_30d_v1"
    )
    assert statement.role == "evidence_gap"
    assert "stale measurement" in statement.text
    assert first.assessment_id != later.assessment_id


def test_inapplicable_metric_does_not_create_an_evidence_gap() -> None:
    """Coverage does not penalize a company for a definition that does not apply."""
    payload = _source().model_dump(mode="json")
    payload["metrics"][0] |= {
        "state": "not_applicable",
        "value": None,
        "evidence_ids": [],
        "reason": "Not a package-distributed product.",
    }
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    assert all(
        row.statement_id != "metric-alpha-sdk_downloads_30d_v1"
        for row in alpha.statements
    )


def test_company_shutdown_and_product_retirement_remain_distinct() -> None:
    """Product retirement never becomes evidence that the company shut down."""
    payload = _source().model_dump(mode="json")
    payload["events"][0] |= {"kind": "product_retirement", "stage": "completed"}
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    event = next(row for row in alpha.statements if row.event_ids)
    assert event.role == "observation"
    assert "Product retirement completed" in event.text
    assert alpha.outcomes[1].assessment_status == "unavailable"
    payload["events"][0]["kind"] = "company_shutdown"
    shutdown_source = CompanySourceSnapshot.model_validate(payload)
    shutdown, _ = build_company_assessments(
        shutdown_source, shutdown_source.recorded_at
    )
    risk = next(row for row in shutdown.statements if row.event_ids)
    assert risk.role == "risk"
    assert "Company shutdown completed" in risk.text
    assert shutdown.outcomes[1].assessment_status == "evidence_only"


def test_announcement_does_not_imply_completed_financing() -> None:
    """An announcement never becomes a completed exit."""
    payload = _source().model_dump(mode="json")
    payload["events"][0] |= {
        "kind": "acquisition",
        "stage": "announced",
        "occurred_on": "2025-03-01",
    }
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    event = next(row for row in alpha.statements if row.event_ids)
    assert event.text == "Acquisition announced; expected event date 2025-03-01."
    assert event.role == "observation"
    assert all(row.probability is None for row in alpha.outcomes)


def test_superseded_event_is_not_repeated_as_current_evidence() -> None:
    """An explicit correction removes the older statement from the assessed vintage."""
    payload = _source().model_dump(mode="json")
    revised = payload["events"][0] | {
        "event_id": "alpha-funding-correction",
        "stage": "completed",
        "supersedes_id": "alpha-funding",
    }
    payload["events"].append(revised)
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    assert [row.event_ids for row in alpha.statements if row.event_ids] == [
        ("alpha-funding-correction",)
    ]


def test_missing_family_stays_explicit_and_does_not_drop_company() -> None:
    """Unresolved source families remain explicit in assessed profiles."""
    payload = _source().model_dump(mode="json")
    payload["relationships"] = [
        row for row in payload["relationships"] if row["company_id"] != "alpha"
    ]
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, beta = build_company_assessments(source, source.recorded_at)

    assert alpha.family_id is None
    assert alpha.family_reason_codes == ("family_not_established_at_cutoff",)
    assert beta.family_id == "beta"


def test_company_identity_and_recording_must_be_valid() -> None:
    """The builder fails explicitly rather than dropping an unverified identity."""
    source = _source()
    with pytest.raises(ValueError, match="source publication"):
        build_company_assessments(
            source, source.recorded_at - timedelta(microseconds=1)
        )
    with pytest.raises(ValueError, match="UTC"):
        build_company_assessments(source, source.recorded_at.replace(tzinfo=None))
    payload = source.model_dump(mode="json")
    payload["evidence"][0]["review_state"] = "unreviewed"
    unverified = CompanySourceSnapshot.model_validate(payload)
    with pytest.raises(ValueError, match="identity requires verified public"):
        build_company_assessments(unverified, unverified.recorded_at)


def test_identical_source_and_recording_reproduce_exact_artifacts() -> None:
    """Changing input record order never changes assessed facts or immutable IDs."""
    source = _source()
    payload = source.model_dump(mode="json")
    for table in ("companies", "relationships", "evidence", "metrics", "events"):
        payload[table].reverse()
    reordered = CompanySourceSnapshot.model_validate(payload)

    first = build_company_assessments(source, source.recorded_at)
    replay = build_company_assessments(reordered, source.recorded_at)

    assert first == replay


def test_exact_decimal_values_are_not_rounded_through_binary_floats() -> None:
    """Commercial statements preserve exact source decimals and explicit currency."""
    payload = _source().model_dump(mode="json")
    row = next(
        row
        for row in payload["metrics"]
        if row["company_id"] == "alpha"
        and row["metric_id"] == "operating_cashflow_12m_usd_v1"
    )
    row.update(
        state="observed",
        value={"kind": "decimal", "value": "123456789012345678.19"},
        reason=None,
        evidence_ids=["alpha-source"],
    )
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    cashflow = next(row for row in alpha.statements if "cashflow" in row.statement_id)
    assert "123,456,789,012,345,678.19 USD" in cashflow.text
    assert alpha.outcomes[1].assessment_status == "evidence_only"


def test_restricted_family_and_event_evidence_are_not_exposed() -> None:
    """Public identities do not make private ownership or events publishable."""
    payload = _source().model_dump(mode="json")
    private = payload["evidence"][0] | {
        "evidence_id": "alpha-private-source",
        "access": "restricted",
        "url": None,
    }
    payload["evidence"].append(private)
    for relationship in payload["relationships"]:
        if relationship["company_id"] == "alpha":
            relationship["evidence_ids"] = [private["evidence_id"]]
    payload["events"][0]["evidence_ids"] = [private["evidence_id"]]
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    assert alpha.family_id is None
    assert alpha.family_reason_codes == ("family_not_established_at_cutoff",)
    assert all(not row.event_ids for row in alpha.statements)
    assert "alpha-private-source" not in alpha.model_dump_json()


@pytest.mark.parametrize("value,word", [(True, "yes"), (False, "no")])
def test_boolean_facts_do_not_become_numeric_scores(value: bool, word: str) -> None:
    """Boolean metric rendering retains the source meaning without a score."""
    payload = _source().model_dump(mode="json")
    payload["definitions"][0].update(value_kind="boolean", unit="status")
    for metric in payload["metrics"]:
        if metric["metric_id"] == payload["definitions"][0]["metric_id"]:
            metric["value"] = {"kind": "boolean", "value": value}
    source = CompanySourceSnapshot.model_validate(payload)

    alpha, _ = build_company_assessments(source, source.recorded_at)

    statement = next(
        row
        for row in alpha.statements
        if row.statement_id == "metric-alpha-sdk_downloads_30d_v1"
    )
    assert f": {word} status." in statement.text
    assert statement.role == "observation"
