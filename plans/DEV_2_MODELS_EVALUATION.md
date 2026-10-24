# Dev 2: Features, models, evaluation, and evidence

## Active company-outlook checkpoints (2026-10-24)

[PLAN.md](../PLAN.md) and [issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19)
replace the package-growth ranking objective. Directory ownership remains
unchanged. The numbered D2 tasks below preserve reusable download research;
their targets and completion gates do not define company outcomes.

| Task | Current deliverable | Acceptance |
| --- | --- | --- |
| D2-O1 | Three outcome definitions and separate label/assessment contracts | Reviewed observable labels, calendar horizons, maturity and unknown/conflict semantics |
| D2-O2 | Deterministic evidence assessment consuming exact C1 records | Evidence-linked factors/risks, explicit missingness, no arbitrary probability |
| D2-O3 | Cohort eligibility, multi-family features and mature labels | Historical inclusion/family control; no future evidence or silent negative labels |
| D2-O4 | Outcome-specific baselines/models and chronological evaluation | Coverage, calibration, baseline comparison, frozen final holdout and release criteria |
| D2-O5 | Published assessments/evaluations and prediction eligibility | Exact immutable artifacts; Dev 3 renders probability only through passed gate |

Outcome IDs and initial policy are proposed in
[PR #22](https://github.com/bevynfernandes/oxhack2026/pull/22).
Preserve different reasons for shutdown, nongrowth and negative cash flow. Name
the commercial target cash-flow self-sufficiency until a broader measurable
viability definition is agreed. Downloads remain a traction feature; they
cannot satisfy company commercial labels or establish predictive validity.

## Retained download workstream reference

**Branch:** `dev/models-evaluation`

**Role:** Turn frozen observations into defensible forecasts and measure whether
the resulting five-company shortlist improves the scouting decision.

Read [team coordination](README.md), [PLAN.md](../PLAN.md), and
[AGENTS.md](../AGENTS.md). Follow PLAN.md sections 3, 6, and 7 exactly for target,
temporal, and research rules.

## 1. Outcome and ownership

Your completed work produces versioned feature/label datasets, baseline and
learned forecasts, calibrated uncertainty where supported, evaluation reports,
and evidence summaries that Dev 3 can display without running model training.

Own:

- `oxhack2026/features/**`, `models/**`, `evaluation/**` under the package.
- `oxhack2026/explanations/**`.
- `oxhack2026/cli/models.py`.
- `contracts/datasets/models/**`, `configs/experiments/**`.
- `tests/{unit,integration,fixtures}/models/**`.
- `docs/workstreams/dev2/**`, `docs/tasks/dev2/**`.
- Generated model, feature, and report artifacts under versioned ignored paths.

Do not write source adapters, database migrations, API routes, or frontend code.
Request Python dependency changes from Dev 1. Do not edit root lockfiles.

You own all numerical policy, including pure ranking and shortlist-scoring
helpers used by the API. Dev 3 must not duplicate your target or scoring rules.

## 2. Start your branch and environment

After the common scaffold is committed and published:

```bash
git fetch origin
git switch --create dev/models-evaluation origin/main
uv sync --frozen --inexact --all-extras --group docs
make notebooks
make check test
```

All extras support whole-repository checks after teammate merges. Credentials
are not prerequisites for model development or unit-test collection. Gemini
remains disabled until its implementation and credit gates pass; the API's
narrower production profile must not need your training-only dependencies.

Work initially against saved synthetic observations matching C1. Start real
experiments only when Dev 1 provides a validated real dataset and manifest.

## 3. D2-01: Publish C2 model and numerical contracts

Review C1 first, especially availability, revision, and missingness semantics.

Publish a small contract PR defining:

- Typed feature and label rows/manifests.
- Target ID, ecosystem, decision cutoff, and exact reference/target intervals.
- Model run and model/calibration pair references.
- Forecast batch manifest and result rows.
- Separate mature-outcome records.
- Evaluation report, metric-definition, and cohort-count structures.
- Evidence records that refer to dated source observations.
- Lightweight ranking and manual-shortlist-scoring interfaces.

Place public types in `models/contracts.py` and `evaluation/contracts.py`.
Export schema files under `contracts/datasets/models/`.

Keep public contract modules free of training, database, and paid-service
imports. Keep actual outcomes out of the forecast-result contract.

Supply labelled fixtures for ready, insufficient-history, low-reference-count,
missing-source, unvalidated-interval, immature-outcome, and baseline cases.
Dev 3 reviews them for rendering and replay needs; Dev 1 reviews persistence.

**Done when:** C2 merges to main, fixtures validate, and consumers can import the
contracts without importing CatBoost or starting any external service.

## 4. D2-02: Temporal builders and a single numerical policy

Implement one source of truth for:

- Monday 00:00 UTC decision origins.
- Fixed observation anchor `a = t - 48 hours`.
- Half-open intervals.
- Next-30-day target and its reference window.
- Separate 91-day/trailing-28-day target definition.
- Required 84-day complete feature history.
- Percentage-growth ranking only at reference counts of at least 1,000.
- Mature-label rules and actual collection cutoff in prospective mode.
- Organization representative selection/deduplication under the frozen mapping.

Use the worked dates in PLAN.md section 3 as saved boundary fixtures.
Do not move the anchor to fill missing data.

Build features with Polars using shared rolling computations, not a Python
loop rescanning each tool's full history at every cutoff. Fit learned
preprocessing only on the training fold.

Produce versioned feature and label artifacts with availability and eligibility
metadata. Keep immature labels missing.

Implement lightweight pure helpers in `evaluation/shortlists.py` for ranking,
eligibility presentation, and manual-shortlist scores. Use standard-library
operations where practical so API imports do not pull in training packages.

**Done when:** future-available observations, revised prospective vintages,
boundary dates, and incomplete labels are all handled by saved tests.

## 5. D2-03: Baselines and the first real forecast handoff

Implement:

1. Persistence.
2. Weekday seasonal baseline.
3. Damped recent trend, including clipping, damping, and midpoint scaling.
4. Recent growth and popularity ranking comparators.
5. Random/tie-aware comparator behavior.

Do not present persistence's tied zero-growth predictions as a meaningful
alphabetical ranking.

Once Dev 1 supplies a real npm dataset:

- Load only the frozen dataset version.
- Build real eligible rows.
- Generate reproducible baseline forecasts.
- Publish a C2-compatible batch and separate outcome artifact.
- Produce an initial honest report with actual data periods and sample counts.
- Mark evidence exploratory when the required history is insufficient.

Give Dev 1/3 the artifacts, hashes, schema versions, and retrieval instructions.

**Done when:** Dev 3 can render a real baseline forecast/reveal through Dev 1's
storage. This handoff does not wait for CatBoost or validated intervals.

## 6. D2-04: Learned forecasts and chronological evaluation

Implement the predeclared ladder from PLAN.md:

- Ridge on log-growth residuals with training-only preprocessing.
- CatBoost quantiles with the specified bounded development search.
- Separate pooled models for every ecosystem/target.
- No per-tool overfit model collection or pooled npm/PyPI target.
- Correct estimate kinds; log-space RMSE output is not automatically a median.

Build calendar-based splits across whole origins. Follow the backwards split
construction in PLAN.md section 7:

- Three 13-origin development blocks with sufficient earlier training origins.
- Separate 26-origin calibration period.
- Separate 26-origin initial final test.
- Label-availability purges at every boundary.
- Required feature lookback before eligible origins.

Freeze an experiment manifest before final-test access. It includes cohort,
mapping, source/lag policy, features, candidate models, hyperparameters, seeds,
ranking rules, metrics, and release gates.

Use the primary decision metric and forecast-error guardrail from PLAN.md.
Select the challenger and fallback on development, not on the final holdout.

**Done when:** experiment reproduction recovers split membership and reported
metrics; a failed or inconclusive challenger remains honestly reported and the
preregistered baseline can be served.

## 7. D2-05: Uncertainty, transfer, and dependence

Implement:

- Model/calibrator pair persistence.
- Chronological CQR construction from PLAN.md.
- Quantile-crossing handling and diagnostic reporting.
- Coverage, width, pinball loss, and interval score.
- Explicit minimum-support and subgroup gates.
- Company-family held-out evaluation.
- Paired origin/block-based comparisons.
- Nonoverlapping-origin and lag-policy sensitivity.

Do not refit a model on calibration labels while keeping its old correction.
Do not advertise exact p10/p90 semantics for conformally adjusted interval
endpoints.

Report effective block counts. A short holdout supports descriptive evidence,
not an automatic statistical-superiority claim. Real prospective outcomes
require elapsed time.

Intervals that fail serving gates remain in experimental reports but are absent
from the validated product band.

## 8. D2-06: Evidence and optional source ablations

Produce deterministic evidence summaries from permitted source observations:

- Measured download changes.
- Source windows and availability.
- Model/baseline differences.
- Missing-source limitations.
- Predictive, non-causal interpretations.

Keep numerical predictions authoritative outside any LLM output.

After Dev 1 supplies audited GitHub/HN data, evaluate downloads-only, +GitHub,
+HN, and combined models on identical rows and candidate sets. Report coverage
and abstention as well as conditional accuracy. Source ingestion success alone
does not establish predictive value.

Add the separate PyPI and 91-day experiments only after their own data gates.
Keep their models, calibration, scores, and reports separate.

Gemini remains optional and batch-only:

- Use a bounded supplied evidence bundle with no browsing/tools in replay.
- Validate allowed evidence IDs and reject unsupported output.
- Cache by forecast/evidence/prompt/model version.
- Fall back to deterministic text.
- Run only through Dev 1's approved cost reservation/execution path.

Do not add breakout probabilities, graph models, or unrelated research until a
named experiment demonstrates value beyond the core system.

## 9. D2-07: Model CLI and prospective pipeline

Supply `cli/models.py` and reusable stages for:

- Feature/label building.
- Training and calibration.
- Experiment evaluation.
- Forecast artifact generation/publication requests.
- Outcome maturation and scoring.

Dev 1 registers the group and owns scheduling, environment configuration,
operational locks, and publication infrastructure.

A job after the decision cutoff cannot retroactively create a prospective
prediction. Preserve model/data/evidence hashes and first-recorded time.
Store later corrected outcomes as distinct vintages.

Do not start a second scheduler in your package or execute paid ingestion from
a training function.

## 10. Tests and acceptance

Required saved tests:

- Exact target/reference boundaries and fixed anchor.
- Future data cannot alter earlier features.
- Prospective vintage and collection-time restrictions.
- Missing source versus explicit zero.
- Required history and low-denominator eligibility.
- Immature labels never become negatives/zeros.
- Training/tuning/calibration/final-test isolation.
- Whole-origin splits and company-family grouping.
- Training-only preprocessing.
- Baseline formulas and tied rankings.
- Prediction inversion, quantile order, calibration pairing.
- Same candidate set for every comparison.
- Single representative per organization.
- No-positive and undersized-shortlist metric cases.
- Negative and inconclusive report states.
- Reproduction from manifests.
- Gemini invalid evidence/timeout fallback without network in unit tests.

Run:

```bash
make check test
uv run --frozen --no-sync pytest tests/unit/models
uv run --frozen --no-sync pytest -m integration tests/integration/models
```

Implement suites before treating these paths as runnable. Store full generated
outputs under ignored run directories. Share versioned report artifacts and
concise evaluation summaries; do not flood review context with dataframes.

Coordinate resource use with Dev 1. Do not run benchmarks in parallel.

## 11. Handoff and completion

Every result handoff includes:

- Code/experiment/configuration IDs.
- Dataset, mapping, source-policy, and schema versions.
- Feature, model, calibration, forecast, outcome, and report artifact hashes.
- Load/reproduce commands and artifact retrieval instructions.
- Actual evaluation periods and cohort/organization counts.
- Eligibility/exclusions and missing coverage.
- Baseline comparisons and evidence status.
- Serving decision and limitations.

Your workstream is complete when real baseline/learned experiments, immutable
forecast outputs, numerical policy helpers, evidence summaries, and honest
evaluation can be consumed by the other branches. A baseline winning is a
valid completed research result.

## 12. Copy-paste Codex starting prompt

```text
Implement the Dev 2 workstream in plans/DEV_2_MODELS_EVALUATION.md.
Read AGENTS.md, PLAN.md, and plans/README.md first. Work on
dev/models-evaluation from the committed shared scaffold.

Own features, models, evaluation, explanations, model contracts, and
cli/models.py only. Do not edit ingestion, database migrations, public API,
frontend, root dependencies/lockfiles, or PLAN.md.

Start with D2-01: publish lightweight forecast/evaluation contracts and saved
labelled fixtures. Consume Dev 1's merged data contracts. Then implement
temporal builders and baselines before learned models or optional sources.

Implement numerical rules once and expose lightweight pure helpers to the API.
Use synthetic fixtures for development only, and real versioned observations
for scientific evaluation. Preserve availability, label maturity, and separate
forecast/outcome artifacts. Do not fabricate success or shorten validation
while retaining stronger claims.

Request dependency/schema changes from their owner. Run required checks,
record reproducible artifact handoffs, and deliver small reviewed checkpoints.
Do not merge or publish without the developer's instruction. Continue
independent owned work when an external dependency is blocked.
```
