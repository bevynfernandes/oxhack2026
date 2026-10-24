# Dev 2 handoff

Current product priority: [#19](https://github.com/bevynfernandes/oxhack2026/issues/19)
replaces download-only scouting with a multi-metric company outlook and all three
user-selected outcomes. `PLAN.md` and the Dev 2 role plan define the active scope;
`docs/tasks/dev2/company-outcome-policy.md` explains the label policy.
Existing download checkpoints below remain a traction subsystem. Their passing
tests do not demonstrate startup-success prediction.

Owner: numerical policy, features, models, evaluation, and evidence. Ivan owns
Dev 1 data/platform; Bevyn owns Dev 3 API/frontend. Follow `PLAN.md` and the
workstream boundaries in `plans/README.md`.

Company checkpoints:

- Calendar horizons and separate maturity/unknown-label contracts: #24.
- Three-section evidence-only assessment contracts and schema: #26.
- Outcome-specific chronological label selection and family exclusions: #29.
- Deterministic real-company assessments: #33, published through Dev 1's exact
  source/assessment store and verified in the real API. See
  `docs/tasks/dev2/company-evidence-builder.md` for policy and handoff details.
- Outcome-specific proper scores, discrimination and calibration diagnostics: #37.
- Multi-family numerical feature projection with shared evidence usability: #40.
- Training-only prevalence comparator: #42; explicit exclusions and no invented
  prior when mature labels are absent.

Earlier traction checkpoints:

- C2 contracts and synthetic fixtures: PR #3.
- Shared target windows, frozen organization ranking, and shortlist scores: #4.
- Aggregate baselines and exact tie-averaged comparators: #5.
- Whole-origin chronological evaluation protocol: #6.
- Separate per-tool reveal diagnostics: #8.
- Frozen-pair CQR calculations and empirical interval gates: #10.
- C1 daily vintage selection is implemented in `features.snapshots` (#15).
- `features.builders` provides download features and separate mature labels;
  catalogue-resolved requests and real artifact publication remain separate.

C1 is merged. The artifact-alignment checkpoint adopts C1's canonical reference
class with required size/media type: `models-v2` feature/forecast manifests and
`evaluation-v2` reports. Regenerate old drafts from verified bundle metadata.
No real version-1 artifact was published.

Dev 3 reuses `evaluation.shortlists` and
`evaluation.metrics.outcome_diagnostics(forecast, outcome, as_of)`; actuals stay
separate from immutable forecast payloads. CQR calculations are experimental
until real chronological predictions and final evidence pass every serving gate.

Catalogue resolution and callable baseline batch generation now consume C1
identities. Contemporary historical cohorts require explicit opt-in and retain
their retrospective/survivorship limitations.

Pending: company browser acceptance, historically justified features/families and
mature labels, learned outcome experiments, calibrated evaluation and the
probability-serving gate. Dev 1 has published real npm and
company source bundles; these are evidence inputs, not success-label cohorts.
Synthetic fixtures establish software behavior only; no empirical performance,
validated interval, real-data product completion, or cloud deployment is claimed.

Verification: `make check test`. Retained local logs are under
`tests/outputs/dev2-*/`; task-specific details are in `docs/tasks/dev2/`.
