# Company probability research metrics

`evaluation.company_metrics.evaluate_company_probabilities` evaluates one frozen
experimental endpoint at an explicit UTC label-knowledge cutoff. It reuses the
shared mature-label selector, joins exact company/origin keys and rejects duplicate
selected vintages. Other endpoints are never pooled. Chronological fitting,
historical inclusion, source verification and final-holdout selection remain
separate experiment requirements; the metric input cannot establish them.

The report includes eligible/excluded label counts, predictions without usable
truth, eligible labels without predictions, positive counts and matched company,
family and origin counts. Missing follow-up never becomes false. Counts expose
abstention and repeated-company dependence; they are not confidence intervals.
All metrics use the same matched rows:

- Brier score: mean squared probability error.
- Natural-log loss: probabilities are clipped only for this calculation to
  `[1e-15, 1 - 1e-15]`. Invalid/out-of-range input probabilities are rejected.
- ROC AUC: positive-negative ordering with half credit for ties, using a sorted
  pass rather than enumerating every pair. Single-class AUC is undefined.
- Calibration: ten fixed equal-width bins, lower boundary inclusive, upper
  exclusive except the final bin includes one. Empty bins retain null averages.

No matched rows means null scores, not zero error. Reliability tables are
descriptive: small bins do not establish calibrated probabilities. Compare
experiments on the same matched rows and report any coverage differences.

These frozen dataclasses are internal research inputs/results, not an additional
serving contract or persisted prediction format. The public company assessment
schema still constrains probability to null. No real labelled historical cohort,
empirical performance or model-release eligibility is claimed by these tests.

Validation: fourteen saved unit cases cover hand-computed scores, ties and reverse
ordering, fixed bins, boundary probabilities, immature/unknown/future-available
truth, abstention, endpoint/origin isolation, duplicate vintages and invalid input.
