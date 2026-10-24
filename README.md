# SignalShift

Project template for the developer-tool scouting application described in
[PLAN.md](PLAN.md). The implementation plan remains the source of truth.

**Status: contracts and API foundation.** C1 data types, C2 model types and C3
read-only API routes are implemented with synthetic contract tests. Source
ingestion, persistent repositories and real forecast datasets are not yet
available. An unconfigured API reports unavailable data rather than invented
results. See the workstream handoffs under `docs/workstreams/`.

## Development setup

Requirements: Git, uv, Python 3.12 (uv can install it), and Node.js 24 with npm.

```bash
make install
make notebooks
make frontend-install
```

The development installation includes all locked extras for shared checks.
Individual runtime environments can use narrower profiles, for example:

```bash
uv sync --frozen --inexact --extra api --extra data --group docs
```

Extras reserve dependencies only; installing them does not implement features.
Notebook helpers are installed into the local virtual environment and are not
project requirements. An exact `uv sync` can remove those helpers; rerun
`make notebooks` or use `--inexact` when preserving them.

The optional environment template is `.env.example`. Its empty credentials
and configuration names are placeholders; no service reads them yet.

## Preview the frontend template

```bash
npm --prefix frontend run dev
```

See [frontend/README.md](frontend/README.md) for the frontend structure.
See [the API handoff](docs/workstreams/dev3/README.md) for backend startup and
repository wiring. There is no `signalshift` CLI entry point at this stage.

## Verification

```bash
make check test build docs-test frontend-check
```

Python checks cover contracts, API behavior and saved synthetic fixtures.
Passing them does not establish real-data forecasting performance. Service
integration tests are opt-in with `make test-integration`; default tests require
no external services. CI installs all declared extras and runs shared checks.

## Layout

```text
oxhack2026/
  catalog/       Identity and mapping templates
  ingest/        npm, PyPI, GitHub, and HN adapter templates
  storage/       Database, artifact, and publication templates
  features/      Feature and label templates
  models/        Baseline, training, prediction, and calibration templates
  evaluation/    Split, metric, and experiment templates
  api/           Future application, schemas, and routes
  explanations/  Deterministic and Gemini templates
  cli/           Future command entry points
frontend/        Static React / TypeScript / Vite starter
contracts/       Reserved API and dataset contracts
configs/         Reserved non-secret configuration
migrations/      Reserved database migrations
data/            Catalogue documentation and ignored data directories
artifacts/       Ignored generated model and dataset artifacts
reports/         Ignored generated evaluation reports
demo/            Reserved real-data replay exports
tests/           Smoke checks and reserved unit/integration tests
deploy/          Local, Tiger, and Vultr deployment notes
docs/            Scaffold documentation and task handoff template
```

## Container template

`Dockerfile` builds a development shell image. Its default command is Bash;
it does not start an API, worker, or database, expose ports, or provision cloud
resources.

```bash
docker build -t signalshift-scaffold .
docker run --rm -it signalshift-scaffold
```

The devcontainer adds Node 24 and installs local development dependencies.

## Contributions

For the three-developer implementation split, start with
[the team guide](plans/README.md) and the individual workstream plans it links.

Read [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[PLAN.md](PLAN.md). Keep generated datasets, credentials, and retained test
outputs out of version control.
