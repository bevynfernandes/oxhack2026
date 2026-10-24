# Trained public dimension models and the three forecast cards

Runtime update: the packaged baseline bundle is now connected through additive
`dimension_models` overlays on saved profiles and newly composed v2 reports. The
UI shows trained experimental status and eligible SDK-demand indices. Older saved
reports retain their original bytes; this supersedes statements below that no
experimental model results are connected. Company-outcome forecasts remain null.

24 October 2026. This report supersedes the untrained status and proposed
probability-based AScore in [the earlier research](public-model-research-20261024.md).
The user selected **separate dimension scores plus a descriptive combined index**,
with each target and limitation shown. The index is not a success probability.

## What actually ran

Five real-data baseline models were fitted and saved, followed by a sequential
architecture comparison with **72 fit attempts, 71 successful retained fits**.
One adoption neural network did not converge; its failure is retained and excluded
from selection. No synthetic labels or examples contribute to these reported
metrics. Synthetic examples are used only in unit tests.

The four numeric dimensions each compare 15 fitted candidates: training mean,
training median, four Ridge regularizations, Elastic Net, Huber regression, a
shallow decision tree, random forest, Extra Trees, histogram gradient boosting,
CatBoost, RBF support-vector regression, and a small neural network. Persistence
and constant zero are additional non-fitted comparators. Tree depth, sample-leaf
limits and regularization constrain model complexity; random seeds are fixed.

Sentiment compares 12 classifiers on the identical training-only TF-IDF vocabulary:
six logistic regressions (three regularizations, natural or balanced classes),
two multinomial Naive Bayes settings, Complement Naive Bayes, calibrated linear
SVM, random forest and a small neural network. SVM calibration uses entity-grouped
folds within training. The baseline experiment also retains a class-prior comparator.

Selection uses validation outcomes only: MAE for numeric targets; macro-F1,
then log loss, for sentiment. All preprocessing fits training data only. The
original test results had already been inspected before the user requested a
broader search, so these expanded comparisons are explicitly **exploratory**.
A new untouched evaluation is required before a production accuracy claim.
The methodology follows [scikit-learn's model selection guidance](https://scikit-learn.org/stable/modules/cross_validation.html).
The earlier research reviews tabular-model, startup-outcome, calibration and
leakage papers; their published accuracy is never imported as our performance.

## Public datasets actually acquired

| Dimension | Source and measured target | Effective benchmark population |
| --- | --- | --- |
| Adoption/retention | Official npm daily download history; next 30-day log download growth from two preceding 30-day windows | 37 complete commercial SDK histories from 53 predeclared SDKs; current/previous windows require at least 1,000 downloads |
| Industry/competition | Same npm history, with change in download share against a frozen technical peer cohort | Complete histories grouped by declared technical segment, at least three members; this is SDK share, not market share |
| Team/execution | Official GitHub release history; next 90-day `log1p` stable-release count from preceding 90-day cadence | 21 repositories with actually completed pagination; drafts and prereleases excluded; incomplete histories stay missing |
| Financial health | SequelSEC normalized SEC annual revenue and operating cash flow; next annual `asinh(OCF/revenue)` | 2,167 eligible annual pairs from 338 public software issuers before split filtering; reported USD metrics only, not derived values |
| Attention/sentiment | Original FinEntity company-entity annotations; Positive/Neutral/Negative sentiment around the named entity | 979 original news articles and 2,131 annotations; deduplication and entity/story purging leave 904 split-eligible annotations |

The declared cohort is `configs/experiments/public-sdk-cohort-v1.json`.
Its six technical segments are data infrastructure, analytics, feature management,
communications, identity and payments. These are training peers for shared proxy
models. We did not train six reliable industry-specific company-success models.
The existing company publication tests vector infrastructure (Qdrant and Weaviate).

Official acquisition semantics are documented in the
[npm download-count API](https://github.com/npm/registry/blob/main/docs/download-counts.md)
and [GitHub releases API](https://docs.github.com/en/rest/releases/releases).
Downloads include automated activity and cannot establish paying customers or
retention. Public release cadence measures public delivery, not founder quality.
The current SDK cohort also has survivor and developer-tool selection bias.

[FinEntity's paper](https://aclanthology.org/2023.emnlp-main.956/) and
[original author repository](https://github.com/yixuantt/FinEntity) provide
entity-level financial-news labels. The downloaded dataset is pinned to commit
`3b6cedc5485b669c2ed168f1d949f517636eb7b8`; its repository specifies ODC-BY.
Each target entity is replaced with `targetentity` within a bounded text context.
Entity surface strings determine split assignment; duplicate stories and stories
crossing partitions are excluded. Surface strings are not audited company-family
identities, and financial news does not validate Hacker News discussion sentiment.

[SequelSEC's publisher documentation](https://sequelsec.com/datasets/us-public-company-fundamentals)
distinguishes reported and derived financials. Retained normalized data and
README specify CC BY 4.0 attribution. This experiment uses only reported annual
revenue and operating cash flow from SIC 7370–7379, excludes incomplete/ambiguous
annual pairs, and requires positive comparable revenue. Current downloads can
change: the exact bytes, retrieval URLs, sizes and SHA-256 hashes are retained in
`sources.json`. The publisher also offers a
[dated Zenodo archive](https://doi.org/10.5281/zenodo.22832210); our results refer
to the retained bytes, not an unverified assertion that the daily feed equals
that archive. Latest restated financial values lack original filing availability;
this is a reconstructed benchmark, not an as-filed historical backtest.
Direct SEC source probes returned HTTP 403; their retained errors were not used
as financial data.

## Actual model comparison results

The numeric target units are transformed quantities, so MAE cannot be read as
percentage accuracy. Positive R² is useful evidence relative to a constant-mean
squared-error comparator; negative R² is a warning, even when MAE improves.

| Dimension | Validation-selected candidate | Held-out result | Interpretation |
| --- | --- | --- | --- |
| Adoption/retention | Shallow decision tree, depth at most 3 | MAE 0.1139; R² −0.090; prior-growth persistence MAE 0.1440 | Modest MAE improvement, weak generalization; not validated customer growth |
| Industry/competition | Shallow decision tree, depth at most 3 | MAE 0.0988; R² −0.213; persistence MAE 0.1154 | Better absolute error than persistence, poor variance explanation |
| Team/execution | Constant-zero baseline | MAE 1.6631; R² −5.736; persistence MAE 0.5148 | Validation preference fails on test; defer this dimension as unreliable |
| Financial health | Current-margin persistence | MAE 0.1349; R² 0.879; fitted Ridge MAE 0.1640 | No demonstrated need for ML over the simple baseline in this population |
| Attention/sentiment | Balanced logistic regression, C=0.1, TF-IDF word unigrams/bigrams | Accuracy 73.8%; macro-F1 0.591; log loss 1.008 | Better class balance than the initial unweighted model, weak negative-class detection and probability quality |

The initial portable Ridge/TF-IDF baseline JSONs remain separate from the expanded
comparison winners. For example, the initial unweighted sentiment model achieves
78.6% accuracy, macro-F1 0.577 and log loss 0.611. The balanced validation winner
has lower test accuracy and worse probability loss; it is chosen for validation
macro-F1, not advertised as the best calibrated probability model. Its negative
recall is only 2/11, versus 1/11 initially. Neither is ready as a broad company
sentiment service.

| Dimension | Train rows / subjects | Validation rows / subjects | Test rows / subjects |
| --- | --- | --- | --- |
| Adoption | 310 / 24 | 44 / 4 | 119 / 7 |
| Competition | 295 / 23 | 44 / 4 | 119 / 7 |
| Execution | 221 / 17 | 27 / 3 | 15 / 1 |
| Finance | 245 / 101 | 101 / 52 | 165 / 85 |
| Sentiment | 699 / 393 | 102 / 74 | 103 / 66 |

Numeric subjects are SDK projects or issuer CIKs, not universally verified legal
families. Known SendGrid/Twilio linkage shares a split. Stable subject hashing
separates entities, while target measurement endpoints must fall within their
chronological partition. SDK cutoffs are June 2023, June 2024 and December 2025;
financial cutoffs are December 2019, December 2022 and December 2025. SDK demand
windows and release windows do not overlap their own targets; rolling rows within
a partition remain correlated. Repeated rows do not create independent firms.
Execution's one-repository test has insufficient population support.

## How this relates to the three top forecast cards

The current contract is in `models/startup_outlook.py` (`FORECAST_HORIZONS` and
`OutcomeForecast`). `frontend/src/pages/research/CompanyDossier.tsx` renders the
cards, currently with an explicit dash and “Prediction unavailable”. It does not
read these experimental model artifacts. Neither training command changes the
public API, report serialization or frontend.

| Top card | Required company outcome | How dimensions could help | Present status |
| --- | --- | --- | --- |
| Growth, 24 months | Verified operation plus comparable revenue or active paying-customer growth through the calendar endpoint | Pre-origin adoption, demand/share, execution, finance and text features can be tested as predictors | No trained 24-month commercial-growth head; SDK next-month growth is a different target |
| Survival, 24 months | Verified continued company operation at the endpoint, with dated shutdowns and explicit handling of acquisitions/censoring | Same available pre-origin features, tested against independent operating outcomes | No trained survival head; a live website, SDK releases or an acquisition cannot silently become this label |
| Financial health, 12 months | The existing viability proposal uses nonnegative trailing operating cash flow plus continued operation; final target policy remains pending in the serving contract | Comparable current financials and other pre-origin dimensions can be tested | Public-issuer next-annual cash-margin proxy is trained, but it does not establish this full endpoint for private startups |

The older [company outcome policy](company-outcome-policy.md) and
`features/company_outcomes.py` include **financing/acquisition**, not survival.
Do not relabel that third v1 target as survival. A survival contract needs its own
target definition and adjudicated dated cohort. For a mature binary 24-month
cohort start with regularized logistic regression against prevalence, then tree
challengers; for censored follow-up consider a separately validated survival
model. Discrete-time survival or Cox models cannot rescue missing event evidence.

The dimensions and AScore can be displayed alongside outcomes, but averaging
sentiment, download growth and cash margins cannot produce a calibrated survival
probability. A future outcome head may use raw dimension features or leakage-safe
out-of-fold predictions and missingness indicators, with a same-row raw-feature
baseline. It needs its own mature labels, chronology, family separation,
calibration, and independent holdout. Our proxy datasets do not provide one joined
company panel with all five dimensions and these outcomes.

For additional survival evidence, [IdeaProof's failure corpus](https://ideaproof.io/datasets)
offers documented shutdowns with sources under CC BY 4.0, but explicitly contains
no survivors and cannot estimate failure rates. It is a candidate adjudication
source, not a balanced survival training dataset. A closed-only corpus or present
YC “inactive” flag cannot produce the missing dated survivor cohort. Historical
Crunchbase snapshots have different access and licensing from modern data; neither
has been silently imported as a verified point-in-time company panel here.

## Training versus Bevyn's inference data

The required match is definitions, units, identity and feature derivation across
separate companies/time periods. Reusing training examples as the test set would
invalidate accuracy measurement. Having the same API does not eliminate domain
shift or historical-availability problems.

| Model input | Match to current backend | Required eligibility check |
| --- | --- | --- |
| Current/previous 30-day npm counts | Same official count source and window type | Exact SDK, 30 complete days per window, nonnegative counts, matched publication cutoff and supported volume |
| Stable GitHub releases in previous 90 days | Same source/filter type | Numeric repository identity, complete pagination, published timestamps, no drafts/prereleases; domain support is weak |
| Revenue/OCF | Same named 12-month USD measures are defined | Same period/accounting basis, issuer versus private-company applicability; current real company publication has missing values |
| Entity sentiment text | Not present in structured HN count output | Need actual dated company-linked text and entity spans, deduplication, provenance, coverage and target-domain validation |
| Peer SDK histories | Not present as an approved complete production competition feature | Exact retained peer membership and identical complete windows; unknown peers must not become zero |

`research/attention.py` currently structures object ID, URL and timestamp, not
sentiment-ready title/body text. Raw retained API responses alone do not constitute
an approved production text feature. The financial model's public-issuer population
also differs from early private vector companies. A universal five-score inference
adapter is therefore not claimed. The source-readiness audit remains relevant.

## Descriptive AScore

The baseline experiment retains an explicit equal-weight recipe:

- Numeric predictions map to midrank percentiles against training outcome values.
- Sentiment maps to `50 * (1 + P(Positive) - P(Negative))`.
- AScore is the mean of the five 0–100 dimension scores.
- Missing or ineligible dimensions cause abstention; there is no default 50 or
  silent weight renormalization.

Weights are a product preference specified by the user. They were not learned
from company success. The combined index has no independent company-health
validation, and unreliable execution / unsupported production inputs currently
prevent a defensible complete live score. `ascore.index.json` records the recipe;
it is not an additional trained sixth predictor or a top-card probability.
The expanded candidate comparison does not silently replace the baseline index
recipe or ship a failed selected model.

## Reproduction and artifacts

```bash
# Public SDK collection, cached raw responses with source hashes.
UV_CACHE_DIR=.cache/uv uv run --frozen --no-sync python tools/collect_public_sdk_data.py \
  configs/experiments/public-sdk-cohort-v1.json .cache/dimension-training-20261024

# Five portable interpretable baseline models and explicit index recipe.
UV_CACHE_DIR=.cache/uv uv run --frozen --no-sync python -m oxhack2026 models train-public \
  .cache/dimension-training-20261024 configs/experiments/public-sdk-cohort-v1.json \
  artifacts/public-dimension-models-20261024

# Sequential linear/tree/boosting/kernel/neural comparisons on identical rows.
UV_CACHE_DIR=.cache/uv uv run --frozen --no-sync python -m oxhack2026 models compare-public \
  .cache/dimension-training-20261024 configs/experiments/public-sdk-cohort-v1.json \
  artifacts/public-dimension-comparison-20261024
```

The non-SDK raw captures are `finentity.json`, `fundamentals.csv.gz`,
`companies.csv.gz` and `README.md` beneath the cache root. `sources.json` records
exact download URLs, timestamps, byte sizes and SHA-256 hashes; retain the original
SequelSEC README/attribution when redistributing. Redownloading mutable sources
requires comparing hashes or recording a new source manifest, not claiming an
identical run.

Saved local outputs (generated artifacts are gitignored):

- `artifacts/public-dimension-models-20261024/run.json`, five `*.model.json`,
  five `*.evaluation.json`, `sources.json`, and `ascore.index.json`.
- `artifacts/public-dimension-comparison-20261024/comparison.json`, per-dimension
  comparisons and every converged candidate's weights with SHA-256 digests.

Baseline numeric and sentiment JSONs have explicit portable inference functions
in `models/public_dimensions.py`. Expanded architecture candidates are self-created
trusted-local pickle artifacts (vectorizer included for text); they are not
accepted as arbitrary uploaded models or loaded by serving code. Pickle is only
for retained local research; convert and validate a chosen model before deployment.
All manifests explicitly mark public serving as unapproved.

Verification: 693 Python tests passed, with 17 integration tests deselected.
Ruff lint/format checks, mypy over the package/tests plus the collector, and the
strict documentation build passed. Saved model/evaluation digests and current
training/comparison code hashes were verified against both run manifests.
