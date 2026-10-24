# SignalShift: startup outlook

Latest direction: [startup prediction plan #46](https://github.com/bevynfernandes/oxhack2026/issues/46)
and its [data-readiness and delivery plan](docs/tasks/dev2/startup-prediction-reset.md)
update the scope below to Software/SaaS, single-company research and local backend
models. Training waits for verified historical inputs and labels. Ivan retains
the UI assignment; Bevyn owns the delegated data/backend audit.

## 1. Product decision

Assess a startup's prospects using dated evidence about traction, commercial
health, execution, and financing. The researcher searches companies, opens a
profile explaining its outlook and critical unknowns, and compares up to three
relevant peers. The destination is separately validated outcome predictions;
the first usable checkpoint is a clearly labelled evidence assessment.

This replaces the download-only objective following the user's direction on
2026-10-24 and [team agreement in #19](https://github.com/bevynfernandes/oxhack2026/issues/19).
Dev 1 owns this shared specification; Dev 2 owns precise outcome/model rules;
Dev 3 owns the application/design. Ownership in [plans/README.md](plans/README.md)
continues to apply. Do not create three independent scoring implementations.

Downloads are one product-adoption signal for applicable developer tools. They
are not customers, revenue, company growth or a company-success label. Start
with the verified AI developer-tool segment; extend to other segments only with
appropriate metrics, identities and peer definitions.

## 2. Three separate outcomes

These IDs and horizons are proposed by Dev 2 in
[PR #22](https://github.com/bevynfernandes/oxhack2026/pull/22).
Label definitions must be reviewed and versioned before experiments are frozen.

| Outcome ID | Horizon | Observable question | Required distinction |
| --- | --- | --- | --- |
| `operating_growth_24m_v1` | 24 calendar months | Is the company operating at the endpoint, with growth in the cohort's predeclared comparable revenue or active-paying-customer measure? | Shutdown and continued operation without growth have different reasons |
| `commercial_viability_12m_v1` | 12 calendar months | Is it operating with nonnegative operating cash flow over the ending twelve months? | Name this target **cash-flow self-sufficiency** in the UI; negative cash flow does not itself mean business failure |
| `financing_or_acquisition_24m_v1` | 24 calendar months | Did qualifying primary financing or a change-of-control acquisition complete within the horizon? | Financing, acquisition announcement, completed acquisition and distressed exit remain distinct facts |

The cash-flow definition is a measurable proposal, narrower than the everyday
meaning of viability. Preserve that qualification until the label-policy review
resolves it. Revenue/runway estimates must not substitute for actual operating
cash flow. Predeclare the growth measure and matching windows per cohort; never
choose the measure after observing which grew.

Dev 2 label states: `observed`, `immature`, `unobserved`, `conflicting`. Only
mature, sufficiently observed, unambiguous labels enter initial binary evaluation.
Missing financial data, a dead website, silence about funding, or disappearance
from a directory never automatically means failure. A company shutdown requires
verified company-level evidence; product retirement alone is insufficient.

Use calendar-month horizons and UTC cutoffs, not the download subsystem's weekly
origins. Separate event occurrence, publication, collection, assessment and
label-evaluation dates. Future labels live outside assessment/features payloads.

## 3. What the user sees

1. **Companies:** search and segment/stage/coverage filters over a compact table.
   Rows show company context, supported outlook, strongest supported signal,
   principal risk or evidence gap, coverage and update date. Default to name or
   recency until a model-owned ordering is justified.
2. **Company profile:** identity and assessment date, three outcome rows, concise
   evidence and risks, metric tables, dated event timeline and source links.
   Definitions and technical provenance expand on demand.
3. **Compare:** at most three companies using the same metric definitions and
   outcome horizons. Show different stages, business models, dates and missing
   data explicitly. No invented composite winner.

Assessment statuses are `evidence_only`, `validated_probability`, `unavailable`.
An evidence-only explanation describes facts and gaps; it must not assert an
unvalidated likelihood. Show an outcome probability only when the published
Dev 2 evaluation gate permits it. There is no arbitrary overall 0-100 score.

Visual direction: neutral surfaces, readable system typography, one restrained
accent, compact navigation, tables and divided rows. Reduce oversized headlines,
repeated metric cards, excessive badges and decorative charts. Preserve keyboard
focus, contrast, mobile access and reduced motion. Dev 3's concrete design and
acceptance are tracked in [PR #21](https://github.com/bevynfernandes/oxhack2026/pull/21).

## 4. Data and contract checkpoint

The proposed C1 fields, initial metric set, source access and historical cohort
procedure are in [Dev 1's source contract](docs/workstreams/dev1/STARTUP_OUTLOOK.md).
Agree those names with Dev 2/3 before exporting public schemas. Add company
contracts alongside existing download contracts; do not reinterpret old artifacts.

| Owner | Produces | Consumed by |
| --- | --- | --- |
| Dev 1 | Company/context identities, effective mappings, metric definitions, observations, evidence, events, immutable source snapshots and typed reads | Dev 2 and Dev 3 |
| Dev 2 | Outcome definitions, labels/censoring, evidence assessments, features/models, evaluation and probability gate | Dev 1 storage and Dev 3 API |
| Dev 3 | Snapshot-scoped company list/profile API, generated client types, comparison and evidence presentation | User interface |

Start with existing npm observations, public GitHub release evidence, and reviewed
primary company announcements. Registry records are conditional on a verified
legal-entity match and access. Revenue, customer retention, burn, runway and
concentration remain explicitly unknown unless adequate evidence is supplied.

Every observation carries a definition/unit/window, applicability, missingness,
source and actual collection time. Evidence quality describes the source's
verification, not the probability the company succeeds. Source completeness is
separate from transport success. Keep raw responses and hashes; never splice
package migrations or backdate current company ownership.

## 5. Historical validity and prediction gate

The ten current tools are a present-day demonstration cohort, not a survival
training set. Freeze historical inclusion rules and dated discovery evidence
before examining outcomes. Retain companies that later failed or became inactive.
Do not combine a handpicked list of famous failures with today's winners and
claim representative calibration.

Historical financial endpoints need matching pre-outcome measurements and mature
follow-up. Public financing announcements usually establish positive events;
absence does not establish a verified negative. Publish coverage and censoring
counts before deciding whether a binary model is feasible.

Dev 2 owns chronological splits, label-availability purging, organization-family
separation, baselines, calibration and final holdout discipline. Evaluate each
outcome separately against training-only prevalence and a simple classifier.
Report calibration, Brier/log loss, discrimination, follow-up, class balance and
supported peer groups. Freeze the numerical probability release criteria before
holdout inspection. Passing contract tests is not evidence of predictive skill.

## 6. Implementation checkpoints

| Checkpoint | Deliverable | Completion evidence |
| --- | --- | --- |
| O1: shared definitions | Reviewed C1 source fields, C2 label/assessment rules and C3 projection | Consumer reviews; saved valid/invalid fixtures |
| O2: real company evidence | Immutable multi-family source bundle, explicit gaps, typed reader and checksummed transfer | Another developer loads real bytes and verifies sources/dates |
| O3: usable assessment product | Company list/profile/compare with all three outcome sections | Real API/browser flow; unknown/stale/conflict states; accessible mobile/keyboard behavior |
| O4: outcome research | Historically justified cohort and mature labels; separate models/evaluation | Reproducible chronological results and reviewed release gate; probabilities remain absent if it fails |
| O5: operated service | Scheduled bounded refresh, publication/rollback, deployment | Real restore and operational checks; verified credits before paid resources |

Dev 1 immediate order: finish #17 attribution fix; publish additive source
contracts; produce the real multi-family company snapshot and reader; integrate
Dev 2 assessments with Dev 3. Dev 2 proceeds with label/calendar invariants and
evidence assessment policies while historical labels are assembled. Dev 3 can
ship the visual foundation, then the company workflow against agreed contracts.

Further download-only catalogue expansion is held. Reuse completed download
extractors, immutable artifact storage, temporal boundaries and tests where they
fit. Do not claim previous completion percentages apply to this revised product.

## 7. Engineering and operational constraints

Keep the existing Polars/Pydantic/orjson stack, lightweight contracts, generated
API types, reviewed branches, small PRs and ownership boundaries. All persisted
objects are immutable/versioned with provenance; publication is atomic and
readers request exact versions. Unit tests mock vendors; service tests are opt-in.
Run Ruff, mypy and relevant tests before publishing implementation changes.

API requests read published artifacts: no vendor collection, training or paid
explanation calls in a request. Production never substitutes synthetic fixtures.
Keep secrets in environment configuration and out of artifacts/logs. Use only
existing verified credits/free quotas; installations and work remain local where
possible. Tiger/Vultr integration is conditional on access and cost controls,
not a reason to add unrelated product features.

No new offline export/demo implementation is assigned in this revision; Dev 3
has recorded its user's exclusion of that work. Local development and replayable
immutable research artifacts remain supported. Optional explanations cannot
invent numbers or replace source-backed assessment logic.

The [archived download plan](plans/archive/DOWNLOAD_FORECAST_PLAN.md) preserves
existing download-specific algorithms and implementation rationale. It is not
the current product specification. Its package targets, rankings, five-company
shortlist, success exclusions and completion gates do not override this plan.
