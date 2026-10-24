# Public-data specialist models and combined AScore

Research date: 24 October 2026. User direction: five separate specialist scores,
then a combined score derived from them; public sources only; training inputs must
match the inputs available for new-company inference.

## Later training results and clarified AScore

The user subsequently chose a descriptive dimension index. Five public-data
proxy baselines are now trained and 72 model configuration fits were attempted
(71 converged). See [actual training results, limitations, reproducible commands
and the three-card mapping](public-dimension-training-20261024.md). The original
company-outcome trainers below remain distinct; they do not supply trained
survival or commercial-growth forecasts. This document preserves the earlier
source/readiness audit; its untrained status and proposed probability AScore
are superseded by that later report.

## Original decision

Use small regularized tabular models first. Train each specialist against an
explicit observable endpoint, with a prevalence comparator, then test a regularized
logistic combiner on later held-out specialist predictions. Chronological
out-of-fold stacking is a later, more data-efficient extension. A small
CatBoost challenger is reasonable after a sufficient labelled panel exists.
Neither a neural network nor a language model fixes missing labels.

This is an architecture and source-selection decision, **not a trained-model
release**. The verified local company publication contains two companies at one
origin, zero resolved ownership families and no supplied outcome-label artifact.
No defensible accuracy estimate or complete five-group AScore is available yet.
The offline trainer implements the specialist baseline and a three-period
held-out combiner, reporting readiness failures without inventing weights.
A real fitted combiner remains dependent on public historical publications,
complete specialist predictions and mature labels for a frozen endpoint.

## What Bevyn's backend actually collects

Reviewed the locally available merged Dev 1 work, including `6528b76` (research
jobs), `cf17706` (integrity/privacy/leases), and the readiness branch at `0704a39`.
This review covers available code and handoffs, not unpublished agent state.

A later read-only check of the live repository found no newer collector handoff:
the latest Dev 1 readiness comment still reports HN-only outside-company research,
failed data gates and unresolved financial inputs. The local coordination note
assigns fresh outside-company resolution to Bevyn. This report does not assume
that work has already produced historical training publications.
The subsequently opened [PR #59](https://github.com/bevynfernandes/oxhack2026/pull/59)
changes four frontend files for dimension expansion; its description explicitly
states there are no backend changes. The open
[issue #57](https://github.com/bevynfernandes/oxhack2026/issues/57) assigns outside-
directory research to Bevyn and explicitly preserves unknown commercial metrics
and null untrained predictions. Neither supplies a historical label panel.

| Input | Implemented production semantics | Training implications |
| --- | --- | --- |
| npm | Complete current and previous 30-day SDK download windows | Same package identity and complete days at every origin; downloads are not users, retention or revenue |
| GitHub | Verified numeric repository ID; paginated published stable releases in 90 days | Reuse the exact release/draft/prerelease filters; incomplete pagination is missing |
| Financing | One reviewed company announcement with amount/date anchors | Not total funding, unrestricted cash, runway or solvency |
| Hacker News | Exact-domain story URLs in a bounded window; truncated responses are missing | Currently a link count only, not comment sentiment or broad media coverage; first-observed availability is collection time |
| Commercial metrics | Revenue, operating cash flow and paying-customer definitions exist | The real two-company publication has missing values for all three |
| Identity/family | Dated evidence-aware resolution with explicit unresolved results | Both current companies have unresolved families; current ownership cannot be backfilled into history |

Relevant implementations: `ingest/company_pipeline.py`, `research/attention.py`,
`features/company.py`, `features/company_policy.py`, and `storage/company.py`.
Current tested business sector is vector/developer infrastructure (Qdrant and
Weaviate); the five specialist groups are evidence dimensions, not five industries.
The 229-company YC discovery file is broader and needs sector/stage checks before
using its companies as training peers.

The executable audit was run against `company-vector-20261024-v1` through
`LocalCompanyStore`, which verifies the source content and raw evidence hashes.

| Group | Companies with fresh usable metrics | Usable observations |
| --- | ---: | ---: |
| Adoption/retention | 2 | 4 |
| Attention/sentiment | 0 | 0 |
| Financial health | 0 | 0 |
| Industry/competition | 0 | 0 |
| Team/execution | 2 | 2 |

Fresh research HN observations live in a separate research inventory and are not
silently included in the older source snapshot. A future training adapter must
preserve their original measurement, availability and capture times.

Audit artifact: `artifacts/company-training-readiness-20261024/objects/b3/`
`b3f4e7a6c8983d1bc75e29d8d3de101e73a1c70d6a4b1d75bb4e77fb52f0fb83`.
The earlier 59-company readiness audit and four-company closure review are in
`startup-target-readiness.md` and `startup-label-audit.md`. Their unadjudicated
statuses are not training labels.

## Research that changes the implementation decision

The following is a focused primary-source review, not an exhaustive systematic
review. Reported results belong to their original populations and definitions;
none is an accuracy claim for our backend.

| Study | Relevant finding or method | Reproducibility and decision for this project |
| --- | --- | --- |
| [Thirupathi et al., ICAIF 2021, *A Machine Learning Approach to Detect Early Signs of Startup Success*](https://github.com/abhit20/ML-Startup-Success) | XGBoost on 3,160 SBIR/STTR recipients; endpoint is IPO/M&A. Authors release study data and analysis. | Useful auditable benchmark candidate, but award-recipient sampling, Crunchbase/person features and exit labels differ from our inference population and financial-health endpoint. Do not import its claimed performance. Verify data-specific reuse rights separately from the code licence. |
| [Antretter et al., 2019, *Predicting new venture survival*](https://alexandria.unisg.ch/entities/publication/60ba54aa-b24f-4c01-a354-4883f2be70e8) | Examines online legitimacy using over 187,000 tweets from 253 ventures. | Supports testing attention features. Twitter content is not the current HN URL-count feature; historical collection/access and population differences prevent direct replication of the reported survival result. |
| [Wright, Nagle and Greenstein, 2024, *Contributing to growth?*](https://business.columbia.edu/faculty/research/contributing-growth-strategic-role-open-source-software-global-startups) | Matches GitHub participation to PitchBook software firms and finds a positive relationship with growth. | Strong motivation for an execution-source ablation. The matched proprietary firm panel is not our public training dataset; counting SDK releases is also a different construct from employee OSS contributions. |
| [Mashhadi et al., revised June 2026, *Interpretable Machine Learning for Predicting Startup Funding, Patenting, and Exits*](https://arxiv.org/html/2510.09465v2) | Separate firm-quarter endpoints, time-separated development/holdout/final windows, fixed preprocessing, logistic/tree comparisons. | Adopt endpoint separation and temporal preprocessing discipline. Crunchbase/USPTO predictors and funding/patent/exit labels do not supply our cash-flow or survival labels. This preprint is methodological evidence, not independently replicated performance. |
| [Benhenda, 2026, *YC Bench*](https://arxiv.org/abs/2604.02378) and [author data/code](https://github.com/benstaf/ycbench) | Open W26 startup/mentions data and a short-term pre-Demo-Day traction proxy. | Reproducible attention benchmark candidate. A proxy partly constructed from mentions cannot validate a general health score or growth/survival forecast from mentions. Do not train against that score and call it independent success ground truth. |
| [Gupta et al., YIFE, September 2026, author repository](https://github.com/guptasiddharth2409/yife-startup-prediction) | Logistic/tree comparisons on YC companies with a cohort-based holdout. | Authors explicitly warn that funding/investor features can postdate the nominal origin and overlap the target. Useful leakage counterexample and feature inventory; not an accepted ex-ante training panel. |
| [McCarthy et al., 2023, *The impact of founder personalities on startup success*](https://www.nature.com/articles/s41598-023-41980-y) | Studies founder/team associations in 21,187 startups. | Released data are aggregated, not a company-level training panel. Do not infer personality, education or founder quality from unavailable personal data; this does not justify training a team model on release counts. |
| [Grinsztajn et al., NeurIPS 2022, *Why do tree-based models still outperform deep learning on tabular data?*](https://arxiv.org/abs/2207.08815) | Benchmarks 45 datasets and finds strong tree-model performance for medium tabular datasets. | Justifies a small tree challenger after a linear baseline. It does not establish that trees beat logistic regression on our dataset, nor that all modern tabular neural methods are inferior. |
| [Hollmann et al., Nature 2025, *Accurate predictions on small data with a tabular foundation model*](https://www.nature.com/articles/s41586-024-08328-6) | TabPFN demonstrates that pretrained tabular transformers can work well with small datasets. | Keep as a later benchmark rather than assuming deep models never work. More runtime/dependency and explanation complexity is unwarranted before a usable labelled panel exists. Article abstract/metadata inspected; full page retrieval failed. |
| [Hutto and Gilbert, ICWSM 2014, *VADER*](https://ojs.aaai.org/index.php/ICWSM/article/view/14550) | Lightweight rule/lexicon sentiment model with public implementation. | Suitable first sentiment feature extractor once actual company-linked text exists. Validate on manually labelled HN/company-discussion examples; its original social-text performance is not HN or startup-outcome accuracy. |
| [van der Laan, Polley and Hubbard, 2007, *Super Learner*](https://pubmed.ncbi.nlm.nih.gov/17910531/) | Learns a combination of candidate predictors using cross-validation. | Basis for learning the AScore from specialist predictions. Our adaptation needs chronological, label-purged, family-aware folds rather than random folds. |
| [Guo et al., ICML 2017, *On Calibration of Modern Neural Networks*](https://proceedings.mlr.press/v70/guo17a.html) | Demonstrates that discrimination/confidence and calibrated probabilities differ. | Require calibration diagnostics and a separate calibration period if fitted. Temperature scaling results for neural classifiers do not automatically prescribe the right calibrator for our logistic models. |
| [Kapoor and Narayanan, 2023, *Leakage and the reproducibility crisis in machine-learning-based science*](https://www.sciencedirect.com/science/article/pii/S2666389923001599) | Documents multiple leakage mechanisms affecting scientific ML evaluation. | Record prediction-time availability, target construction and dataset provenance; enforce family/time separation and compare identical held-out rows. Abstract/indexed text inspected; some full-text endpoints were access-blocked. |

## Public sources to use, and their limits

| Source | Reproducible raw inputs and matching rule | Availability and deployment decision |
| --- | --- | --- |
| [npm download API](https://github.com/npm/registry/blob/main/docs/download-counts.md) | Daily package counts; retain immutable package/company mapping, raw JSON, exact windows and complete-day coverage | Implemented. First choice for SDK adoption; batch activity and CI downloads remain contamination. No claim of customer retention. |
| [GitHub release API](https://docs.github.com/en/rest/releases/releases) | Numeric repository identity, published timestamps, stable release filters, all required pages | Implemented. Best immediate execution alignment. Current release metadata can be edited/deleted; preserve captures rather than asserting historical immutability. |
| [GH Archive](https://www.gharchive.org/) | Timestamped public event archives; aggregate only verified repositories and event kinds | Public archive candidate for execution/contributor history. Not currently a company-level production feature; add matching historical/live event semantics before training on it. Private work remains invisible. |
| [HN Algolia API](https://hn.algolia.com/api) | Exact-domain links, deduplicated story IDs, declared time window, completeness checks | Implemented for counts. Sentiment would require text/comment capture, company disambiguation and annotation; points/comment totals retrieved today cannot be treated as pre-origin totals. |
| [Tranco](https://tranco-list.eu/api_documentation) | Fixed list IDs, dates, provider/configuration metadata and domain mapping | Historical reach candidate. Rank is not visits or active users; absence is censored/unknown. Confirm timezone of availability and provider changes. The earlier 59-row audit had only 11 matches. |
| [GDELT](https://gdeltproject.org/data.html) | Timestamped news/entity/domain records with deduplication and language/source coverage | Optional attention/industry extension, not implemented. Entity-name ambiguity and article copyright require separate controls. A free archive does not make BigQuery computation free. Prefer bounded raw extracts first. |
| [SEC Form C datasets](https://www.sec.gov/data-research/sec-markets-data/crowdfunding-offerings-data-sets) and [field definitions](https://www.sec.gov/dera/data/crowdfund.pdf) | Private crowdfunding issuer disclosures: revenue, cash/equivalents, short/long debt, assets, net income and employees, with filing identity | Best additional financial-source lead found. These are fiscal-year disclosures, not automatically trailing-12-month metrics. Bulk documented fields do not provide operating cash flow or runway. Match legal entity/CIK/domain, accounting periods, amendments and publication time. Crowdfunding issuers may differ materially from venture-backed vector infrastructure. |
| [SEC companyfacts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Filing-vintage US-GAAP/IFRS revenue and cash-flow facts, units and periods | Appropriate only for confirmed reporting entities. Do not train on public incumbents and assume calibration on private startups. Retain original filing availability and restatement vintages. |
| [SEC Form D](https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets) | Exempt offering filings; link accession/amendment chains to verified issuer identity | Financing context only. Offerings are not cash inflows or solvency labels. Prior 2024-Q1 audit found no accepted matches to the 59-company cohort. |
| [YC public directory mirror](https://github.com/yc-oss/api) | Commit-pinned company discovery rows including inactive/acquired entries | Discovery only. Current headcount/taxonomy/status do not become historical predictors or dated outcomes. Preserve all selected statuses and resolve name/domain/family histories. |
| [Common Crawl index](https://index.commoncrawl.org/) and [archive access](https://www.commoncrawl.org/get-started) | Dated URL-index entries and bounded WARC records from pinned crawls | Useful public identity/domain and original-publication leads. A captured page can support an assertion; a missing crawl cannot prove shutdown. Archive capture date alone is not necessarily the original publication date. No cohort-wide archive join has been run here. |
| [Buffer Open](https://buffer.com/open) and [Baremetrics Open Startups](https://baremetrics.com/open-startups) | Voluntarily public SaaS metrics and dated company reports; preserve revenue/customer/churn definitions and originals | Promising small accounting/retention validation subset. Public pages were inspected, but historical machine-readable panels were not downloaded. Disclosure participation and surviving dashboards create selection bias; repeated months do not substitute for independent companies or negative outcomes. MRR/ARR are not recognized trailing revenue or operating cash flow. |
| First-party closure, continuity and financial publications | Capture dated statements and originals; independently adjudicate company/product and calendar horizon | Candidate outcome evidence. Easy-to-find companies are a biased subset; audit every preselected cohort member and retain unknown/conflicting/censored states. |

**New source probe:** the SEC documentation and government catalogue expose the
Form C archive. A direct fetch of the documented 2024-Q1 ZIP returned HTTP 403.
The actual error response and capture metadata are retained under
`.cache/public-model-research-20261024/`; this is not a downloaded financial panel
and establishes neither cohort matches nor financial-label coverage. No provider
block was bypassed. The exact reference is:
`https://www.sec.gov/files/dera/data/crowdfunding-offerings-data-sets/2024q1_cf.zip`.

## Meaning of the five scores and the combined AScore

The recommended first predictive experiment uses the **same independently
observed endpoint and horizon** for all five specialists. For example, after its
exact label policy is frozen, operating commercial growth at 24 months. Each
specialist sees only its assigned pre-origin inputs. Its score is `100 * p_group`
for that explicitly named outcome, not a standalone scientific measurement of
"team quality" or general startup success. Predictive associations are not causal
explanations.

For multiple product endpoints, fit and evaluate independent sets of specialists
and combiners. A score predicting survival and a score predicting financial
health cannot be averaged and described as one calibrated probability. The
existing financing/acquisition v1 label is not the proposed survival endpoint.

The combined model is proposed as:

```text
AScore(Y, horizon) = 100 * sigmoid(
    intercept + sum(weight[group] * logit(p_group))
)
```

The implemented first version is held-out blending: fit all five specialists on
the base period, fit a logistic combiner on their predictions for a later blend
period, then evaluate the frozen system on a still-later final test. All three
periods must be company- and family-disjoint, with mature label support available
at each fitting cutoff. Base specialists remain fixed after fitting; they never
train on blend or final-test labels. This is simpler than cross-validated stacking,
but uses data less efficiently and should not be called cross-validation.

Clip probabilities at a fixed `1e-6` before logits. Fit scaling only on complete
blending rows, followed by L2 logistic regression (`C=1`, `lbfgs`, 1,000 iterations).
The portable artifact retains the five specialist models, outcome, group order,
source identities, cutoffs, preprocessing, coefficients and training digest.
The combined AScore is 100 times the endpoint probability, not a multi-outcome
utility. Final-test Brier/log loss, AUC and reliability bins compare the combiner,
blending prevalence and all five specialists on identical complete rows, retaining
label abstention counts. Add a same-row all-feature baseline and uncertainty
analysis before selecting a public model; no test result automatically approves
release. Keep a separate later calibration period if fitting a calibrator.

If a larger cohort permits chronological cross-validated stacking, fit the combiner
on out-of-fold specialist predictions with family separation and label-maturity
purges at every fold. Evaluate once on the untouched final test; retain the simpler
model if combination adds no value.

Missing specialists need an explicit, validated serving policy. The initial
complete five-group AScore should abstain when a required group is unavailable.
Do not fill with 50, zero or renormalized weights. A separately validated reduced
model can later have a distinct name and eligibility rule. Report data coverage
separately from probability and avoid describing missingness as a weakness in the
business itself.

If the intended AScore is instead an investor's multi-outcome utility, its endpoint
weights are preferences, not learned facts. That requires a separately documented
mapping after independent endpoint validation. A descriptive peer percentile is
also possible but must be labelled a percentile, not a success forecast.

## Architecture and reproducible experiment

The implemented first candidate uses signed `log1p` numeric features, training-only
median imputation, one missingness indicator per feature, training-only scaling
and L2 logistic regression (`C=1`, `lbfgs`, maximum 1,000 iterations). This preserves
negative cash flow and limits domination by large currency/download units.
No class rebalancing, SMOTE or threshold tuning changes the real prevalence.
Portable JSON stores medians, scales, coefficients, intercept, sklearn version,
ordered metric definitions, selected source vintages and a training digest.
Coefficients describe effects on log odds; they are not probability percentage
points or causal effects.

`models/company_training.py` uses the same `company_feature_frame` projection as
production evidence. It rejects definition/unit drift, synthetic training sources,
duplicate origins, future label support and conflicting family joins. Test
companies and resolved test families are excluded from fitting. Companies without
usable predictors abstain. Predeclared distinct-family support gates default to
20 training and 10 test families **per class**; these are safeguards, not a power
calculation or automatic release approval. Held-out Brier/log loss, AUC, reliability
bins and abstention are retained alongside an identically evaluated prevalence
baseline. Add PR-AUC and family-block uncertainty before a rare-outcome release.

`configs/experiments/company-local-v1.json` lists existing production metric IDs
per specialist. The empty attention and competition arrays are intentional:
research HN observations need a versioned adapter and no approved competition
metric exists. This is a feature inventory, not an executable labelled experiment.
`CompanyExperimentPlan` JSON is required for fitting; no valid real plan can be
constructed from the current single-origin publication alone.

```bash
UV_CACHE_DIR=.cache/uv uv run --frozen --no-sync python -m oxhack2026 models audit \
  .cache/company-handoff/source company-vector-20261024-v1 \
  artifacts/company-training-readiness-20261024

# Once exact historical publications, a frozen plan and adjudicated labels exist:
UV_CACHE_DIR=.cache/uv uv run --frozen --no-sync python -m oxhack2026 models train \
  /path/to/company-store /path/to/frozen-plan.json /path/to/labels.json \
  artifacts/company-experiments/run-id

# Three-period five-specialist blending, once its frozen plan/data exist:
UV_CACHE_DIR=.cache/uv uv run --frozen --no-sync python -m oxhack2026 models train \
  /path/to/company-store /path/to/combiner-plan.json /path/to/labels.json \
  artifacts/company-experiments/combined-run-id --combined
```

Commands emit content-addressed artifact references. The training run retains the
plan/label byte hashes, verified source manifests and a result reference; failed
gates also produce a retained report. No runtime vendor call or public probability
publication happens during training. The current API continues to return explicit
untrained/null scores. Synthetic tests exercise fitting and leakage protections;
their metrics are never promoted as real-data validation.

## Next data deliverable

Extend the preselected public cohort across dated origins, preserving failures and
acquisitions. Before collecting all feature families, verify legal/domain/repository
identity, company continuity and family membership at each origin. Adjudicate a
bounded cohort-wide sample of endpoint labels to estimate coverage in both classes.
Then backfill the exact npm/release/HN definitions and compare cohort/sector/stage
coverage with intended inference companies. Use disjoint families and whole later
origins, with label-maturity purges; select models on development, not final test.

For financial health, first verify the Form C raw archive and its actual matched
coverage, then review any cash-flow exhibits needed for the frozen endpoint. If
the vector-infrastructure cohort lacks comparable disclosures, retain financial
abstention. The literature does not justify substituting fundraises, net income,
domain rank or sentiment for missing cash-flow labels.

## Follow-up evidence and access audit

The first four inactive discovery entries remain the declared bounded label-review
subset; follow-up searches do not change the cohort, origin or horizon to make a
positive result easier to obtain. A newly located
[founder announcement on Fly.io](https://community.fly.io/t/deprecation-notice-for-enveloop/25821)
is dated 2 September 2025 and states a planned Enveloop service end of 1 October
2025. The [YC profile](https://www.ycombinator.com/companies/enveloop) identifies
the same founder and developer-messaging product, and the
[company launch post](https://blog.enveloop.com/hello-from-enveloop/) is dated
18 November 2022. These sources improve current identity and event evidence.
They do not establish legal dissolution, unchanged ownership or continuity from
the proposed January 2022 origin. In particular, a 2025 service shutdown cannot
be coded as a shutdown within the frozen January 2022–January 2024 window.
No Boolean training label was added. A direct raw-page download failed during
TLS negotiation; web-readable evidence is linked, without claiming a retained
raw-byte hash for those pages.

The SEC's documented `2024q1_cf.zip` archive returned HTTP 403 both with the
default client and with an identified research User-Agent. Error bodies and
capture metadata are retained in `.cache/public-model-research-20261024/`.
This is an access failure, not an empty financial dataset or evidence that no
company has disclosures. No archive contents or coverage are claimed.

The [official Wefunder API reference](https://docs.wefunder.com/api-reference)
offers another public-disclosure route: Form C fiscal statements and issuer
cash/burn disclosures, with issuer currencies and document links. Even public
reads require an OAuth token; the server-side flow needs app credentials. No
credentials were created or used and no records were downloaded. Its live
explore list is curated by traction/approval, so use of that list alone would
introduce selection bias. A closed offering means a completed fundraise, not a
closed business. Current disclosures also need filing/statement dates and
archived availability before any historical feature projection. This remains
a source candidate, not a working inference adapter or an accepted training set.
