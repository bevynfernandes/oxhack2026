# Company-label calendar and maturity checkpoint

`features.company_outcomes` defines the three IDs agreed in #19 and calculates
their twelve-/twenty-four-calendar-month anniversaries. Company cutoffs accept
any aware UTC instant; Monday origins remain specific to download forecasting.
Leap-day anniversaries clamp to February 28.

`models.company_contracts.CompanyOutcomeLabel` stores truth separately from
assessments, using `company-labels-v1`. It binds company/family/source-vintage
identity, exact horizon, evaluation time, observed/immature/unobserved/conflicting
state and nullable strict Boolean truth. Both positive and negative labels need
complete follow-up and source evidence. Negatives also need their precise reason;
undefined labels need an exclusion reason and cannot contain false/zero truth.

The exported schema is additive to download C2. Python validation also checks
cross-field temporal rules that JSON Schema alone cannot establish. Saved tests
cover all outcome horizons, leap years, arbitrary weekdays, exact maturity,
future/early availability, strict Boolean parsing and missing/conflicting facts.

This implements label interchange invariants, not source-to-truth adjudication,
a trained classifier or probability serving. Commercial target operationalization
remains provisional under the shared coordination review. Source-owned company
metrics/events and supporting facts must be validated before generating real
labels. The current surviving npm catalogue is not a company-failure cohort.

Validation on integrated main: Ruff and mypy pass; 407 unit tests pass, with six
service/filesystem integrations intentionally excluded by the default test target.
Logs remain under `tests/outputs/dev2-company-labels-20261024/`.
