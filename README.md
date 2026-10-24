# SignalShift

Project template for the developer-tool scouting application described in
[PLAN.md](PLAN.md). The implementation plan remains the source of truth.

**Status: scaffold only.** Python modules reserve implementation boundaries;
the frontend renders a static template notice. There are no source connectors,
API endpoints, database models, forecasts, evaluation algorithms, CLI commands,
or cloud integrations yet.

## Development setup

Requirements: Git, uv, Python 3.12 (uv can install it), and Node.js 24 with npm.

```bash
make install
make notebooks
make frontend-install
```

The default Python installation includes development tools. Planned application
dependencies are opt-in extras, for example:

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
There is no backend server or `signalshift` CLI entry point at this stage.

## Verification

```bash
make check test build docs-test frontend-check
```

The Python tests check namespace imports only. Passing scaffold checks does not
validate any forecasting or product behavior. CI runs the same checks.

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
