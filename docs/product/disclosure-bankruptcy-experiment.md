# Public disclosure timing and later bankruptcy: experiment plan

25 October 2026. Prespecified before fitting this experiment. This is one candidate
financial-risk component, not five business scores, operating survival, growth or
an Overall index. It does not change the full product's outstanding requirements.

## Data and meaning

Use the authors' public ECL CSV from
`https://cloud.ilabt.imec.be/index.php/s/TFGZgF3EyS4jsz2/download`, SHA-256
`bde2184a88e3130e1dec7e06b2e04072c23adced0ef36f323e3bdd600a5d1608`.
The [authors' repository](https://github.com/henriarnoUG/ECL) publishes it for
benchmark reconstruction. No Compustat values are used. Preserve the original
CSV and attribution; do not redistribute a vendor financial extract.

The [2022 paper](https://aclanthology.org/2022.finnlp-1.25/) places the prediction
window after the actual filing date, avoiding the leakage caused by using fiscal
year end as the decision date. The ECL population is a selected US reporting-firm
sample joined to the LoPucki bankruptcy database. Its coverage of large Chapter
7/11 cases does not establish complete bankruptcy coverage for small companies.
A Chapter 11 filing also does not establish permanent business cessation.

Target: a recorded bankruptcy filing strictly after an annual report's filing
date and no later than one calendar year afterwards. Recompute this from the
provided event dates and check agreement with the authors' label. Exclude rows
with a recorded bankruptcy on/before the origin, invalid chronology, conflicting
duplicate filings, unknown eligibility, or incomplete outcome maturity.

Predictors: current report filing lag in days, previous annual-report filing lag,
days since previous annual filing, change in filing lag, and an explicit indicator
for missing previous history. Previous observations must precede the origin.
CIK, company name, bankruptcy date, label, partition and future filings are never
model features. Do not call reporting tenure company age or delay cash runway.
These inputs can be reconstructed from the same SEC submissions metadata that the
live collector captures, subject to verified issuer identity and historical pages.

## Frozen evaluation

Prefit feasibility amendment: the initial 2012-only validation window contained
three positive issuers and was inadequate for model selection. No model or
predictive metric had been computed. Before fitting, replace that design with
training through 2006 and validation during 2008–2013, preserving the issuer
buckets and 2015–2017 test window. This gives 187 training, 22 validation and 13
test positive issuers in the initial eligibility audit. Retain the rejected first
design's panel/audit separately. This amendment addresses sample size, not model
performance; no further split adjustment is permitted after fitting begins.

- Identify issuers by normalized CIK. SHA-256(CIK), first byte modulo 10, assigns
  buckets 0–5 to training, 6–7 to validation, 8–9 to test. These groups are disjoint
  issuers; historical parent/family relationships remain unaudited.
- Train origins through 2006-12-31, validation origins during 2008–2013, test origins
  during 2015–2017. Require each training label to mature before 2008-01-01 and
  validation labels before 2015-01-01. Do not adjust cuts after seeing metrics.
- Use only authors' `qualified=Yes` rows for this initial disclosed population;
  reconstruct prior filing history from all source rows. Report the resulting
  selection and missingness. Require at least 20 positive training issuers and
  10 each for validation and test before model comparison.
- Compare training prevalence, regularized logistic regression (C=0.01, 0.1, 1)
  and a small histogram gradient boosting classifier (100 iterations, seven leaf
  nodes, learning rate 0.05, L2=1). Fit sequentially. Imputation/scaling fit only on
  training. Use no outcome-based resampling or class balancing.
- Select by validation log loss, then evaluate the selected model and prevalence
  baseline once on untouched test. Report ROC AUC, average precision, Brier score,
  log loss, event counts and coverage. Estimate uncertainty by issuer bootstrap.
- A production candidate must improve validation and test Brier/log loss over
  prevalence, with positive held-out average-precision improvement supported by a
  paired issuer bootstrap. Even then, deployment requires independent label and
  identity review, serving-input parity and population validation. Failure of this
  experiment does not justify a different split or a fabricated score.

The initial text corpus link supports bounded GET range retrieval, but the archive
is 13.84 GB. Its download is unnecessary for the metadata baseline. The SEC mirror
inspected separately is 5.28 GB; neither large archive has been downloaded.

## Actual fitted results

Four estimators were fitted and saved under the ignored local directory
`artifacts/disclosure-bankruptcy-20261025-v1`. The checked-in
[evaluation](disclosure-bankruptcy-evaluation.json) and
[provenance](disclosure-bankruptcy-provenance.json) retain their hashes, source
hash, package versions and exact measurements. The original source CSV stays in
`tests/outputs/business-data-followup-20261025/ecl-labels.csv`; it is not bundled.
To reproduce in a fresh output directory with the model/data dependencies:

```sh
LOKY_MAX_CPU_COUNT=1 uv run --frozen --no-sync python -m \
  oxhack2026.models.disclosure_risk \
  tests/outputs/business-data-followup-20261025/ecl-labels.csv \
  artifacts/disclosure-bankruptcy-reproduction
```

Training used 22,702 origins / 3,810 issuers, validation 3,694 / 812, and test
1,741 / 660. Positive issuers were 187, 22 and 13 respectively. Validation chose
histogram gradient boosting over the three logistic candidates and prevalence.

| Held-out test metric | Selected boosting | Training-prevalence baseline |
| --- | ---: | ---: |
| ROC AUC | 0.71706 | 0.50000 |
| Average precision | 0.03864 | 0.00747 |
| Brier loss | 0.00737172 | 0.00741188 |
| Log loss | 0.04301715 | 0.04404852 |

The paired issuer-bootstrap 95% interval for average-precision improvement is
[0.00269, 0.16313]. The wide interval and small absolute probability-loss gains
limit confidence. This is not a 96% accuracy claim. The originally saved Boolean
gate omitted the validation-loss conditions in code; it was corrected after
fitting to match this plan. The already measured validation and test losses
satisfy the full rule. No model was refitted and no holdout/split was changed.

## Input compatibility and release boundary

The SEC adapter `sec_disclosure_timing` uses the training feature calculation,
checks the verified CIK, requires every declared historical page, excludes
amendments/quarterly reports and applies an end-of-day cutoff. Its contract tests
cover missing pagination, mismatched identities and malformed arrays/dates.
These tests establish calculation/schema behavior, not live collection coverage.

The [ECL construction paper](https://aclanthology.org/2023.finnlp-2.2/) explains
that unmatched EDGAR/Compustat records are discarded and asset eligibility affects
labels. This creates selection and serving issues even without using vendor
financial values: a missing matched record can change previous-report cadence;
SEC metadata alone does not establish the authors' asset eligibility. The live
collector now follows all declared history pages up to a limit of eight, validates
root/facts CIKs, and retains the pages before attempting financial facts. Too many,
invalid or unavailable pages leave explicit incomplete history while preserving
independent registry facts. Actual SEC access still needs the operator's contact
user-agent; mocked pagination checks do not establish live availability. Do not
treat schema similarity as verified feature-value parity.

Preliminary event checks against the original SEC-hosted company disclosures
corroborate [Perfumania's 2017-08-26 filing](https://www.sec.gov/Archives/edgar/data/880460/000088046017000028/exhibit991bkfiling.htm),
[Bon-Ton's 2018-02-04 filing](https://www.sec.gov/Archives/edgar/data/878079/000095014218000301/eh1800267_ex9901.htm)
and [Republic Airways' 2016-02-25 filing](https://www.sec.gov/Archives/edgar/data/1159154/000115915416000211/a2ndqtr10q2016.htm).
These are three positive spot checks, not independent blinded review or proof
that negatives are complete. The disclosures also describe continued operations,
reinforcing why bankruptcy cannot be relabeled permanent operating failure.

Release remains disabled. No five-dimension score, Growth/Survival forecast or
Overall index has been manufactured from this experiment.

## Follow-up: actual history parity and later evaluation

The complete 1,235,685,023-byte SEC metadata mirror was downloaded and matched its
published SHA-256. The retained [history comparison](disclosure-bankruptcy-history-parity.json)
found 623 training, 59 validation and 15 test origins whose input features changed
when all annual reports were used. Three of 82,343 eligible origins did not match;
21 ambiguous issuer/dates were excluded from the metadata reconstruction. This
confirms that sharing column names alone did not establish parity.

The [frozen follow-up plan](disclosure-bankruptcy-full-history-plan.md) replaced
the inputs with complete SEC history and reserved 2018–2021 as a later holdout.
Four new estimators were actually fitted, with the same candidate set. The
[new evaluation](disclosure-bankruptcy-full-history-evaluation.json) and
[provenance](disclosure-bankruptcy-full-history-provenance.json) preserve this run.
Boosting again won validation. On 689 held-out issuers / 2,272 origins, including
14 positive issuers, test ROC AUC was 0.60341, AP 0.05796 versus 0.00616 prevalence,
Brier 0.00597933 versus 0.00612849, and log loss 0.03545780 versus 0.03780359.

**The frozen statistical gate failed.** Validation Brier was 0.00592590, slightly
worse than 0.00592554 prevalence; later ROC AUC was also weaker than the earlier
experiment. The AP-improvement bootstrap interval was very wide. Do not change
the gate, retry another holdout or advertise the first run as the final model.
The complete-history calculation now matches the live adapter's conventions,
but actual live field/value reconstruction, population eligibility and useful
financial predictors still need work. The user's permission to extrapolate
permits clearly labeled estimates; it does not turn this failed gate into a pass.

The reusable builder was checked against every fitted follow-up input, target and
partition and reproduced them exactly. To reproduce the follow-up in a fresh
directory, use the pinned label CSV and SEC release file:

```sh
LOKY_MAX_CPU_COUNT=1 uv run --frozen --no-sync python -m \
  oxhack2026.models.disclosure_risk \
  tests/outputs/business-data-followup-20261025/ecl-labels.csv \
  artifacts/disclosure-bankruptcy-full-history-reproduction \
  --sec-history \
  tests/outputs/business-data-followup-20261025/sec-filings-20260930.parquet
```

The command verifies both source hashes before fitting and saves an input manifest.
