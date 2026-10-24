# Dev 1: Data, storage, platform, and integration

## Active company-outlook checkpoints (2026-10-24)

[PLAN.md](../PLAN.md) and [issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19)
replace the download-only destination. Directory ownership remains unchanged.
The numbered D1 tasks below are retained implementation history/reusable work;
their old completion gates do not establish company-outlook completion.

| Task | Current deliverable | Acceptance |
| --- | --- | --- |
| D1-O1 | Additive company identity/metric/event/evidence/source snapshot contracts | Dev 2/3 review; strict fixtures and provenance/unknown/time invariants |
| D1-O2 | Real multi-family company evidence and dated mappings | Sources, gaps, raw hashes and independent bundle retrieval verified |
| D1-O3 | Exact-version source and assessment publication/readers | Compatible C1/C2 artifacts, atomic publication and failure/rollback tests |
| D1-O4 | Historical cohort source/discovery/follow-up ledger | Failed/inactive companies retained; missing labels visible; Dev 2 applies policy |
| D1-O5 | Integrate real company list/profile/compare | Real multi-family API/browser flow with all three outcome sections |
| D1-O6 | Bounded refresh and conditional deployment | No paid operation without verified access/credits; real operational checks |

Finish #17's package-attribution fix. Hold additional download-only expansion.
Implement [the source proposal](../docs/workstreams/dev1/STARTUP_OUTLOOK.md)
after consumer review. Private commercial data and a representative historical
labelled cohort are unresolved data-acquisition gates, not assumed inputs.

## Retained download workstream reference

**Branch:** `dev/data-platform`

**Role:** Deliver trustworthy versioned observations and the platform used by
the other developers. Coordinate shared configuration and merges.

Read [team coordination](README.md), [PLAN.md](../PLAN.md), and
[AGENTS.md](../AGENTS.md). This plan assigns implementation work; it does not
replace the original data, temporal, or credit requirements.

## 1. Outcome and ownership

Your completed work lets Dev 2 obtain a validated historical dataset and lets
Dev 3 read immutable published forecasts without knowing vendor or database
details.

Own:

- `oxhack2026/catalog/**`, `ingest/**`, and `storage/**` under the package.
- `migrations/**`, `data/catalog/**`, `deploy/**`.
- `contracts/datasets/data/**`, `configs/data/**`, `configs/platform/**`.
- Root CLI registration and data commands; not `cli/models.py` or
  `cli/demo.py`.
- Shared settings, root Python dependencies/lockfile, Makefile, CI, containers,
  devcontainer, environment/ignore templates, root documentation indexes.
- `tests/{unit,integration,fixtures}/data/**` and shared test infrastructure.
- `docs/workstreams/dev1/**` and `docs/tasks/dev1/**`.

Do not implement model policy, public API routes, or frontend screens.
Dev 2 owns forecast eligibility and numerical rules; Dev 3 owns public API
contracts and rendering. See the complete ownership table in the team guide.

## 2. Start your branch and environment

Branch only after the reviewed scaffold/plans are committed to shared main:

```bash
git fetch origin
git switch --create dev/data-platform origin/main
uv sync --frozen --inexact --all-extras --group docs
make notebooks
make check test
```

All extras are installed for whole-repository checks after teammate merges.
This does not activate integrations. Do not provision cloud resources or
execute paid jobs merely to set up your branch.

Your first integration change must establish CI dependency profiles before
feature PRs introduce imports from optional extras. The full verification job
installs all extras without requiring cloud credentials. Keep production API
dependencies separate from training-only dependencies and verify its lightweight
contract/scoring imports under that narrower profile.

Make service integration tests opt-in in the same bootstrap change. The current
plain pytest command does not exclude a registered integration marker. Configure
the default unit command to exclude integration tests and add an explicit
service-enabled integration command/job. Collection must not open connections.

## 3. D1-01: Publish C1 data contracts

This is your first small PR, separate from full ingestion/storage implementation.

Define lightweight types and schema exports for:

- Organization, tool, package, repository, and effective-dated mappings.
- Mapping evidence and catalogue version.
- Observation series and revisions.
- Source coverage and completeness.
- Availability basis: actual observation, vendor timestamp, or assumed lag.
- Dataset manifest and content-addressed artifact references.
- Artifact access and dataset read/publication interfaces.

Put public interchange types in `catalog/schemas.py` and new
`storage/contracts.py`; export schemas under `contracts/datasets/data/`.

Every observation must distinguish event/measurement time, publication evidence,
collection time, revision, and extraction version. Use integer counts and UTC
timestamps. Preserve missing values and explicit zeros separately.

Supply saved synthetic fixtures under your owned fixture paths covering:

- A complete series and an explicit zero.
- A missing day and an incomplete source.
- A late-arriving observation.
- A revised historical count.
- A renamed repository or changed package mapping.

Mark their provenance as synthetic. Have Dev 2 review availability semantics and
Dev 3 review fields needed for catalogue, history, and data-health responses.

**Done when:** schemas, labelled fixtures, compatibility rules, and lightweight
interfaces merge to main and both consumers can load them without a database,
credentials, or training imports.

## 4. D1-02: Catalogue and real npm ingestion

Follow PLAN.md section 4.

1. Verify ten diverse npm tools using official installation/repository evidence.
2. Record organization representatives before looking at future growth.
3. Preserve one primary package per tool/ecosystem and one representative per
   organization/ecosystem for the shortlist.
4. Implement catalogue validation and normalized identities.
5. Implement single-package, explicit-date npm daily extraction.
6. Convert inclusive source dates to half-open internal intervals.
7. Handle scoped package names, request limits, retries, and missing dates.
8. Save raw responses, hashes, extraction configuration, and checkpoints.
9. Record actual coverage; never invent pre-release history.
10. Expand the verified catalogue toward at least twenty organizations after
    the first integration path works.

Do not filter the cohort using eventual success. Keep mapping changes explicit
and retain historically eligible inactive tools.

Make extraction resumable and idempotent. Follow the fixed availability
assumptions for reconstructed history while retaining actual collection times.

**Deliver to Dev 2:** a real dataset candidate bundle, manifest, catalogue
snapshot, coverage report, hashes, and retrieval instructions.

**Done when:** real npm observations flow through validation, a rerun does not
duplicate facts, and late revisions remain distinguishable from prior versions.

## 5. D1-03: Local storage and atomic dataset publication

Prioritize the local path before managed-cloud deployment.

- Implement normalized relational entities and reviewed Alembic migrations.
- Use PostgreSQL/Timescale semantics compatible with the intended managed service.
- Use BIGINT counts, DATE where appropriate, and TIMESTAMPTZ instants.
- Keep source observations append-only by revision.
- Provide filesystem artifact storage and its contract-compatible future
  object-storage adapter.
- Keep credentials in environment configuration; imports open no connections.
- Upload/write artifacts, verify them, commit references, then advance the
  published pointer atomically.
- Leave the previous release usable after interrupted publication.
- Prevent duplicate jobs from publishing conflicting pointers.
- Provide read interfaces for catalogue, history, coverage, and dataset versions.

Implement the small forecast/evaluation storage extension only after C2 is
merged. Consume Dev 2's published contracts rather than inventing parallel ones.

Expose narrow repository operations needed by Dev 3, including saved forecast
batches, evidence, evaluations, and mature outcome access. SQL schemas and
migration ordering remain your responsibility.

**Done when:** Dev 2 can consume a frozen dataset and Dev 3 can read an imported
forecast batch using local services, without importing ingestion code.

## 6. D1-04: First end-to-end integration

Coordinate this sequence:

1. Merge your real-data publication checkpoint.
2. Have Dev 2 generate and publish baseline artifacts for that dataset.
3. Import/persist those artifacts using the C2 contract.
4. Have Dev 3 connect API/UI reads to the saved batch.
5. Run a complete historical forecast and reveal.
6. Verify old batches remain unchanged after a revised observation arrives.

Use actual baseline results for this milestone; a trained challenger is not a
dependency. Log exact dataset/model/batch versions in the integration handoff.

You coordinate the merge queue, but do not rewrite the other developers'
implementations to make the integration pass. Request bounded changes from the
owner and preserve the shared contracts.

## 7. D1-05: Operational pipeline and CLI registration

Implement data/platform CLI groups and root command registration:

- Catalogue validation.
- Source extraction.
- Dataset validation/publication.
- Artifact verification and data-health inspection.
- Registration of Dev 2's model group after it merges.
- Registration of Dev 3's demo group after it merges.

Keep commands as thin wrappers around reusable services.

Own job state, watermarks, advisory locks/leases, bounded retries, and scheduler
integration. Dev 2 provides training, forecasting, and outcome-scoring stages;
your worker invokes them according to the frozen recipe. The API never runs a
scheduler.

Add source refresh/revision handling, weekly forecasts, outcome maturation jobs,
and last-known-good publication behavior. Keep late jobs distinguishable from
forecasts recorded before their outcome window began.

## 8. D1-06: Additional sources and research support

After the npm vertical slice:

- Add PyPI only after schema inspection, dry runs, and verified credit limits.
- Apply the same distribution filter throughout history, including the August
  2026 definition change.
- Batch bounded extraction across packages instead of repeated full scans.
- Add GH Archive with deduplication, repository IDs, schema-version handling,
  and event-type coverage audits; exclude historical stars initially.
- Add HN with reviewed aliases, date subdivision, deduplication, and truncation
  detection.
- Produce source coverage reports and versioned observation artifacts for Dev 2.
- Preserve separate ecosystem datasets and mappings.

You supply evidence about source quality. Dev 2 decides whether each source
improves forecasts through controlled ablations. Do not claim added predictive
value merely because ingestion works.

## 9. D1-07: Tiger/Vultr deployment and credits

Follow PLAN.md section 10. Local completion is independent of cloud completion.

Before paid execution, establish:

- Verified provider balances, eligibility, expiry, unsettled usage, and prices.
- Transactional reservations with the specified safety reserve.
- BigQuery dry runs and maximum billed bytes.
- Stable job IDs and status reconciliation after timeout.
- Token/retry allowances for optional Gemini work supplied by Dev 2.
- A resource lease with export and cleanup procedures.

Unknown access or credits blocks that provider's paid work. Continue local tasks.

Deploy the web application supplied by Dev 3 and batch stages supplied by Dev 2
using separate runtime roles/processes. Own TLS, database roles, connection
limits, object storage, scheduling, monitoring, backups, restoration, and
rollback. Do not assume stopping a VM ends billing.

Keep the API image independent of training-only libraries where possible.
Pin tested images and release manifests. Do not publish frontend secrets.

**Done when:** CLOUD_READY is demonstrated; CLOUD_DEPLOYED is claimed only after
actual credited resources and deployment/restore checks pass.

## 10. Tests and acceptance

Add saved tests for new behavior, with external dependencies mocked in unit
tests. Integration tests use explicit local service setup.

Required cases:

- Identity normalization, duplicates, unverified mapping, repository rename.
- Inclusive npm bounds and scoped package handling.
- Missing versus zero, late arrival, revisions, and incomplete publication.
- Idempotent reruns and concurrent publication.
- Artifact corruption and incompatible schema versions.
- Dataset import/export preserving integer/null/time semantics.
- Forecast and outcome persistence preserving C2 separation.
- Budget reservation races, unknown credits, and duplicate paid-job prevention.
- Database outage, restore, rollback, and last-known-good behavior.
- No credential requirement during module import or unit-test collection.

Run:

```bash
make check test
uv run --frozen --no-sync pytest tests/unit/data
uv run --frozen --no-sync pytest -m integration tests/integration/data
make build docs-test
```

The new test directories/commands become meaningful when tests are implemented.
Do not mark an empty suite as an acceptance pass.

For integrated releases also run Dev 3's browser/offline suite and Dev 2's
reproducibility checks. Preserve test outputs.

## 11. Handoff and completion

Each handoff includes:

- Commit and task ID.
- Contract version and migration revision.
- Dataset/artifact IDs, hashes, location, and loading instructions.
- Source coverage and availability limitations.
- Commands/checks run.
- Required environment variable names without values.
- Remaining blockers and exactly which gate they affect.

Your branch is complete when real data, local storage, immutable publication,
job interfaces, and integration infrastructure work; optional cloud/source
gates remain explicitly reported if access prevents them.

## 12. Copy-paste Codex starting prompt

```text
Implement the Dev 1 workstream in plans/DEV_1_DATA_PLATFORM.md.
Read AGENTS.md, PLAN.md, and plans/README.md first. Work on
dev/data-platform from the committed shared scaffold.

Own data/catalogue ingestion, storage, migrations, platform/CI, root dependency
configuration, and integration wiring only. Follow the ownership exceptions
for cli/models.py and cli/demo.py. Do not edit PLAN.md.

Start with D1-01: a small data-contract and CI dependency-bootstrap change.
Keep real ingestion, persistence, and later cloud work in subsequent reviewable
checkpoints. Publish interfaces before consumers depend on them.

Use saved labelled fixtures to unblock teammates; do not call them real data.
Provide artifact hashes and transfer instructions for real datasets. Coordinate
root dependency and migration changes. Never exceed verified credits.

Run required checks, record a task handoff, and stop at a reviewable checkpoint
before moving to an unrelated subsystem. Do not merge or publish without the
developer's instruction. Continue independent owned work when an external gate
is blocked and report that gate honestly.
```
