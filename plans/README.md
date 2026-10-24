# Three-developer implementation guide

## Current product and precedence

The company-outlook specification in [PLAN.md](../PLAN.md) supersedes the
original download-only product and its completion gates. Read the active
D1-O*, D2-O*, D3-O* checkpoint tables at the top of the role plans first.
The remaining guide preserves ownership, review, reproducibility and handoff
protocols. Its original five-company/download/offline-demo milestones are
historical reference and do not override the revised specification.

Dev 1 owns shared plan edits. Source contracts belong to Dev 1, outcome and
assessment rules to Dev 2, and API/UI projections to Dev 3. Agree additions in
[issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19); each consumer
reviews its boundary before contract freeze. The first product gate is a real
multi-family company assessment with three outcome sections and usable comparison.
A validated prediction model is a separate gate, not implied by that first flow.

## Existing engineering coordination

These plans divide implementation of SignalShift across three independent
developer branches. Read this guide with [PLAN.md](../PLAN.md) and
[AGENTS.md](../AGENTS.md). PLAN.md remains the product and research specification;
this guide assigns ownership and integration responsibilities.

The developers can assign their names to any role. Keep the role boundaries
stable after work begins. Dev 1 is the integration coordinator by default.

| Role | Individual plan | Branch |
| --- | --- | --- |
| Dev 1: data and platform | [Dev 1 plan](DEV_1_DATA_PLATFORM.md) | `dev/data-platform` |
| Dev 2: models and evaluation | [Dev 2 plan](DEV_2_MODELS_EVALUATION.md) | `dev/models-evaluation` |
| Dev 3: API and frontend | [Dev 3 plan](DEV_3_API_FRONTEND.md) | `dev/api-frontend` |

There is no deadline-driven feature cut. Work advances through verified
milestones. Existing credits/free quotas are the only financial allowance.

## 1. Publish the common starting point before branching

At the time these plans were written, the scaffold changes were still
uncommitted on `main`. A branch created from the old committed main will not
contain that scaffold.

Before implementation:

1. Review the scaffold and these plans together on main.
2. Commit the intended scaffold and planning files. Inspect the staged changes;
   do not blindly add local datasets, credentials, caches, or generated output.
3. Publish that commit to the team's shared main branch.
4. Record its SHA in the first task handoff. All three developers start there.
5. Each developer creates their own branch from the published main.

These documents do not create commits, branches, pull requests, or deployments.

On each developer's clean checkout:

```bash
git fetch origin
git switch --create dev/data-platform origin/main
```

Use the branch name from that developer's plan. If the branch already exists,
switch to it rather than recreating it. Do not discard local changes to make
these commands work.

Separate laptops need separate clones/branches. Concurrent agents on one
machine need separate worktrees; do not have multiple agents edit the same
working tree.

## 2. Directory ownership

An owner controls changes under a path, including its local documentation.
Other developers may read and import its public interfaces. Request a change
from the owner instead of silently editing another workstream.

| Paths | Owner |
| --- | --- |
| `oxhack2026/catalog/**`, `oxhack2026/ingest/**` | Dev 1 |
| `oxhack2026/storage/**`, `migrations/**` | Dev 1 |
| `data/catalog/**`, `data/README.md`, `deploy/**` | Dev 1 |
| `configs/data/**`, `configs/platform/**` | Dev 1 |
| `contracts/datasets/data/**` | Dev 1 |
| `oxhack2026/features/**`, `oxhack2026/models/**`, `oxhack2026/evaluation/**` | Dev 2 |
| `oxhack2026/explanations/**`, `configs/experiments/**` | Dev 2 |
| `contracts/datasets/models/**` | Dev 2 |
| `oxhack2026/api/**`, future `oxhack2026/demo/**`, `frontend/**`, root `demo/**` | Dev 3 |
| `contracts/api/**`, `configs/api/**` | Dev 3 |
| `oxhack2026/cli/models.py` | Dev 2 |
| `oxhack2026/cli/demo.py` | Dev 3 |
| Remaining `oxhack2026/cli/**`, including root registration | Dev 1 |
| Shared settings, root package initialization, root Python configuration and lockfile | Dev 1 |
| `frontend/package.json`, `frontend/package-lock.json` | Dev 3 |
| Root Makefile, Dockerfile, devcontainer, CI, ignore files, environment template | Dev 1 |
| Root documentation/indexes and contract/config index READMEs | Dev 1 |
| `tests/{unit,integration,fixtures}/data/**` | Dev 1 |
| `tests/{unit,integration,fixtures}/models/**` | Dev 2 |
| `tests/{unit,integration,fixtures}/api/**`, frontend tests | Dev 3 |
| Root/shared `tests/conftest.py` and existing scaffold smoke checks | Dev 1 |
| `docs/workstreams/dev1/**`, `docs/tasks/dev1/**` | Dev 1 |
| `docs/workstreams/dev2/**`, `docs/tasks/dev2/**` | Dev 2 |
| `docs/workstreams/dev3/**`, `docs/tasks/dev3/**` | Dev 3 |

Some listed subdirectories are planned additions rather than existing files.
Create them only when the corresponding work begins.

Generated data, models, reports, and test outputs are not shared source files.
Write to versioned/run-specific directories; preserve outputs and follow the
repository ignore policy. Dev 1 extends ignore rules before new generated
locations, including demo exports, are introduced.

Only Dev 1 changes `pyproject.toml` and regenerates `uv.lock`. Dev 3 independently
owns the frontend manifest and lockfile. Request Python dependencies through a
small Dev 1 integration change; never edit a lockfile manually or install an
undeclared project dependency as a permanent workaround.

Do not rewrite PLAN.md or AGENTS.md as part of a feature task. Product changes
need an explicit team decision and a separately reviewed specification change.

## 3. Three early contract checkpoints

The scaffold has no implemented contracts yet. Publish three small contract
changes before integrating full features:

| Checkpoint | Author | Required deliverables |
| --- | --- | --- |
| C1: data contracts | Dev 1 | Catalogue, observations, coverage, dataset manifest, artifact references, storage read/write interfaces, and labelled fixtures |
| C2: model contracts | Dev 2 | Features/labels, forecast and outcome artifacts, evaluation/evidence artifacts, numerical policy interfaces, and labelled fixtures |
| C3: application contracts | Dev 3 | Public Pydantic API schemas, OpenAPI, generated TypeScript types, request/error cases, and labelled fixtures |

Review responsibilities:

- Dev 2 reviews C1 availability, identity, and dataset boundaries.
- Dev 3 reviews C2 fields needed by charts, rankings, evidence, and reveal.
- Dev 1 reviews C3 storage access, deployment requirements, and response safety.

Each checkpoint merges to main and is incorporated into the other branches.
C2 can be drafted while C1 is reviewed; C3 can be drafted while C2 is reviewed.
Freeze the final fields on the merged contracts rather than maintaining three
incompatible copies.

The first Dev 1 integration change must also update CI installation profiles.
Current scaffold CI installs only development/docs dependencies. It will not
support later imports of FastAPI, Polars, or CatBoost without that change.
The full verification job and developer environments must install all declared
extras so whole-repository mypy/pytest checks still work after other branches
merge. Keep production API and worker installation profiles narrower. Installing
a cloud client library neither requires credentials nor authorizes paid calls.

Dev 1 also makes service integration tests explicitly opt-in. Registering the
pytest integration marker alone does not exclude those tests from plain pytest.
The default unit-check command must exclude them; a separate command/job enables
them only with the documented local services available. No test may connect to a
service at import/collection time.

### Contract locations and import direction

- Dev 1: `catalog/schemas.py` and new `storage/contracts.py`.
- Dev 2: new `models/contracts.py` and `evaluation/contracts.py`.
- Dev 3: `api/schemas.py`; generated OpenAPI under `contracts/api/`.
- JSON Schema exports belong under each owner's contract directory.

Contract modules import lightweight types only. They must not open database
connections, import training services, register CLI commands, or start an API.

The dependency direction is:

```text
catalogue / observation / artifact types
                  |
                  v
forecast / evaluation / numerical policy types
                  |
                  v
public API schemas -> generated TypeScript types
```

Storage implementations may consume the merged forecast contracts. Model
services consume storage interfaces. Neither subsystem's contracts import the
other subsystem's implementation.

### One owner for numerical policy

Dev 2 implements target windows, history/growth eligibility, ranking,
organization deduplication, and manual-shortlist scoring.

Expose lightweight pure helpers, preferably in
`evaluation/shortlists.py`, without CatBoost, database, or network imports.
Dev 3 calls those helpers or reads saved results. Dev 3 must not independently
reimplement these rules in Python API code or TypeScript.

Dev 1 validates source-level facts, mappings, counts, and completeness.
Forecast/ranking eligibility remains Dev 2's policy.

## 4. Artifact handoff

Use schemas and saved fixtures to work independently; use immutable real
artifacts to satisfy integration gates.

| Artifact | Producer | Consumers | Minimum content |
| --- | --- | --- | --- |
| Catalogue snapshot | Dev 1 | Dev 2, Dev 3 | Identities, organization representatives, effective mappings, evidence/version IDs |
| Observation snapshot | Dev 1 | Dev 2, Dev 3 | Count/interval, source, availability basis, revision, coverage and provenance |
| Dataset manifest | Dev 1 | Dev 2, Dev 3 | Dataset/catalogue/mapping versions, source/filter/lag policy, artifact hashes and relative locations |
| Features and labels | Dev 2 | Dev 2 | Typed rows, exact windows, eligibility, label availability, schema version |
| Forecast batch | Dev 2 | Dev 1 storage, Dev 3 API | Target, decision cutoff, estimates, baselines, evidence, quality and model/data versions |
| Outcome artifact | Dev 2 | Dev 1 storage, Dev 3 reveal | Separately stored mature actuals, outcome vintage and scoring inputs |
| Evaluation/evidence artifacts | Dev 2 | Dev 1 storage, Dev 3 | Metric definitions, periods, counts, baseline comparisons, source observations |
| Offline demo bundle | Dev 3 | Whole team | Compatible published artifacts, API-contract version, hashes and real-data provenance |

Preferred artifact names inside versioned bundles:

- `dataset_manifest.json`, `catalog.json`, `observations.parquet`.
- `feature_manifest.json`, `features.parquet`, `labels.parquet`.
- `forecast_manifest.json`, `forecasts.parquet`, `outcomes.parquet`.
- `evaluation.json`, `evidence.json`.

C1-C3 define exact field names, Arrow types, nullability, enums, schema versions,
and compatibility rules. The table does not replace those schemas.

Transfer rules:

1. Git stores source, schemas, configuration, and small labelled fixtures.
2. Real datasets/models use immutable bundles with checksums.
3. Before cloud storage is available, transfer a compressed bundle through the
   team's existing file-sharing channel. Include its location and hash in the
   handoff; another developer's absolute local path is not a distribution method.
4. Resolve relative artifact paths against the receiver's configured data root.
5. Later use credited object storage through Dev 1's artifact interface.
6. Never commit secrets or credential-bearing download URLs.
7. A manifest pointing to inaccessible files is an incomplete handoff.

Synthetic fixtures must have unmistakable synthetic provenance. They enable
contract tests, model development, and UI work, but cannot satisfy a real-data
acceptance gate. No demonstration may quietly fall back to invented forecasts.

## 5. Work in parallel, merge in checkpoints

Use the three named developer branches, with small reviewed checkpoints from
each branch. Do not wait until three complete applications exist before merging.

| Round | Dev 1 | Dev 2 | Dev 3 | Integration result |
| --- | --- | --- | --- | --- |
| 0 | C1 and CI/dependency bootstrap | Draft C2 and boundary fixtures | Draft C3 and component states | Shared contracts on main |
| 1 | Verified npm dataset and local storage | Temporal builders and baselines on fixtures | Contract-backed API/UI development | Independent work against the same interfaces |
| 2 | Real data publication and repository reads | Real baseline forecasts and evaluation artifacts | API/UI consumes real batch and reveals outcomes | Real npm vertical slice |
| 3 | Expanded cohort, durable publication, job controls | Learned challengers and honest validation | Full rankings, detail, evaluation and browser tests | Complete local product |
| 4 | Credit-gated PyPI/GitHub/HN and deployment | Source ablations, intervals, medium-term model | Additional-source rendering and offline demo | Research and sponsor extensions |

Npm data and baseline integration precede optional services. Dev 1 must not
spend the first phase on cloud deployment while the other branches lack a
usable dataset and storage contract.

The baseline product remains useful if a learned model loses or the data cannot
support a strong research claim. Publish those findings; do not relax the
specification to manufacture a pass.

## 6. Branch synchronization and pull requests

After another checkpoint merges, incorporate updated main into your branch:

```bash
git fetch origin
git switch dev/data-platform
git merge origin/main
```

Replace the branch name for your role. Commit your own reviewed work before a
merge; do not reset or auto-stash another person's changes.

Use ordinary merge commits for shared checkpoints on these continuing branches.
This preserves ancestry across repeated merges. If the team instead requires
squash merges, create a fresh task branch from updated main after each merged
checkpoint rather than repeatedly reusing a squashed history.

Do not cherry-pick the same shared contract commit independently into all
branches. Merge it through main and update each branch. Do not force-push
another developer's branch.

Each PR includes:

- Task/checkpoint ID and owned paths.
- Concrete resulting behavior.
- Contract/dependency changes.
- Tests and commands run.
- Fixture or real-artifact versions and retrieval instructions.
- Known limitations and external blockers.

Keep one open checkpoint PR per continuing developer branch. Do not push an
unrelated next checkpoint onto that branch while its previous tip is under
review. Prepare later work locally or on an isolated task branch, then integrate
it after the earlier checkpoint merges.

Dev 1 coordinates the merge queue; the author does not self-approve their
cross-stream contract change. Fix ownership conflicts with the relevant owner.

## 7. CLI and runtime integration

Dev 1 owns the root CLI registration and runtime configuration. Planned command
groups are `catalog`, `ingest`, `dataset`, `models`, and `demo`.

- Dev 1 registers data/platform commands.
- Dev 2 supplies `cli/models.py` with the model/evaluation subcommands.
- Dev 3 supplies `cli/demo.py` with offline export commands.
- Dev 1 wires the merged command groups into the root entry point.

Executable demo/export and offline-serving code belongs in the new package
`oxhack2026/demo/`, owned by Dev 3. Root `demo/` holds documentation and approved
sample manifests/artifacts; it is not installed as Python code by the current
wheel configuration. Reuse Dev 1's artifact validation/read interfaces in the
offline adapter rather than creating another persistence system.

Do not reference unmerged command modules or advertise commands as working
before their implementation is present.

Dev 1 owns operational orchestration: cost reservations, source refresh,
training invocation, forecast-publication scheduling, outcome-scoring
scheduling, and deployment. Dev 2 supplies callable pipeline stages and their
configuration; Dev 3 supplies the web app and exporter.

The web API never trains a model, fetches vendor data, or makes paid model calls
during a browser request.

## 8. Verification and review

All roles follow AGENTS.md and PLAN.md. Python remains 3.12, dataframe work uses
Polars, and JSON I/O uses orjson. Never fabricate metrics or silently replace
missing data with zero.

Run current scaffold checks with:

```bash
uv sync --frozen --inexact --all-extras --group docs
make check test
```

The full local dependency profile prevents another workstream's merged imports
from breaking global type checking or test collection. A focused environment is
valid for a scoped task, but is not a substitute for the full integration check.

Each role also runs task-specific saved tests. New test suites are added with
the implementation, not represented by empty scripts that always pass.

Integration responsibilities:

- Dev 2 reviews temporal integrity of Dev 1's data output.
- Dev 3 reviews usability and reveal separation of Dev 2's output.
- Dev 1 reviews storage/security/deployment integration of Dev 3's output.
- Dev 3 owns the full browser replay test and no-network demo test.
- Dev 1 wires these tests into CI and manages the release manifest.
- Dev 2 owns reproducibility and leakage tests for training/evaluation.

Each developer retains test output under a distinct run directory.
Benchmarks run serially; model training and paid extraction are coordinated to
avoid duplicate work and resource contention.

A blocked external dependency does not authorize bypassing credit limits or
substituting fake results. Record the blocker, continue independent owned work,
and identify exactly which acceptance gate remains unmet.

## 9. Final integration gate

Dev 1 coordinates a release candidate containing:

1. Verified real catalogue and npm observations.
2. Immutable dataset and compatible model/baseline artifacts.
3. Reproducible temporal evaluation and transparent limitations.
4. Working API, five-company shortlist, detail, reveal, and evaluation views.
5. Evidence explanations backed by source records.
6. Passing leakage, contract, browser, packaging, and quality checks.
7. A complete offline real-data demo.
8. Deployment readiness documentation and, only where credits permit, tested
   Tiger/Vultr deployment.

Keep PLAN.md completion states separate: LOCAL_COMPLETE, SECOND_ECOSYSTEM_COMPLETE,
CLOUD_READY, CLOUD_DEPLOYED, EXPLANATIONS_ENABLED, and prospective validation.
A functioning local app is not evidence of a deployed sponsor integration.
