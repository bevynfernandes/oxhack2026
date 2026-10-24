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

Next: D2-02 temporal builders and ranking policy, followed by D2-03 baselines.
Contracts remain a checkpoint draft until cross-stream compatibility is checked.
