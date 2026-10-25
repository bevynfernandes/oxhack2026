# D2-05a: CQR calculations and empirical interval gates

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


- Owner: Dev 2; branch `dev/models-calibration`.
- Paths: `models/calibrate.py`, saved model calibration tests, Dev 2 docs.
- Dependencies: existing NumPy model extra and C2 model references; no additions.
- Inputs: chronologically held-out log-target quantiles/actuals, frozen model
  digest, and evaluation evidence on a common preregistered candidate universe.
- Outputs: immutable scalar calibration pair and experimental count bands.

Quantiles are sorted with crossing-rate diagnostics. The correction uses
nonnegative CQR scores and the exact ceil(0.8*(n+1)) order statistic via linear
partition, never interpolated quantiles or a clamped unsupported rank. Application
checks the original model ID **and artifact digest**, widens on log-target scale,
then inverse-transforms and clips at zero. A refitted model needs new calibration.
These interval endpoints do not claim calibrated p10/p90 semantics.

Serving gates require 500 calibration predictions, 26 origins, 30 organizations,
75%-90% final overall coverage, no supported major subgroup below 70%, and an
interval score no worse than its preregistered calibrated baseline. Supported
subgroups have at least 100 rows and 13 origins. Invalid evidence fails validation;
failed gates return explicit reasons and leave bands experimental.

The pure calculations cannot infer collection dates or split provenance from
arrays. Pipeline callers must use the frozen chronological protocol, prove label
availability, and persist model/calibrator pairing before publishing a band.
No real model, calibration data, empirical coverage, or serving approval is
claimed. Synthetic formula/gate tests are independent of those evidence gates.
