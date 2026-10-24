# SignalShift

Startup outlook from dated evidence about traction, commercial health, execution
and financing. Search companies, inspect three separate outcome assessments and
compare relevant peers. [PLAN.md](PLAN.md) defines the revised product;
[issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19) coordinates it.

**Status:** real company source/assessment publication and verified recovery are
implemented. The initial Qdrant/Weaviate bundle includes dated public evidence and
explicit commercial gaps. A separate 229-company public discovery cohort retains
inactive/acquired companies without inventing historical labels. Company API/UI
integration is tracked in [the acceptance audit](docs/workstreams/dev1/STATUS.md).
No validated startup-success probabilities are claimed.

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
uv sync --frozen --no-dev --extra api --extra data
```

Extras reserve dependencies only; installing them does not implement features.
Notebook helpers are installed into the local virtual environment and are not
project requirements. An exact `uv sync` can remove those helpers; rerun
`make notebooks` or use `--inexact` when preserving them.

The optional environment template is `.env.example`. See the
[local runtime runbook](deploy/local/README.md) for explicit company publication
selection. Optional provider credentials do not activate services.

## Frontend and API

```bash
npm --prefix frontend run dev
```

See [frontend/README.md](frontend/README.md) for the frontend structure.
See [the API handoff](docs/workstreams/dev3/README.md) for backend startup and
repository wiring. Administrative data commands are available through
`python -m oxhack2026 data --help`; no `signalshift` shell entry point is installed.

## Verification

```bash
make check test build docs-test frontend-check
```

Python checks cover contracts, API behavior and saved synthetic fixtures.
Passing them does not establish real-data forecasting performance. Service
integration tests are opt-in with `make test-integration`; default tests require
no external services. CI installs all declared extras and runs shared checks.

## Layout

| Path | Responsibility |
| --- | --- |
| `oxhack2026/catalog`, `ingest`, `storage` | Source contracts, collection, publication and recovery |
| `oxhack2026/features`, `models`, `evaluation`, `explanations` | Model contracts, evidence assessments and research evaluation |
| `oxhack2026/api`, `frontend` | Public API and company workflow |
| `oxhack2026/cli` | Administrative commands |
| `contracts`, `configs`, `data/catalog` | Versioned schemas and nonsecret recipes/identity evidence |
| `artifacts`, `reports`, `tests/outputs` | Ignored generated data and retained validation artifacts |
| `deploy`, `docs/tasks` | Runtime/operations and reviewed handoffs |
| `migrations` | Reserved; no PostgreSQL migration acceptance yet |


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

Standalone startup research is available through the additive v2 backend. See the
[local worker setup, API sequence and evidence semantics](docs/tasks/dev3/research-v2.md).
It requires an explicit writable research root and opt-in collection worker; saved
company publications are optional. The existing frontend needs the corresponding
v2 domain-confirmation and multi-source presentation work before exposing this flow.
