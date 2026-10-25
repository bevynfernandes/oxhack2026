# Prediction workspace: agreed UI and backend boundary

Updated integration decision: 2026-10-25, following
[Dev 2's clarification on #79](https://github.com/bevynfernandes/oxhack2026/pull/79#issuecomment-6391306205).
The summary now uses Growth, Survival and Overall; Financial Health remains in
the five drivers. This supersedes the duplicate Financial Health summary from
the 2026-10-24 Stitch alignment. Draft #79 carries the presentation/default
implementation; this document records the agreed integration target.
No validated startup growth/survival prediction or complete business score is
established by the separate public-issuer research experiments.

## Page hierarchy

1. **Startup Outlook**: company identity, report cutoff, overall outlook and
   concise supported drivers/risks. Null outlook is visibly unavailable.
2. **Summary cards**: Growth, 24 calendar months; Survival, 24 calendar months;
   Overall outlook. Overall is a separate combined view, without an invented
   horizon or success-probability interpretation. It requires all five dimension
   scores and a reviewed aggregation/release policy. Missing predictions are not
   zero or an implied bad outlook.
3. **Five fundamental drivers**, in shared backend order:
   Adoption & Retention, Attention & Sentiment, Financial Health,
   Industry & Competition, Team & Execution. These organize evidence and future
   specialist analyses; they are not five independent definitions of success.
4. **Sources and limitations**: dated evidence, provider completeness, gaps and
   model/data versions. Real backtesting/uncertainty appears after validation.

The approved periods do not freeze growth thresholds, financial-resilience rules,
stage treatment, labels or overall combination weights. Those remain subject to
[the data/target gate](startup-target-readiness.md). Do not relabel the existing
v1 cash-flow or financing/acquisition outcomes as financial health or survival.

## Additive backend contract

The existing `build_untrained_outlook` API includes `outlook.forecasts` in this
order. The revised summary presentation does not remove, rename or reinterpret
these fields or their saved values:

| outcome_id | horizon_months | definition_status | model_status | prediction |
| --- | --- | --- | --- | --- |
| growth | 24 | pending_label_policy | model_not_trained | null |
| survival | 24 | pending_label_policy | model_not_trained | null |
| financial_health | 12 | pending_label_policy | model_not_trained | null |

Each has `reason_codes: [target_definition_pending, model_not_trained]`. These
product outcome IDs are separate from old training-target IDs. Schema validation
rejects incorrect horizons, incomplete/repeated/reordered lanes, numeric outputs,
confidence claims and unapproved model/label status.

The five `outlook.specialists`, independent data/model states, null
`overall_outlook`, source references and saved assessment definitions are retained.
Research routes are unchanged: POST `/api/v1/research-jobs`, GET job, GET immutable
report. The report cutoff anchors the horizons; this does not execute inference.

Older immutable reports omit `forecasts`. Reading/serializing them must not add
the field or rewrite their bytes. UI shows a legacy-report notice and preserves
the original saved analysis; do not derive new lanes from the old outcomes.
Starting fresh research remains an explicit confirmed action. The generated
OpenAPI/TypeScript field is optional for this compatibility boundary.

## Mapping default and experimental components

- The integration default is `SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules`.
  `rules_gemini` explicitly enables optional Gemini interpretation. The Live
  timeout/attribution fixes in #81 remain applicable to that opt-in mode.
- An experimental annual cash-flow estimate belongs within the Financial Health
  dimension, with its fiscal-year target, observed-follow-up condition, retained
  filing evidence, model identity and population/validation limitations visible.
- Such a component is not the pending 12-calendar-month financial-health
  forecast, operating survival, unrestricted runway or a complete Overall score.
- Experimental model execution and software tests do not approve calibrated
  startup-outcome serving. Existing immutable reports retain their original
  outcome meanings and serialized fields.

## Frontend structure

`frontend/src/pages/research/CompanyDossier.tsx` and `frontend/src/workspace.css`
implement the shared dossier structure: compact header, company identity, four
summary tiles, five parallel pillars and a bottom evidence ledger. The overview
fits the viewport; source details scroll inside a right-hand drawer. Phones switch
between pillars in place. Local fonts avoid third-party browser requests.

Saved profiles and fresh reports share this component. The API now projects the
same explicit metric grouping into saved company details (`company-metric-groups-v2`).
Unknown metrics remain unassigned. Old embedded profiles omit the optional
projection when serialized, preserving immutable report bytes.

The earlier `design/prediction-workspace/index.html` is archived and superseded
for visual implementation. Preserve the shared dossier interactions and the
versioned API semantics while following the updated summary hierarchy above;
no investment grades or fabricated scores.

## Implementation acceptance

- Preserve name/domain search and exact identity confirmation. Current research
  supports known saved companies only; unknown companies remain an explicit gap.
- Separate saved analysis from new research. Show actual queued/running/partial/
  completed/failed and actionable 503/409/error states; no guessed percentages.
- Render backend forecast order/horizons and five specialist groups, with null
  predictions readable and target/model readiness explicit. No browser scoring.
- Resolve metric/evidence references from the report inventory. Retain values,
  units, windows, stale/missing/restricted states and original measurement dates.
  Funding is not cash/runway; downloads are not customers/retention; exact-domain
  HN links are not broad sentiment. An available metric is not model confidence.
- Show actual supported signals/risks when supplied; otherwise explain the gap.
  No invented narrative, inferred ARR, verified badges or bubble/success labels.
- Keep saved v1 URLs, exact old outcome names and legacy research reports usable.
- Verify a real partial report, five groups, all three null forecast lanes, mobile
  layout/zoom, dialog keyboard focus/Escape/tabs, reduced motion and source links.
  Test the normal empty/error paths and verify generated types/build/format.

The existing private Qdrant replay shared in #46 predates forecast metadata; use
it for legacy compatibility. New report tests exercise the approved three lanes.
Any new live run must retain its actual capture and cannot rewrite that replay.

## Verification

Full Python checks, Ruff, mypy, strict docs, generated types, frontend build,
formatting and 23 frontend unit tests pass. Browser acceptance: 21 fixture tests
and two real-publication/replay tests. Overview bounds and nonoverlapping metrics
are checked at 1440×900, 1366×768, 1280×720, 390×844 and 375×667. Drawer focus,
Escape, keyboard tabs, source links, exact JSON export and directory pagination
are covered. Automated accessibility checks pass.

The retained Qdrant report still serializes byte-identically without adding
forecasts. Screenshots/results remain under ignored `tests/outputs/dossier-*`.
These checks establish UI/contract behavior, not predictive performance.
