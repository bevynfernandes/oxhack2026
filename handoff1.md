# SignalShift — Engineering Handoff

**Project:** Early adoption intelligence for open-source AI developer tools

**Context:** OxHack 2026 · Theme: Time · HRT: Best Use of Data for Predictions & Decision Making

**Status:** Implementation specification, **not** a claim that the dataset, trained model, or product is complete

**Primary objective:** Determine whether developer and discussion signals improve predictions of future software adoption beyond past download trends.

> **Single sentence:** At a historical point in time, use only previously available public evidence to forecast an AI tool's package-download activity 91 days later, explain the supporting observations, and test whether those forecasts lead to better research shortlists.

## 0. Non-negotiable scope and definitions

- **Unit being predicted:** an **open-source AI developer tool**, linked to a verified Python package and (where available) a verified GitHub repository. A tool is **not** necessarily a company or startup.
- **Main observed outcome:** future **PyPI distribution-file download requests**. This is an *adoption/activity proxy* — **not** unique users, paying customers, production installs, revenue, or company success.
- **Main forecast horizon:** **91 days / 13 weeks**. Weekly historical cutoffs are always Monday 00:00 UTC. UI can say “~90 days”.
- **Target at cutoff `t`:** `D28(t + 91 days)`, the sum of consistently filtered daily downloads in the **half-open interval** `[t + 63 days, t + 91 days)`.
- **Reference at cutoff `t`:** `D28(t)`, downloads in `[t - 28 days, t)`. All windows exclude the cutoff instant; this makes boundaries unambiguous.
- **Secondary target:** `breakout_91d = 1` if `D28(t+91) >= 1.5 * D28(t)`, provided the tool has enough history, `D28(t) >= 100`, and future labels are fully observed. These thresholds are **initial experimental choices**; record them in model metadata and test sensitivity.
- **What “sustained adoption” means here:** future 28-day download activity, **not** retention, engagement or long-term customer adoption. Do not use the stronger phrase unless independently validated.
- **Input features at `t` MUST have source availability timestamps <= `t`.** Event timestamp alone does not prove information was already published/available.
- **Decision use case:** help analysts *prioritise which tools to investigate*, not provide investment recommendations or assert startups will succeed.
- **Predictions and confidence ranges must be computed**; no invented values. No LLM-generated numeric forecasts.

### Out of scope for the core model

Predicting revenue, funding rounds, customer growth, business success, market saturation or causally measuring how marketing/hiring changes adoption. Those require separate ground-truth data and models. They can be future modules, but must **not** appear as validated core outputs.

---

## 1. Input space — exactly what goes into the system

There are **three distinct input interfaces**: (A) user interaction, (B) source data, and (C) model features.

### A. User-facing input interface

| Control | Type | Default | Validation / effect |
|---|---|---|---|
| Select tools | Searchable multi-select from curated catalogue | One tool | 1–5 IDs; no arbitrary unverified repo/package mapping |
| As-of date | Historical week selector / date picker | Most recent **eligible** cutoff | Snap to Monday 00:00 UTC; restrict to dates with enough history; hide Reveal before request |
| Forecast horizon | Fixed `91` days in v1 | 91 | Keep one trained horizon; do not silently interpolate to others |
| Compare against | Toggle: naive baseline / model | Both | Show both and their evaluation statistics |
| Reveal future | Button in historical replay | Off | Only enabled when complete future target data exists |
| Rank tools | Sort/filter on growth probability, predicted growth, minimum coverage | Breakout probability | State whether ranking is model-based or baseline |
| Evidence | Expandable per-source details | Collapsed | Display dated events/aggregates and missing-source warnings |
| Research budget (optional) | Integer top-K | 5 | Select K tools and score their observed 91-day breakout rate in historical replay |

**Do not offer “hire more developers” or “change prices” controls as if the model can estimate causal outcomes.** A separate what-if *sensitivity* view may change assumed feature values, but label it as hypothetical/model sensitivity, not an observed alternate history.

### B. Data-source input space

| Source | Access | Data we actually use | Historical caveat | Phase |
|---|---|---|---|---|
| **PyPI BigQuery** | `bigquery-public-data.pypi.file_downloads`; BigQuery project/auth/billing quota needed | Daily distribution download requests by canonical package | Aug 24, 2026 logging-definition change; filter distribution extensions consistently across all dates | **Required** |
| Curated catalogue | Checked-in CSV/YAML | `tool_id`, display name, PyPI project, GitHub repo, aliases, category, mapping evidence | Incorrect mapping ruins all results; manually review | **Required** |
| **GH Archive** | Public hourly JSON / BigQuery | Dated public Push, Issue, PR, Release, Fork event counts and unique actors per repo | Missing events/coverage gaps; star-event coverage may be unreliable; don't backfill GitHub's *current* stars as historical counts | Second |
| **Hacker News Algolia** | Public historical search endpoint | Dated matching stories/comments, original IDs/URLs | Terms are ambiguous, result coverage varies; current points/comment totals are *not* historic snapshots | Second |
| **deps.dev** | Public API/BigQuery where available | Verified ecosystem dependency relations and project-package mapping | Not automatically a historical time series; don't use today's dependency graph for past forecasts | Research extension |
| **npm downloads** | Public daily/range download API | Separate JavaScript-ecosystem modelling target | Do not mix absolute npm and PyPI counts into one target | Research extension |
| **Google Trends** | API is limited-access alpha | Search-interest feature **if access is approved** | Do not block implementation on the alpha; manually supplied time series must document dates/scaling | Optional |
| Founder/developer field research | Explicit opt-in interviews or aggregated usage exports | Qualitative research, optional measured activation/retention labels | Consent, privacy, selection bias; small samples cannot train a general customer-growth model | Research extension |

**Important PyPI correction:** On 2026-08-24 PyPI stopped counting metadata-file requests as downloads. Queries spanning this date must consistently select actual distribution filenames (`.whl`, `.tar.gz`, `.zip`) across **both** sides of the change, or the model can learn a fictitious decline. PyPI also warns that even corrected downloads are not reliable counts of people using a package.

**Important Github caveat:** The GitHub REST Events API only contains up to 30 days of events, so it is **not** a historical feature store. Use GH Archive, dated releases, or other reproducible historical sources; audit coverage by event type and month. If GH Archive's WatchEvent/star coverage drops, flag the series as missing rather than inferring falling interest.

**No source should be silently treated as zero if it was unavailable.** Store missingness and coverage fields.

### C. Model feature space — one observation per `(tool_id, as_of_week)`

Keep a feature dictionary with `name`, type, unit, window, extraction version, source, and availability rule. Suggested first pass:

| Feature | Type / unit | Definition at cutoff `t` | Availability |
|---|---|---|---|
| `downloads_7d` | int, requests | Sum PyPI filtered downloads for last 7 complete UTC days | Core |
| `downloads_28d` | int, requests | Last 28 complete UTC days | Core |
| `downloads_prev_28d` | int, requests | Previous nonoverlapping 28-day window | Core |
| `downloads_84d` | int, requests | Last 84 complete UTC days | Core |
| `log_downloads_28d` | float | `log1p(downloads_28d)` | Core |
| `growth_28d` | float | `log1p(D28(t)) - log1p(D28(t-28d))` | Core |
| `volatility_12w` | float | Std dev of weekly log-download deltas | Core |
| `tool_age_days` | int | Days since first verified release **known by t** | Core |
| `calendar_week_sin/cos` | float | Annual seasonality | Core |
| `repo_push_events_28d` | int/nullable | GH Archive PushEvent count in prior 28 days | Later |
| `repo_unique_actors_28d` | int/nullable | Distinct actors in dated GitHub events | Later |
| `repo_pr_opened_28d` | int/nullable | PR opened events; avoid counting unrelated edits twice | Later |
| `repo_issue_events_28d` | int/nullable | Issue activity | Later |
| `repo_release_events_90d` | int/nullable | Dated release events | Later |
| `hn_mentions_28d` | int/nullable | Dated matched stories/comments after ambiguity filtering | Later |
| `hn_mentions_delta` | float/nullable | Change vs preceding 28-day period | Later |
| `has_github_coverage` | bool | Whether GitHub historical extract covers this tool/week | Later |
| `has_hn_coverage` | bool | Whether HN historical extraction succeeded | Later |
| `data_freshness_days` | number | Age of latest relevant observation as of cutoff | Core |

Store tool category, package ecosystem and mapping metadata separately. **Do not use current company funding, current stars, current employees, latest company descriptions or other future snapshots as past features.** Do not join on globally revised labels without snapshot dates.

Feature values may be null if genuinely missing. Use an explicit availability mask so models can distinguish missing observation from zero activity.

---

## 2. Output space — precise prediction contract

### A. Core numerical outputs (per tool and cutoff)

| Field | Type | Meaning |
|---|---|---|
| `forecast_target` | enum/string | Always `pypi_distribution_downloads_trailing_28d` in v1 |
| `as_of_week` | ISO UTC date/time | Last permitted information cutoff |
| `target_date` | ISO UTC date/time | Exactly 91 days later |
| `observed_d28` | int | Trailing 28-day download count at `t` |
| `predicted_d28_p50` | nonnegative float | Median forecast of trailing 28-day activity at `t+91` |
| `predicted_d28_p10` / `p90` | nonnegative floats | 80% forecast interval, **only if supported by calibration** |
| `predicted_growth_pct` | float | `100*(predicted_d28_p50 / max(observed_d28, 1) - 1)`; null when baseline too small |
| `prob_breakout` | nullable float in [0,1] | Calibrated probability of the defined 50% growth event; null if not eligible |
| `baseline_predicted_d28` | nonnegative float | Naive persistence comparison (current D28) |
| `data_quality` | object | Source coverage, completeness and warnings |
| `evidence` | array | Dated measurable features and source links, not invented narratives |
| `model_version` / `data_version` | string | Reproducibility identifiers |
| `status` | enum | `ready`, `insufficient_history`, `low_coverage`, `unavailable`, `unvalidated` |

**Do not return an arbitrary “confidence: 93%” score.** A calibrated prediction interval and a measured probability of a specifically defined event are different and should be labelled as such.

**Illustrative response only; numbers are fake:**

```json
{
  "tool_id": "example-ai-sdk",
  "as_of_week": "2025-01-06T00:00:00Z",
  "horizon_days": 91,
  "target_date": "2025-04-07T00:00:00Z",
  "forecast_target": "pypi_distribution_downloads_trailing_28d",
  "status": "ready",
  "observed_d28": 12000,
  "predicted_d28_p10": 13200,
  "predicted_d28_p50": 17800,
  "predicted_d28_p90": 25100,
  "predicted_growth_pct": 48.3,
  "prob_breakout": 0.46,
  "baseline_predicted_d28": 12000,
  "data_quality": {
    "package_mapping_verified": true,
    "pypi_days_present_84d": 84,
    "github_coverage": "partial",
    "hn_coverage": "not_loaded",
    "warnings": ["Discussion features not available at this cutoff"]
  },
  "evidence": [
    {"feature": "growth_28d", "value": 0.22, "unit": "log-ratio", "source": "pypi", "observed_through": "2025-01-06T00:00:00Z"}
  ],
  "model_version": "pypi-catboost-v1",
  "data_version": "extract-2026-10-24"
}
```

### B. User-visible outputs

1. **Forecast chart:** past observed activity, future median, p10–p90 band and naive baseline, with the historical cutoff clearly marked.
2. **Breakout probability:** with a tooltip stating precisely what “breakout” means and when it is unavailable.
3. **Signal evidence:** current/download growth, developer activity, public discussion changes, missingness and original source links. Model contributions, if shown, are **predictive explanations**, not causal claims.
4. **Historical time machine:** rewind to `t`, make a shortlist, forecast using only knowable data; click **Reveal Reality** to plot actual downloads through `t+91` and score forecast error.
5. **Decision panel:** top-K tool investigation shortlist under a hypothetical research budget; report `Precision@K` against realised historical breakouts, with simple-popularity and random/rank-baseline comparisons.
6. **Reliability panel:** holdout metrics, sample count, interval coverage, data period, missing-source warnings, model version.

### C. “Future changes” scenario outputs (optional; clearly separated)

Users may perturb a **hypothetical input** (“What if public discussions doubled?”) and inspect how the trained model's prediction changes. Return `scenario_type: "predictive_sensitivity_not_causal"`, modified inputs and alternative model outputs. **Never claim that causing more discussions would cause more adoption.** Genuine causal intervention simulation requires separately identified causal mechanisms and validation.

---

## 3. Data contracts, validation and storage

### Canonical catalogue: `data/catalog/tools.csv`

```csv
tool_id,display_name,ecosystem,package_name,github_repo,category,mapping_verified,mapping_evidence_url
example-ai-sdk,Example SDK,pypi,example-ai-sdk,example-org/example-repo,ai-sdk,true,https://example.org/docs
```

`example-ai-sdk` is **placeholder data**. Replace with 30–80 **manually verified** tools. Map product/company identity to one or more packages carefully; v1 uses **exactly one primary package per tool** to avoid double counting. Reject duplicates and ambiguous aliases.

### Canonical daily metric: `daily_metrics.parquet`

```text
tool_id: string
source: string                  # pypi | github | hn
metric: string                  # distribution_downloads | push_events | hn_mentions | ...
date_utc: date
value: float                    # nonnegative for count metrics
observed_at_utc: timestamp     # time event occurred
available_at_utc: timestamp    # earliest credible availability time / ingest bound
collected_at_utc: timestamp    # when extraction ran
completeness: string           # complete | partial | missing
source_version: string
extraction_id: string
```

For daily aggregate metrics, `observed_at_utc` is the day-end timestamp; `available_at_utc` is no earlier than the day becoming publishable. **Do not use this event-time shortcut if the vendor publishes later**; choose a conservative documented lag. Enforce unique `(tool_id, source, metric, date_utc, extraction_id)` and create a canonical latest-validated view.

### Prediction data: `feature_rows.parquet` / `label_rows.parquet`

```text
feature_rows: tool_id, as_of_week, ...typed features..., coverage_mask, feature_schema_version
label_rows: tool_id, as_of_week, future_target_d28, breakout_91d, label_available_at, label_eligible
```

**Validation rules:**

- UTC everywhere; dates of week cutoffs are Monday at 00:00 UTC.
- Exactly one primary package per tool; no conflicting mapping.
- Deduplicate event IDs before aggregation where possible.
- Disallow negative counts; flag unexplained gaps or implausible jumps.
- Do not impute missing event days as zero without independently confirming coverage.
- Each feature's `available_at_utc <= as_of_week`; each training label's availability must predate the model's training cutoff.
- Package-release date must precede cutoff; avoid `D28=0` breakout classifications for not-yet-released projects.
- Store extract manifests (date, query, filter version, row count, source, hashes) and model artefacts.
- Quantify group coverage by tool/week/source; apply minimum history (e.g. 84 complete days) and an eligibility mask.

### PyPI extraction SQL (initial example; verify schema/permissions in your environment)

```sql
-- BigQuery Standard SQL; parameterize @start_ts, @end_ts and @packages.
SELECT
  LOWER(file.project) AS package_name,
  DATE(timestamp, 'UTC') AS day_utc,
  COUNT(*) AS distribution_downloads
FROM `bigquery-public-data.pypi.file_downloads`
WHERE timestamp >= @start_ts
  AND timestamp < @end_ts
  AND LOWER(file.project) IN UNNEST(@packages)
  AND REGEXP_CONTAINS(LOWER(file.filename), r'\.(whl|tar\.gz|zip)$')
  AND (details.installer.name IS NULL
       OR LOWER(details.installer.name) NOT IN ('bandersnatch'))
GROUP BY 1, 2
ORDER BY 1, 2;
```

Always filter on the partitioned timestamp, run a BigQuery **dry run** to estimate bytes/cost, and sanity-check download discontinuities around 2026-08-24. If filtering creates a pre/post discontinuity, document and address it rather than fitting the model blindly. Avoid claiming all bot activity was excluded.

---

## 4. ML architecture — build one strong model, not ten weak ones

### Baselines (must implement)

1. **Persistence:** `D28(t+91) = D28(t)`.
2. **Damped recent trend:** extrapolate recent log-download slope with explicit clipping/damping to avoid explosive predictions.
3. **Regularised linear model:** Ridge/ElasticNet on log-transformed target, for an interpretable learned benchmark.

### Main quantitative models

- **Forecast regressor:** CatBoostRegressor or LightGBM trained on `log1p(D28(t+91))` using grouped feature windows. Inverse-transform with `expm1`, clip at zero. Begin with **PyPI-only features**, then add GitHub and HN in controlled ablations.
- **Breakout classifier:** CatBoostClassifier predicting `breakout_91d` where eligibility rules pass. Calibrate probabilities on a **separate chronological calibration set** (e.g. isotonic or sigmoid), not the final test set.
- **Intervals:** Train p10/p50/p90 quantile regressors (or use a calibrated residual/conformal approach). Evaluate realised interval coverage on later dates; an 80% interval is meaningful only with measured coverage.
- **NLP research extension:** An off-the-shelf embedding model classifies/clusters problem discussions; aggregated dated topic counts become **features**. The LLM may summarise linked evidence, but does not invent numeric forecasts.
- **Graph research extension:** Feed historically valid dependency/network features into CatBoost first. Consider a temporal GNN only after demonstrating signal and sufficient time-stamped relations.

### Why multiple models?

One **shared versioned feature store**, a **regression model** for numerical forecasts, a **classification model** for a clearly defined breakout event, and a **calibration method** for uncertainty. This separation produces interpretable, testable outputs. A giant multimodal end-to-end model is not justified without much more aligned ground-truth data.

### Avoid hidden leakage

- Use only information `available_at <= t`.
- Split by prediction cutoff in chronological order. If validation starts at `T`, the training data used at that stage must have **fully matured 91-day outcomes by T** (include source reporting delay); apply the same rule before final testing.
- Many rows are adjacent overlapping windows; use an **embargo** and evaluate in blocks to prevent overly optimistic estimates.
- Freeze all hyperparameters/calibration before touching the final future-period test block.
- Report **seen-tools / new-weeks** performance separately from **held-out-tool / cold-start** performance.
- Don't let historic models learn a tool's later name, sector, final funding status or end-of-period total as a predictor.
- Maintain separate source-availability and missingness signals to avoid misleading feature correlations.

### Evaluation outputs (in `reports/`)

| Metric | Use |
|---|---|
| MAE on `log1p(downloads)` | Forecast error across small and large tools |
| MAE in raw downloads, by size band | Human-interpretable absolute errors |
| Breakout ROC-AUC and Average Precision | Ranking rare positives |
| Breakout Brier score and reliability curve | Quality of predicted probabilities |
| 80% interval coverage and width | Forecast uncertainty honesty |
| Precision@K / Recall@K | Whether research shortlist identifies future breakouts |
| Ablation Δ vs downloads-only | Whether GitHub/HN actually help |

Compare baselines on **identical eligible rows**. Publish n, time windows, package list, class prevalence and observed model performance; never fabricate metrics.

---

## 5. Backend contract (FastAPI + Pydantic)

### Required endpoints

| Route | Purpose |
|---|---|
| `GET /api/health` | Backend, data version, model availability |
| `GET /api/tools?query=&category=` | Curated catalogue with source/coverage status |
| `GET /api/tools/{tool_id}/history?start=&end=` | Daily/weekly observed metrics and source completeness |
| `POST /api/forecast` | Point-in-time prediction for selected tools |
| `POST /api/replay` | Historical future reveal **only if outcomes fully observed** |
| `POST /api/rank` | Top-K research shortlist given cutoff/filters |
| `GET /api/experiments/latest` | Baseline vs model metrics and provenance |

### Request contract

```json
{
  "tool_ids": ["tool-a", "tool-b"],
  "as_of_week": "2025-01-06T00:00:00Z",
  "horizon_days": 91,
  "compare_baseline": true
}
```

### Response contract

**Example only; all numeric predictions are invented test fixtures.**

```json
{
  "as_of_week": "2025-01-06T00:00:00Z",
  "horizon_days": 91,
  "model_version": "pypi-catboost-v1",
  "data_version": "extract-id",
  "predictions": [
    {
      "tool_id": "tool-a",
      "status": "ready",
      "target_date": "2025-04-07T00:00:00Z",
      "forecast_target": "pypi_distribution_downloads_trailing_28d",
      "observed_d28": 12000,
      "predicted_d28_p10": 13200,
      "predicted_d28_p50": 17800,
      "predicted_d28_p90": 25100,
      "predicted_growth_pct": 48.3,
      "prob_breakout": 0.46,
      "baseline_predicted_d28": 12000,
      "data_quality": {"warnings": [], "pypi_days_present_84d": 84},
      "evidence": [],
      "error": null
    },
    {
      "tool_id": "tool-b",
      "status": "insufficient_history",
      "target_date": "2025-04-07T00:00:00Z",
      "forecast_target": "pypi_distribution_downloads_trailing_28d",
      "observed_d28": null,
      "predicted_d28_p10": null,
      "predicted_d28_p50": null,
      "predicted_d28_p90": null,
      "predicted_growth_pct": null,
      "prob_breakout": null,
      "baseline_predicted_d28": null,
      "data_quality": {"warnings": ["Fewer than 84 verified days"]},
      "evidence": [],
      "error": "Insufficient point-in-time history"
    }
  ]
}
```

**Pydantic contract skeleton** (extend evidence/quality with typed nested models in implementation):

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["ready", "insufficient_history", "low_coverage", "unavailable", "unvalidated"]

class ForecastItem(BaseModel):
    tool_id: str
    status: Status
    target_date: datetime
    forecast_target: Literal["pypi_distribution_downloads_trailing_28d"]
    observed_d28: int | None = Field(default=None, ge=0)
    predicted_d28_p10: float | None = Field(default=None, ge=0)
    predicted_d28_p50: float | None = Field(default=None, ge=0)
    predicted_d28_p90: float | None = Field(default=None, ge=0)
    predicted_growth_pct: float | None = None
    prob_breakout: float | None = Field(default=None, ge=0, le=1)
    baseline_predicted_d28: float | None = Field(default=None, ge=0)
    data_quality: dict
    evidence: list[dict]
    error: str | None = None

class ForecastResponse(BaseModel):
    as_of_week: datetime
    horizon_days: Literal[91]
    model_version: str
    data_version: str
    predictions: list[ForecastItem]
```

Perform semantic validation beyond type checks: `p10 <= p50 <= p90`, no numeric predictions unless `status=ready`, UTC Monday cutoff, and cutoff source readiness. Generate frontend TypeScript types from the OpenAPI specification or maintain a shared schema test to prevent drift. Return errors per tool where possible (e.g. missing history for B must not block A). Invalid horizon/date should give HTTP 422. A replay response adds observed truth, error metrics and a `reveal_allowed` flag; current/unmatured forecasts have `reveal_allowed=false`.

### Suggested data path

```text
Source adapters -> immutable raw snapshots -> validated daily aggregates
    -> as-of joins and weekly feature rows -> trained model artefacts
    -> FastAPI inference -> React visualisation
```

Run **model training as an offline batch**, not inside the web request. Keep local predictions in DuckDB/Parquet for fast, deterministic hackathon demos. API responses should include version and warning metadata.

---

## 6. Frontend implementation (React + TypeScript)

### Required screens

**A. Observatory / Explore**
- Search and pick verified AI tools; show ecosystem/category, coverage, freshness.
- Comparison cards display *download activity*, *predicted growth*, *breakout probability*, and warnings; avoid generic “success score”.
- A ranked table is linked to the selected historical cutoff.

**B. Tool detail / Forecast**
- Single timeline chart: observed D28 history to `t`; baseline, median forecast, p10–p90 interval after `t`; visible vertical cutoff.
- Source evidence panels for PyPI, GitHub, HN; show precise windows, date freshness and missingness.
- Explain predictions by measured feature differences and model attributions **without causal language**.

**C. Time Machine / Replay (signature demo)**
1. Select a historical Monday cutoff.
2. Display exactly what was knowable then; hide post-cutoff activity.
3. Choose a few tools and optionally a top-K shortlist.
4. Show forecast + baseline **before** reveal.
5. Click **Reveal the next 91 days**; animate observed values, show errors and actual breakout outcomes.
6. Compare model ranking vs simple popularity ranking.

**D. Model Lab / Trust**
- Experimental comparison table: baseline, downloads-only CatBoost, +GitHub, +HN.
- Display test period, n, MAE, AP, calibration, Precision@K and source/label limitations.
- Do not show a source as helpful until the ablation actually demonstrates an improvement.

### Frontend state shape

```ts
type AppState = {
  selectedToolIds: string[];
  asOfWeek: string;          // ISO UTC week start
  horizonDays: 91;
  showActualFuture: boolean;
  selectedSources: Array<'pypi' | 'github' | 'hn'>;
  rankTopK: number;
  activeView: 'explore' | 'forecast' | 'time-machine' | 'model-lab';
};
```

### UX requirements

- Clearly distinguish **Observed / Forecast / Simulated** at every stage.
- Never fetch “now” values to construct a past company's profile in a historical replay.
- Show a useful loading/empty/error state and source gaps instead of fake numbers.
- Default to a curated, cached historical scenario so the live demo does not depend on external APIs.
- Show data and model versions unobtrusively in a provenance drawer.

---

## 7. Repository layout and team ownership

```text
signalshift/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── .env.example               # public config only; no secrets
├── data/
│   ├── catalog/tools.csv
│   ├── raw/                    # gitignored
│   └── processed/              # gitignored unless small demo snapshots
├── src/signalshift/
│   ├── ingest/
│   │   ├── pypi.py
│   │   ├── gharchive.py
│   │   ├── hackernews.py
│   │   └── catalog.py
│   ├── features/
│   │   ├── definitions.py
│   │   ├── build_features.py
│   │   └── build_labels.py
│   ├── models/
│   │   ├── baselines.py
│   │   ├── train.py
│   │   ├── predict.py
│   │   ├── calibrate.py
│   │   └── evaluate.py
│   ├── storage/
│   │   ├── database.py
│   │   └── schemas.py
│   └── api/
│       ├── app.py
│       ├── models.py
│       └── routes.py
├── frontend/
│   ├── src/components/
│   ├── src/pages/
│   ├── src/api/client.ts
│   └── package.json
├── tests/
│   ├── test_catalog.py
│   ├── test_features_asof.py
│   ├── test_label_horizon.py
│   ├── test_api_contract.py
│   └── test_replay_integrity.py
├── scripts/
│   ├── extract_data.py
│   ├── build_dataset.py
│   ├── train_models.py
│   └── export_demo.py
├── artifacts/                  # model files / manifests (gitignored or versioned)
├── demo/                       # small checked fixture + scripted scenario
└── reports/                    # real evaluation tables / plots
```

### Four independent Codex workstreams

| Owner | Owns | First deliverable | Avoid editing |
|---|---|---|---|
| **1. Data** | `ingest/`, `catalog/`, raw/processed datasets | Verified catalogue + daily PyPI metrics + source manifest | API/UI/model files |
| **2. ML** | `features/`, `models/`, evaluation | Leakage-safe rows, baselines, CatBoost experiment, honest test metrics | UI/ingest adapters |
| **3. Backend/integration** | `storage/`, `api/`, `scripts/export_demo.py` | FastAPI endpoints with fixture and then real model wiring | Model internals/UI |
| **4. Frontend/demo** | `frontend/`, demo storytelling | Search + chart + historical reveal from fixed contract | Python pipeline/API schemas |

**Integration sequence:** freeze catalogue schema + `ForecastResponse` JSON first; frontend and backend use a shared checked-in fixture. As each workstream finishes, merge small pull requests; one named integration owner enforces tests and checks the demo. On separate laptops use separate branches; use worktrees if one machine runs multiple Codex agents.

---

## 8. Implementation order and definitions of done

### Milestone 0 — Freeze contracts

- Commit `data/catalog/tools.csv` with verified mappings.
- Commit Pydantic response schema and matching TypeScript types/JSON fixture.
- Define `D28`, `t+91`, breakout eligibility and UTC conventions in tests.

### Milestone 1 — One reliable real data series

- Extract actual PyPI daily distribution counts for several verified AI packages.
- Audit continuity, counts, bot/mirror caveats and August 2026 definition change.
- Implement history API and chart with observed data; document the query and date span.

### Milestone 2 — Honest forecasting

- Build weekly feature/target rows with strict as-of validation.
- Train persistence + linear baseline + CatBoost regressor.
- Train breakout classifier only if enough eligible positive/negative labels exist.
- Export reproducible out-of-sample metrics; **stop claiming ML value if it doesn't beat baseline**.

### Milestone 3 — Time Machine

- Implement historical cutoff, conceal future, forecast, reveal reality, score selection.
- Cache a demo case using real observed history; no requests to third-party APIs during the stage demo.

### Milestone 4 — Does developer data add value?

- Add GH Archive source with coverage masks and date cutoffs.
- Retrain with/without GitHub on the **same test rows**.
- Add HN only if coverage and entity disambiguation are acceptable.
- Publish source ablations, including negative results.

### Milestone 5 — Ambitious research extensions

- Historical dependency adoption, product-discussion embeddings, validated breakout regimes.
- Founder-authorised retention exports for a *separate* true-usage outcome.
- Temporal market graph with point-in-time nodes/edges.
- Decision optimisation that accounts for calibrated uncertainty and research capacity.

**Definition of done for a defensible core:** end-to-end real PyPI history → reproducible weekly features → leakage-safe trained and baseline forecasts → model metrics on unseen historical weeks → working historical reveal → a transparent research shortlist → claims accurately match measured outcomes.

---

## 9. Critical tests

1. `test_features_asof`: add an event available after cutoff and assert features/predictions for the cutoff do not change.
2. `test_label_horizon`: verify trailing 28-day target exactly 91 days after weekly cutoff, inclusive/exclusive dates tested at boundaries.
3. `test_unmatured_labels`: most recent periods without `t+91` outcome are never assigned negative labels.
4. `test_pypi_definition_change`: pre/post Aug 24, 2026 use identical distribution-file filter.
5. `test_missing_vs_zero`: no source event coverage results in null + mask, never fake zero.
6. `test_tool_mapping`: reject unverified/duplicate PyPI package-to-tool mappings.
7. `test_split_embargo`: no training label used before it became observable; final test untouched by tuning.
8. `test_interval_order`: enforce `0 <= p10 <= p50 <= p90`.
9. `test_probability_range`: calibrated probabilities in `[0,1]`; `prob_breakout=null` for ineligible tools.
10. `test_replay_integrity`: forecast payload identical before/after revealing actual history; reveal can only add ground truth.
11. `test_api_contract`: JSON generated by API parses against TypeScript-facing schema/fixture.
12. `test_demo_offline`: precomputed fixtures and models support a complete replay without external API availability.

---

## 10. Tools, dependencies and execution

**Recommended:** Python 3.11+, `pandas` or `polars`, `duckdb`, `pyarrow`, `google-cloud-bigquery` (for PyPI), `httpx`, `pydantic`, `fastapi`, `uvicorn`, `scikit-learn`, `catboost`, `pytest`; React + TypeScript + Vite + a charting library. Pin installed versions in the lockfile; these are proposed dependencies, not installed components.

**Environment variables:** `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` (or application default credentials), optional `GITHUB_TOKEN`, `DATA_ROOT`, `MODEL_ROOT`; never commit secrets. BigQuery may bill for scanned data; filter package and timestamp ranges, dry-run queries and set a cost cap.

**Suggested commands after project setup** (scripts must be implemented before these work):

```bash
python scripts/extract_data.py --source pypi --catalog data/catalog/tools.csv
python scripts/build_dataset.py
python scripts/train_models.py
pytest -q
uvicorn signalshift.api.app:app --reload
# separate terminal, in frontend/: npm install && npm run dev
```

Use `pip install -e .` to make `signalshift` importable in the Python environment; choose package configuration in `pyproject.toml` accordingly. Test the above commands once they exist rather than assuming success.

---

## 11. Research sources and important limits (checked 2026-10-24)

- **PyPI public BigQuery dataset:** https://docs.pypi.org/api/bigquery/ — daily downloads in `bigquery-public-data.pypi.file_downloads`.
- **PyPI field/query documentation:** https://packaging.python.org/en/latest/guides/analyzing-pypi-package-downloads/ — timestamp, `file.project`, `file.filename`, installer fields and BigQuery setup.
- **PyPI 2026 logging change:** https://blog.pypi.org/posts/2026-08-31-download-counts/ — download-definition break and caution against treating requests as users.
- **GH Archive:** https://www.gharchive.org/ — hourly public GitHub event archive; audit historical completeness.
- **GitHub REST event history limitation:** https://docs.github.com/en/enterprise-cloud@latest/rest/activity/events — only recent events; not adequate for years of history.
- **HN Algolia:** https://hn.algolia.com/api — dated posts/comments and query filters.
- **deps.dev:** https://docs.deps.dev/ — package/dependency relationships, which are not automatically point-in-time historical adoption metrics.
- **Google Trends API alpha:** https://developers.google.com/search/apis/trends — limited access, not a guaranteed public feature source.
- **npm download counts (secondary ecosystem):** https://github.com/npm/registry/blob/main/docs/download-counts.md — daily ranges by package.

## 12. Final instructions to the implementation team / agents

- This file is the **source of truth for v1 input/output contracts**. Modify contracts by an agreed PR, not by independent agents.
- **First prove a downloads-only historical baseline works.** Then test whether GitHub and discussion features add predictive value.
- Treat **data provenance, cutoff integrity and model evaluation** as primary engineering features, not documentation afterthoughts.
- Keep the UI exciting through **time travel and reveal**, but don't disguise unavailable ground truth, insufficient coverage or unvalidated causal assumptions.
- Deliver real reproducible results and explain negative outcomes. A model that fails to beat the baseline is a finding, not a reason to invent a success metric.
