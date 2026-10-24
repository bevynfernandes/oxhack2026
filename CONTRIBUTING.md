# Contributing to SignalShift

Read `AGENTS.md` for code-quality requirements and `PLAN.md` for product,
data, temporal, and evaluation decisions.

## Setup and checks

Use Python 3.12, uv, and Node 24:

```bash
make install notebooks frontend-install
make check test build docs-test frontend-check
```

Optional Git hooks can be installed with `uv run --no-sync pre-commit install`.
Run `make format` explicitly when changing Python formatting.

## Scaffold boundaries

Most Python files contain only module docstrings. Their presence does not mean
the subsystem exists. Introduce executable product code in bounded follow-up
tasks with the appropriate saved tests and documentation.

Keep source fixtures clearly labelled. Do not use invented forecasts or
unverified catalogue entries in a product demonstration.

## Parallel work

Follow [the three-developer team guide](plans/README.md) for branch ownership,
shared contracts, artifact handoffs, and checkpoint merge order.

Use an isolated branch/worktree for each task and declare owned paths in a copy
of `docs/tasks/TEMPLATE.md`. The integration owner coordinates contracts,
root dependency manifests/lockfiles, and migration ordering.

Change dependencies through uv or npm and include the corresponding lockfile.
Install only the extras needed by the task. Keep benchmark execution serial.

## Tests and artifacts

Save tests before running them. Mock external dependencies in unit tests.
Service-dependent tests belong in `tests/integration/` and must be opt-in.
Retain generated test outputs under `tests/outputs/<run-id>/`; do not delete
them automatically. Never place secrets in test fixtures or logs.
