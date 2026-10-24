# Company metric features

`features.company.company_feature_frame` consumes one exact validated C1 snapshot.
It produces a deterministic long-form Polars frame with one company/metric row,
Float64 predictors, explicit usability states, units/scope, measurement and source
knowledge times, and source/cohort/mode/synthetic/feature-version metadata.

Verified public fresh measurements alone become numeric predictors. Missing,
conflicting, inapplicable, stale, restricted and unverified measurements stay null
with distinct states. Overflow/underflow stays null rather than infinity or false
zero. Boolean predictors use 0/1. Float64 is a model projection; C1 preserves exact
financial decimals. No imputation, scaling or other learned preprocessing is fitted.

`features.company_policy` shares public support and frozen freshness rules with
the assessment builder. Existing real assessment records reproduce unchanged.
Future labels, company identifiers as predictors, family assumptions and historical
cohort eligibility are not inferred. Experiments must resolve historical inclusion
and dated families separately, freeze metric definitions/units, and fit any learned
preprocessing on training folds only. Current survivors do not validate prediction.

Real source `company-vector-20261024-v1` yields seven usable metrics, six missing
commercial metrics and one stale financing metric. A local Parquet projection and
checks are retained under `tests/outputs/dev2-company-features-20261024/`.
This is a callable research input, not an additional source or serving contract.

Validation: twelve feature cases plus sixteen existing builder cases pass, covering
zero, missingness/applicability/conflict, access/review, frozen freshness boundaries,
Boolean predictors, numeric range and deterministic ordering.
