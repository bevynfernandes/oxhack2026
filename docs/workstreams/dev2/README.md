# Dev 2 handoff

Owner: numerical policy, features, models, evaluation, and evidence. Ivan owns
Dev 1 data/platform; Bevyn owns Dev 3 API/frontend. Follow `PLAN.md` and the
workstream boundaries in `plans/README.md`.

Merged checkpoints:

- C2 contracts and synthetic fixtures: PR #3.
- Shared target windows, frozen organization ranking, and shortlist scores: #4.
- Aggregate baselines and exact tie-averaged comparators: #5.
- Whole-origin chronological evaluation protocol: #6.
- Separate per-tool reveal diagnostics: #8.
- Frozen-pair CQR calculations and empirical interval gates: #10.

C1 is merged. The artifact-alignment checkpoint adopts C1's canonical reference
class with required size/media type: `models-v2` feature/forecast manifests and
`evaluation-v2` reports. Regenerate old drafts from verified bundle metadata.
No real version-1 artifact was published.

Dev 3 reuses `evaluation.shortlists` and
`evaluation.metrics.outcome_diagnostics(forecast, outcome, as_of)`; actuals stay
separate from immutable forecast payloads. CQR calculations are experimental
until real chronological predictions and final evidence pass every serving gate.

Pending: C1-backed feature/label builders, a frozen verified npm dataset, real
baseline handoff, learned experiments, full metrics/evidence, and model CLI.
Synthetic fixtures establish software behavior only; no empirical performance,
validated interval, real-data product completion, or cloud deployment is claimed.

Verification: `make check test`. Retained local logs are under
`tests/outputs/dev2-*/`; task-specific details are in `docs/tasks/dev2/`.
