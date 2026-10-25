# Bankruptcy model with complete SEC history: frozen follow-up plan

25 October 2026. Written before fitting this follow-up or evaluating its later
holdout. The first experiment remains recorded without alteration. The goal is
to repair a measured training/serving history mismatch, not optimize the original
test results. This remains one financial-risk component of the broader product.

## Inputs and target

Keep the first experiment's exact event definition, eligible ECL origins and
issuer normalization. Use its pinned public label CSV, SHA-256
`bde2184a88e3130e1dec7e06b2e04072c23adced0ef36f323e3bdd600a5d1608`.
Replace all five timing features with values computed from the complete annual
filing history in Ian D. Gow's CC BY 4.0
[2026-09-30 SEC submissions release](https://github.com/iangow/sec_submissions_data/releases/tag/2026-09-30),
`filings.parquet` SHA-256
`f2e3c041cb8eb2cb4b251e11eae25f61b5e18fab0bef34544b912611c0fd219e`.
Both full-file checksums were verified. Do not use current company/ticker tables,
future annual reports or bankruptcy information as predictors.

Use forms normalized to 10K, 10K405, 10KSB, 10KSB40 and 10KT. Exclude amendments,
invalid periods, ambiguous same-issuer filing dates and origins not matched on
CIK, filing date and period end. Keep missing prior history explicit. The feature
function is shared with the SEC live metadata adapter. This establishes the same
computation and source fields; it does not prove live availability or original
historical-vintage accuracy.

## Frozen comparison

- Keep SHA-256(CIK) first-byte modulo-ten buckets: 0–5 training, 6–7 validation,
  8–9 test. Historical family continuity is still unaudited; do not claim otherwise.
- Keep training through 2006 and validation 2008–2013, with previous label-maturity
  restrictions. Use test origins in **2018–2021**. The earlier 2015–2017 test is
  now diagnostic history and cannot be called an untouched test for this version.
- The new test years have not been used for prediction metrics. Only dataset
  feasibility counts have been inspected. No test-year or issuer-bucket changes
  are permitted after this plan is frozen.
- Compare the same three logistic models (C=0.01, 0.1, 1) and small histogram
  boosting model with identical preprocessing and parameters to the first run.
  Run serially, fit preprocessing only on training, and compare against training
  prevalence. No new candidates or post-hoc calibration tuning.
- Select by validation log loss, then evaluate the winner and prevalence once on
  the later test. Retain ROC AUC, AP, Brier, log loss, independent event counts,
  coverage and a paired issuer-bootstrap interval for AP improvement.
- Require at least 20 positive training issuers and 10 each in validation/test.
  Apply the first plan's complete validation/test statistical gate. Preserve a
  failed result; do not search another split to rescue it.

## Extrapolation and release

The user permits extrapolation with the available public sources. Any resulting
estimate must identify the population transfer and uncertainty. Permission to
extrapolate does not create missing filing inputs or establish private-startup
calibration. This experiment cannot establish paid retention, commercial growth,
team quality or all five business dimensions. Chapter 11 remains a legal distress
event, not permanent operating failure.

Continue to withhold automatic production eligibility pending asset/population
eligibility, independent event/family review and live feature reconstruction.
The current corrected SEC snapshot is retrospective; acceptance/date corrections
are not a substitute for checking historical original disclosures.
