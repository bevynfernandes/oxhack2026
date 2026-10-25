# SignalShift

Startup outlook from dated evidence about traction, commercial health, execution
and financing. Search companies, inspect three separate outcome assessments and
compare relevant peers. [PLAN.md](PLAN.md) defines the revised product;
[issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19) coordinates it.

**Status:** real company source/assessment publication and verified recovery are
implemented. The initial Qdrant/Weaviate bundle includes dated public evidence and
explicit commercial gaps. A separate 229-company public discovery cohort retains
inactive/acquired companies without inventing historical labels. Company API/UI
checks are retained in [the initial acceptance audit](docs/archive/workstreams/dev1/STATUS.md).
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

Notebook helpers are installed into the local virtual environment and are not
project requirements. An exact `uv sync` can remove those helpers; rerun
`make notebooks` or use `--inexact` when preserving them.

The optional environment template is `.env.example`. See the
[local runtime runbook](deploy/local/README.md) for explicit company publication
selection. Optional provider credentials do not activate services.

Five public-data dimension baselines have been trained, with 72 additional model
configuration fit attempts (71 converged), retained evaluation results and an
explicit descriptive AScore recipe. See the
[training results and top-three forecast mapping](docs/tasks/dev2/public-dimension-training-20261024.md)
and the earlier [source research](docs/tasks/dev2/public-model-research-20261024.md).
`python -m oxhack2026 models --help` exposes audits, `train-public`,
`compare-public`, and dated company-outcome experiments. The API loads a packaged, digest-verified baseline bundle and attaches
experimental model status to saved profiles and new research reports. Complete
matched npm windows receive an SDK-demand index; unsupported inputs abstain. The
three company-outcome cards remain unavailable, and execution inference is
withheld because its held-out benchmark is unreliable.

## Frontend and API

```bash
npm --prefix frontend run dev
```

See [frontend/README.md](frontend/README.md) for the frontend structure.
See [the local runtime runbook](deploy/local/README.md) for backend startup,
publication selection and worker configuration. Administrative data commands are
available through
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
| `oxhack2026/research` | Identity confirmation, durable jobs and source-linked reports |
| `contracts`, `configs`, `data/catalog` | Versioned schemas and nonsecret recipes/identity evidence |
| `artifacts`, `reports`, `tests/outputs` | Ignored generated data and retained validation artifacts |
| `deploy`, `docs/tasks` | Runtime/operations and reviewed handoffs |


## API container

See the [local runtime runbook](deploy/local/README.md) for the API container
recipe and its runtime configuration.

## Contributions

Current setup and review steps are in [CONTRIBUTING.md](CONTRIBUTING.md).
Historical plans, handoffs and completed checkpoints are indexed in
[the project archive](docs/archive/index.md).

Read [AGENTS.md](AGENTS.md) and [PLAN.md](PLAN.md). Keep generated datasets, credentials, and retained test
outputs out of version control.

Standalone startup research is available through the additive v2 backend. See the
[local worker setup, API sequence and evidence semantics](docs/tasks/dev3/research-v2.md).
It requires an explicit writable research root and opt-in collection worker; saved
company publications are optional. The frontend supports domain confirmation,
job progress, multi-source reports and explicit retained-evidence re-mapping.
