# Prediction workspace: agreed UI and backend boundary

Decision: 2026-10-24, after comparing both supplied Stitch HTML exports,
screenshots and DESIGN.md with the merged backend. The user approved the
structure and horizons below. The user subsequently requested a direct UI rebuild
from the original Stitch export, with no overview scrolling.
Training remains on hold; no validated numerical prediction is available.

## Page hierarchy

1. **Startup Outlook**: company identity, report cutoff, overall outlook and
   concise supported drivers/risks. Null outlook is visibly unavailable.
2. **Three future outcomes**: Growth, 24 calendar months; Survival, 24 calendar
   months; Financial Health, 12 calendar months. These explain what the product
   aims to predict. Missing predictions are not zero or an implied bad outlook.
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

New `build_untrained_outlook` results include `outlook.forecasts` in this order:

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

## Current frontend implementation

`frontend/src/pages/research/CompanyDossier.tsx` and `frontend/src/workspace.css`
implement the original Stitch dossier: compact header, company identity, four
summary tiles, five parallel pillars and a bottom evidence ledger. The overview
fits the viewport; source details scroll inside a right-hand drawer. Phones switch
between pillars in place. Local fonts avoid third-party browser requests.

Saved profiles and fresh reports share this component. The API now projects the
same explicit metric grouping into saved company details (`company-metric-groups-v2`).
Unknown metrics remain unassigned. Old embedded profiles omit the optional
projection when serialized, preserving immutable report bytes.

The earlier `design/prediction-workspace/index.html` is archived and superseded
for visual implementation. Keep the supplied Stitch layout and the approved
prediction semantics; no investment grades or fabricated scores.

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
