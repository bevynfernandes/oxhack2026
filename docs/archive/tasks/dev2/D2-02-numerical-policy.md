# D2-02: numerical policy checkpoint

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


- Owner: Dev 2, `codex/dev2-numerical-policy`.
- Base: published C2 branch `dev/models-evaluation` (`6efac6a`). A concurrent
  C2 draft was preserved locally on `codex/dev2-c2-local-draft`; this checkpoint
  adopts the published contracts rather than shipping a second schema design.
- Owned paths: `features/definitions.py`, `evaluation/shortlists.py`, C2 validator
  reuse, `tests/unit/models/test_numerical_policy.py`, this task and handoff docs.
- Inputs: C2 forecasts/outcomes and the batch's frozen organization-to-tool mapping.
- Outputs: canonical target windows, display rankings, authoritative manual scores.
- Dependencies: C1 supplies validated dataset and effective representative mapping;
  Dev 3 consumes these helpers through its repository adapter.
- Fixture provenance: existing synthetic C2 fixtures; no empirical performance claim.
- Services/cost: none; existing declared dependencies only, installed locally.

Acceptance: Monday/UTC boundaries; no shifted anchor; exact target windows;
pre-target publication; fixed representative selection; reference threshold;
consistent candidate universe; complete mature truth; shortlist edge cases.

Handoff: `make check test` passes (Ruff, formatting, mypy, all 75 tests), with
11 new numerical-policy cases. Retained local log:
`tests/outputs/dev2-numerical-policy-20261024/check-test.log`.
Consumer notes: `docs/workstreams/dev2/numerical-policy.md`.
This is the numerical-policy part of D2-02. Observation
adapters, vectorized features/labels, baseline experiments, and real artifacts
remain blocked on C1 integration and are not claimed complete here.
