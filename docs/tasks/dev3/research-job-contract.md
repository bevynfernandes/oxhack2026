# Research-job/report contract for #46

Status: agreed by Ivan and Daniyal in #46; implemented by the additive backend.
This is additive; existing v1 assessment IDs, routes and saved links keep their
meaning. No model training or new target semantics are approved by this proposal.

## First runnable slice

Research a company already identified in an explicitly selected C1/C2 publication.
The user confirms its displayed name/domain before starting. The server verifies
that the submitted domain matches the saved company identity. Unmatched names or
domains return `identity_confirmation_required`; they do not inherit another
company's report. Arbitrary-domain entity resolution is a later bounded adapter,
not an inference from an HN keyword match.

Collect only bounded public-source evidence from fixed provider endpoints. First
collector: up to 100 HN stories linking the exact confirmed domain in a declared
30-day window. A multi-page result remains partial/unavailable rather than a
complete count. No arbitrary user URL fetch, hosted AI call or model fitting.
Existing published metrics are explicitly saved evidence, with original dates;
they are not presented as newly researched facts. Unavailable groups stay visible.

## Additive routes

| Method and route | Meaning |
| --- | --- |
| `POST /api/v1/research-jobs` | Validate confirmed identity and enqueue a bounded refresh; return 202 and actual job state |
| `GET /api/v1/research-jobs/{job_id}` | Poll durable state and per-source results; never trigger work |
| `GET /api/v1/research-reports/{report_id}` | Read exact immutable report bytes; no vendor or inference calls |

Request fields: `assessment_publication_id`, `company_id`, `domain`,
`identity_confirmed: true`. The first slice uses the existing company selection
to remove ambiguity; the UI may accept name/domain to find that saved identity.
Only a worker performs collection. Missing worker/storage configuration returns
503 instead of an artificial queued state. An operator controls bounded worker
concurrency. Jobs survive restart; interrupted running jobs are explicitly
recoverable/failed, never silently marked completed. Refresh creates a new ID.

Job fields: `schema_version`, `job_id`, `state`, confirmed identity,
`requested_at`, `started_at`, `finished_at`, `sources`, `report_id`, `reason_codes`.
States: `queued`, `running`, `partial`, `completed`, `failed`.
Per-source states: `pending`, `running`, `succeeded`, `partial`, `failed`.
No guessed percent-complete or fabricated duration. A partial job has at least
one useful traceable result and reports exactly what failed or was truncated.
No source result means failed; successful saved-report lookup alone is not fresh
research. Invalid identity is 409; unknown IDs 404; invalid inputs 422.

## Immutable report

Fields: `schema_version`, `report_id`, `job_id`, `researched_at`,
`source_publication_id`, `assessment_publication_id`, `inventory`, `outlook`
(the unchanged shared `StartupOutlook`), `data_version`, `model_version`,
`limitations`.

The source publication references exact saved C1 facts and raw capture hashes.
Fresh attention has a separately versioned research inventory and never enters a
v1 C1 metric family or the old saved publication. All fresh observation/evidence
IDs resolve within that immutable inventory. The old assessment publication is
labelled saved context, not recomputed after refresh.
Report/public projections withhold raw object locations, restricted contents and
private derived facts. Public evidence references retain actual availability and
collection time; retrospective collection does not become historical knowledge.

Exactly five specialist IDs, in display order:

1. `adoption_retention`
2. `attention_sentiment`
3. `financial_health`
4. `industry_competition`
5. `team_execution`

Dev 2 owns `oxhack2026.models.startup_outlook`; the backend imports that shared
payload rather than introducing a competing model policy. The field names below
match the merged #49 model payload.

Embed `StartupOutlook` unchanged: section fields are `group_id`, `data_status`,
`metric_observation_ids`, `usable_metric_observation_ids`, `evidence_ids`,
`model_status`, `prediction` and `reason_codes`. `data_status` is `available`,
`insufficient_data` or `not_applicable`; model status is only `model_not_trained`.
Provider truncation/partial collection belongs in job/source state, not a new
model state. Available observations do not imply training readiness.

Until Daniyal freezes feasible target/model contracts, `prediction` is null with
`model_not_trained`. A later non-null prediction must name the target version,
endpoint/horizon, fitted artifact, feature schema, training snapshot, split and
validation versions. No placeholder number or compatibility alias for v1 targets.

Use the shared null `overall_outlook` and `overall_reason_codes:
[model_not_trained]`; do not introduce a competing `overall.value` wrapper.
Missing components are not zero and are not reweighted. No bubble score or
success badge. Model/data versions remain independently nullable with reasons.
Backtesting is unavailable until reproducible evaluation artifacts exist.

## Acceptance for this slice

- One real confirmed company is researched through the API and UI.
- Job state comes from actual durable transitions, including partial/provider
  failure and restart behavior; GET requests never run the collector.
- Raw successful source bytes are retained in existing artifact storage, with
  actual timestamps; source/report versions are immutable.
- All five groups and independent data/model status render with null numerical
  predictions/outlook. Existing v1 saved links still load the exact old bytes.
- Mocked provider units cover identity mismatch, truncated results, exact domain
  matching, source errors, recovery and privacy. Opt-in real API/browser checks
  cover source inspection, mobile and keyboard behavior.

Known-company identity and shared mixed-vintage lineage were confirmed in #46.
Arbitrary unknown-company resolution remains outside this first slice.


## Run the local research worker

- Configure `SIGNALSHIFT_COMPANY_ROOT` and `SIGNALSHIFT_COMPANY_PUBLICATIONS` as
  for the existing company API, then set `SIGNALSHIFT_RESEARCH_ENABLED=1`.
- Start `uvicorn oxhack2026.api.company_runtime:create_company_app --factory`
  with **one ASGI process**. Two local threads bound concurrent research.
  An exclusive POSIX lease rejects a second enabled process on the same root.
- The configured root must be writable. Jobs live under `research-jobs`, report
  publications in `research-reports.json`, and immutable report/raw bytes use the
  existing content-addressed `objects` store. Do not edit these files manually.
- Startup resumes queued jobs. An interrupted running job becomes failed with
  `worker_interrupted`; explicitly start another refresh to collect new evidence.
  Graceful shutdown waits for active workers. GET routes never start collection.
- One refresh queries at most 100 HN stories on one page, up to three transport/
  transient retries, 25 seconds per HTTP operation and 4 MiB per response. Access
  denial/rate limits fail without bypass; extra pages produce partial state and
  a missing count. The API does not claim that query results exhaust all HN links.
- Use this local opt-in worker on a trusted development instance. It has no
  authentication, admission quota or public deployment scheduler; do not expose
  writable routes publicly as an unbounded shared service.
- All timestamps come from actual request/worker/capture events. HN windows are
  start-inclusive/end-exclusive. The response exposes capture SHA-256/size, never
  local object paths. Report reads verify report and fresh raw hashes plus saved
  source integrity; corrupt data returns the safe 503 envelope.
- The embedded saved context retains its original coverage cutoff. The outlook
  re-evaluates metric freshness at the new report cutoff; it does not rewrite
  measurement/publication times or refresh old customer/financial facts.
- Fresh source links point to the fixed public API endpoint. Exact query parameters
  are persisted separately in the raw capture checkpoint; the measurement window,
  confirmed identity and metric definition are exposed in the report inventory.
