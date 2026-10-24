# Dev 2 handoff

Scope: features, numerical policy, models, evaluation, and evidence from
`plans/DEV_2_MODELS_EVALUATION.md`. Root configuration and dependencies belong to
Dev 1; API/frontend belong to Dev 3.

## Current checkpoint

D2-01/C2 defines lightweight Pydantic contracts under `models/contracts.py` and
`evaluation/contracts.py`, with schemas under `contracts/datasets/models/` and
synthetic fixtures under `tests/fixtures/models/`. Imports do not load training
libraries or start services. Readiness is separate from evidence validation.
Unvalidated intervals stay absent; immature actuals stay null and cannot reveal.

```bash
uv sync --frozen --inexact --all-extras --group docs
uv run --frozen --no-sync python contracts/datasets/models/export.py
make check test
```

Integration requests:

- Dev 1: publish C1 and enable all declared extras in integration CI as required
  by the team guide. C2 uses existing dependencies; no additions requested.
- Dev 3: consume C2 forecast/outcome types separately and review saved rendering
  fixtures. Numerical ranking/scoring implementation follows in D2-02.

No real dataset, model performance, or product acceptance is claimed. Synthetic
artifact references use placeholder hashes and do not identify retrievable files.
Real baseline evaluation waits for a frozen, verified C1 npm bundle.

Merged: C2 PR #3, corrected author/sign-off `daniyalrai364@gmail.com`. Integration
with C3 passes 102 local tests; GitHub Python/frontend checks pass. Dev 3's merged
bootstrap enabled the existing declared extras in integration CI.

The overlapping shared policy implementation is coordinated through PR #4;
use that implementation rather than the retained local policy prototype.
D2-03a on `dev/models-baselines-v1` supplies aggregate baseline formulas and
tie-averaged comparator expectations. Its numerical tests pass on synthetic
counts. Real feature/label building and baseline artifacts still require C1.

Merged baseline formulas/comparators: PR #5. Shared policy: PR #4, reviewed
against the plan and checked together with baseline code (150 passing tests).
Ivan now owns Dev 1; this stream remains the authority for numerical policy.

D2-04a adds `origin_availability` and `calendar_protocol` for exact backwards
calendar membership. This independent infrastructure does not replace the C1
feature/label integration gate or establish a successful empirical experiment.

Per-tool reveal: `evaluation.metrics.outcome_diagnostics(forecast, outcome, as_of)`
returns the additive `OutcomeDiagnostics` contract. Dev 3 can use its realized
growth, model/baseline absolute count errors, and nullable unavailable states.
The helper enforces matching frozen identity/windows and the truth's collection
availability boundary before returning any actuals.

Merged chronological protocol: PR #6. Merged reveal diagnostics: PR #8.
D2-05a implements experimental CQR calculations with exact finite-sample order
statistics, model-digest pairing, and empirical serving rejection reasons.
No interval is validated by formula tests alone; actual chronological model
predictions and final coverage/baseline evidence remain required.
