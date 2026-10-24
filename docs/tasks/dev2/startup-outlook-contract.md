# Local startup model payload

Implements the Dev 2 report boundary in [#46](https://github.com/bevynfernandes/oxhack2026/issues/46).
Bevyn owns research jobs/report storage and embeds `StartupOutlook` from
`oxhack2026.models.startup_outlook`. Ivan renders the backend payload. Existing
company source/assessment v1 contracts are unchanged.

The user-approved [prediction workspace](prediction-workspace-alignment.md) adds
three `forecasts` above the five driver groups: Growth/Survival at 24 calendar
months and Financial Health at 12. New builders include all three with null
predictions, `pending_label_policy` and `model_not_trained`. Their ordered reasons
are `target_definition_pending` and `model_not_trained`. These are product outcomes,
not aliases for existing v1 targets or approved labels. Detailed endpoint criteria
and trained serving remain gated. Older reports omit `forecasts`; validation and
serialization preserve that absence and their original bytes. The generated API
field is optional for compatibility, not permission to drop a new report's lanes.

Call `build_untrained_outlook(snapshot, company_id, metric_groups, policy_version)`
with a validated source snapshot and an explicit mapping from metric-definition ID
to group ID. Financing must not be guessed to mean industry outlook. Unmapped
observation IDs remain in `unassigned_metric_observation_ids` for audit/review.
The report retains the exact source ID, cutoff and synthetic flag.

The five group IDs are `adoption_retention`, `attention_sentiment`,
`financial_health`, `industry_competition` and `team_execution`. Each section has:

- `data_status`: `available` when any assigned metric is fresh and supported by
  verified public evidence; `not_applicable` when all assigned metrics explicitly
  are inapplicable; otherwise `insufficient_data`. Available is observation
  coverage, not sufficient features, cohort coverage or training readiness.
- `metric_observation_ids`, `usable_metric_observation_ids` and `evidence_ids`:
  exact source references. Only usable observations supply public model evidence.
  Unknown, stale, conflicting, restricted and unverified inputs retain reasons.
- `model_status: model_not_trained`, `prediction: null` and `reason_codes`:
  no fit, inference call, calibrated probability or backtest is implied.

`overall_outlook` is null with `overall_reason_codes: [model_not_trained]`.
`inference_runtime: local_cpu` specifies the intended deployment, not an executed
model. This version rejects numbers and validated-model claims. A future serving
version must validate approved artifacts, target/features/splits and evaluation
metadata before permitting numerical output. It must not reinterpret the old v1
cash-flow/financing targets as the new balanced target.

The schema is exported with the existing C2 export command. Saved tests cover
source identity, five unique sections, independent statuses, real zero, missing
financials, public/review/freshness gates, explicit unassigned metrics, deterministic
ordering and rejection of injected scores or inconsistent references. No training
runs or network calls are needed to produce the payload.
