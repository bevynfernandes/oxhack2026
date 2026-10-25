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
Growth and Survival forecasts and the combined Overall index remain unavailable,
and execution inference is
withheld because its held-out benchmark is unreliable.

A separate [dated bankruptcy experiment](docs/product/disclosure-bankruptcy-experiment.md)
has fitted eight scikit-learn classifiers across an initial study and a follow-up
using complete SEC history. The later holdout gave ROC AUC 0.603 on 689 issuers
with 14 positive cases and failed the frozen validation-loss gate. This research
model is not served; independent label/population review is also outstanding. It does
not replace the requested five business dimensions or private-startup forecasts.
See [FINAL_DEMO.md](FINAL_DEMO.md) for verified demo claims and remaining work.

A newer annual-financial experiment fitted eight classifiers on a fixed historical
320-issuer cohort, with 290 official SEC responses. Regularized logistic regression
for next-fiscal-year positive operating cash flow passed its statistical gate
(ROC AUC 0.869 on 49 rows from 25 test issuers). Revenue-growth candidates lost to
prevalence. The selected cash-flow weights are packaged as portable JSON and
match the fitted pipeline on all 4,462 panel rows. A reviewed SEC identity with
recent usable financials can now show dated original financial facts and an
explicitly experimental cash-flow estimate in the report. The packaged identity
catalog currently covers Cloudflare; other domains require reviewed mappings.
This component does not complete the five business dimensions or private-company
forecasts. See the [evaluation](docs/product/sec-cash-flow-evaluation.json) and
[real report audit](docs/product/sec-live-cash-flow-report-audit.json).

For local public-filings collection, configure `SEC_USER_AGENT` with your app and
contact in the ignored `.env`, then launch with `uv run --env-file .env ...`.
The API reads explicit process settings; it does not load that file implicitly.

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
The main company search accepts names and HTTPS websites. Name candidates come
from a bundled, attributed public domain directory and require identity preview;
names absent from the directory need an exact website. See
[current source/model limits](docs/product/free-source-decisions.md) and
[demo evidence and remaining work](FINAL_DEMO.md). Evidence mapping combines
deterministic rules with native `gemma-4-31b-it` interpretation by default.
Google Search discovery collects candidate pages separately from cited analysis;
set `SIGNALSHIFT_RESEARCH_GOOGLE_SEARCH=0` to disable discovery. Set
`SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules` to disable model requests.
It requires an explicit writable research root and opt-in collection worker; saved
company publications are optional. The frontend supports domain confirmation,
job progress, Fast/Thorough/Deep profiles, cited Gemini findings, explicit
continuation and retained-evidence re-mapping with cache reuse/bypass. Restart
the API worker after pulling implementation changes; capabilities expose its
start time and configured runtime revision.
