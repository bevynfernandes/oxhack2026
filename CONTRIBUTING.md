# Contributing to SignalShift

Read [AGENTS.md](AGENTS.md) for code-quality requirements and [PLAN.md](PLAN.md)
for product, data, temporal and evaluation decisions. Current runtime instructions
are in [deploy/local/README.md](deploy/local/README.md).

## Setup and checks

Use Python 3.12, uv and the Node 24 version pinned in `frontend/.nvmrc`:

```bash
make install notebooks frontend-install
make check test build docs-test frontend-check
npm --prefix frontend run format:check
npm --prefix frontend run test
```

Optional Git hooks can be installed with `uv run --no-sync pre-commit install`.
Run `make format` explicitly when changing Python formatting. Browser setup and
commands are documented in [frontend/tests/README.md](frontend/tests/README.md).

## Changes and pull requests

Use an isolated branch/worktree for each bounded change. Describe the resulting
behavior, affected interfaces and validation in the PR. Coordinate shared
contracts and manifests with other open changes before editing them.

Change Python dependencies through uv and frontend dependencies through npm;
include the corresponding lockfile. Install only the extras needed by the runtime.
Run benchmarks serially.

Python types are the source of truth for contracts. Regenerate the affected
schemas and frontend types when changing an interface, and run the saved drift
tests. See [contracts/README.md](contracts/README.md) for export commands.

## Tests and artifacts

Save tests before running them. Use pytest for Python unit tests and mock external
dependencies. Service-dependent tests belong in `tests/integration/` and must be
opt-in. Keep synthetic fixtures clearly labelled and separate from real-data
acceptance; software tests do not prove model performance.

Retain generated test outputs under `tests/outputs/<run-id>/`; do not delete them
automatically. Keep generated datasets and credentials out of commits, and never
place secrets in test fixtures or logs.

The [project archive](docs/archive/index.md) preserves the original workstream
plans and completed handoffs for historical reference.
