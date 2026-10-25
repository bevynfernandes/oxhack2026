# SEC annual financial component experiment, version 1

Frozen before cohort acquisition or fitting, 25 October 2026. This is a new
financial-value experiment; the failed disclosure-timing experiment stays failed.

## Population and acquisition

Select 320 issuers from the 8,619 with an original 10-K filed in 2011 in the
2026-09-30 SEC submissions mirror (SHA256
`f2e3c041cb8eb2cb4b251e11eae25f61b5e18fab0bef34544b912611c0fd219e`).
Sort unique zero-padded CIKs by SHA256(`sec-financial-cohort-v1:` + CIK), take
the first 320. Selection does not use future outcomes or present listing status.
The initial 160-issuer feasibility selection was expanded before acquisition and
fitting to improve issuer counts in the fixed validation buckets. No model was
fitted and no target distribution was inspected to make that change.

Fetch original-accession financial facts from the official public SEC companyfacts
endpoint, at most one new request each second, maximum 16 MiB per response. Keep
404s, failures and missing reports in the coverage audit. Do not replace failed or
closed issuers with current survivors. Retain raw hashes and retrieval times.
The later SEC snapshots reconstruct filing-time values, not contemporaneous
database vintages. Standard consolidated USD US-GAAP concepts only; unsupported
currency, custom tags, missing facts and conflicts remain unavailable.

## Targets and inputs

1. **Two-fiscal-year recognized revenue growth component:** annual revenue at
   the fiscal period ending two calendar years after the origin reporting period,
   within 14 days for fiscal-calendar movement, divided by original positive
   annual revenue. Classification target is growth of at least 10% over the two
   fiscal years. Endpoint uses its original report, not a later comparative value.
   This measures reported revenue expansion conditional on observed follow-up;
   it does not establish operating survival or exactly 24 months from filing.
2. **Next-fiscal-year operating cash flow component:** positive annual operating
   cash flow in the report ending one calendar year after the origin period,
   within 14 days. Zero is not positive. This is a financial-health component,
   not unrestricted runway or a complete resilience target.

Inputs available in the origin filing: log positive revenue and assets, operating
cash flow/revenue, net income/revenue, gross profit/revenue, liabilities/assets,
cash/assets, current assets/current liabilities and filing lag. Ratios require
positive denominators. Do not winsorize by inspecting the holdout. Median
imputation and standardization are fitted on training rows only; explicit missing
indicators are retained. No source outcome/status, future financials or CIK feature.

## Partitions, models and evaluation

Issuer bucket is SHA256(CIK) first byte modulo 10. Train buckets 0-5 with filing
origins 2011-2014; validation buckets 6-7 with origins 2018-2019; test buckets 8-9
with origins 2023-2024. Target report must be filed before 2018-01-01 for training,
before 2023-01-01 for validation, and by 2026-09-30 for test. Unobserved endpoints
are censored, not failures. Disclose endpoint observation bias and repeat-row
clustering. Issuer separation does not establish corporate-family separation.

Fit logistic regression C=0.1 and C=1, depth-3 decision tree (minimum leaf 20), and
histogram gradient boosting (100 iterations, 7 leaves, learning rate 0.05, L2=1),
seed 20261025, serial local CPU. Candidate selection uses validation log loss;
test is evaluated once after selection. Compare with training prevalence using
ROC AUC, average precision, Brier and log loss, with 200 issuer-bootstrap paired
log-loss differences. Require at least 10 independent issuers and both classes
in each partition to fit; otherwise report insufficient data without changing
selection or cuts. This minimum enables an exploratory fit, not proof of power.

A component passes its statistical gate only if validation and test Brier and log
loss beat prevalence and the 95% issuer-bootstrap interval for test log-loss
improvement is wholly positive. Coverage, sample size, issuer-family review,
numeric extraction review and population transfer remain separate release gates.
These components cannot be represented as five validated business dimensions,
private-startup success probabilities or the complete Overall index.
