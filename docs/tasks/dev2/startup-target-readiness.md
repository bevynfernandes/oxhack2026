# Dev 2 target and data decision: #46

Decision date: 2026-10-24. Training remains on hold. This is a target proposal and
review decision, not an approved labelled dataset or model release. The product
still aims to predict startup outlook; an evidence report is an interim checkpoint.

## Independent readiness review

Reviewed Bevyn's #48 manifest at `b7cc31e709e58dc51aaa3b8f9458e3e3e2e3c4a7`.
Independently streamed the exact SEC archive already shared through the private
`data-startup-audit-20261024-v1` release. Counts agree: 5,542 primary non-fund
filings, 4,886 CIKs, 1,171 amendments, 4,435 declined revenue disclosures and
576 no-revenue reports. This validates archive statistics, not company matches.
Other cohort/attention counts are reviewed producer results; their retained raw
join captures were not independently rerun by Dev 2.

Accept the **failed training gate for all five groups**. The 59 discovery rows
have no approved endpoint labels or historical domain/family mappings. Neither
current status nor present-day taxonomy is a historical outcome. One unmatching
SEC quarter cannot establish absence of financing; 2024 filings cannot be inputs
at a 2022 origin. HN link counts and domain ranks do not establish retention.
No candidate fit, calibration or success probability is justified by this audit.

## Outcome definitions to settle before labels

Keep three endpoint forecasts distinct from the five feature specialists. A group
is a view of predictors; it is not automatically a separate definition of success.
The following proposed targets require cohort coverage and user/model review
before freezing a new label schema. Existing v1 IDs keep their exact meanings.

| Lane | Proposed observable question | Required evidence and unresolved decision |
| --- | --- | --- |
| Growth, 24 months | Is the business still operating with increased comparable commercial activity at the endpoint? | Preselect revenue or active paying customers for the cohort before examining outcomes. Compare like-for-like trailing twelve-month periods at origin and endpoint. Freeze the growth threshold and treatment of inflation/currency; downloads, signups and attention are predictors only. Existing operating/growth v1 is usable only under its exact prior definition. |
| Survival, 24 months | Does the business continue operating through the horizon without a verified permanent cessation? | Require dated operating evidence at the endpoint and adjudicated company continuity. Acquisition/legal dissolution alone is not failure if the business continues. A permanent closure inside the horizon is negative; a website going silent or a current directory status is unknown. This needs a new target ID/schema; it is not the financing/acquisition v1 target. |
| Financial health, 12 months | Does the operating business have evidence of financial resilience at the endpoint? | Candidate definition: nonnegative trailing operating cash flow, or verified unrestricted cash covering a predeclared runway threshold using comparable recent net burn. Freeze the threshold, accounting periods and applicability before labelling. Cash-flow positivity alone is a narrower existing endpoint, not a replacement for broad financial health. Funding amount is not cash or runway. Current public coverage fails this target. |

An OR-based financial target is positive only with a verified qualifying condition;
a negative needs every applicable condition observed and false. Missing components
remain unknown. Stage treatment must be explicit; venture investment and temporary
negative cash flow alone cannot label a company a failure. If comparable financial
data cannot be obtained, defer this lane rather than secretly changing its target
to funding announcements or presenting a two-lane score as balanced three-lane health.

## Label adjudication rules

- Define the cohort and decision origins before looking at outcome values. Keep
  companies that subsequently failed, changed name or were acquired.
- Use `(decision_at, horizon_end]`, exact calendar anniversaries, and full elapsed
  follow-up for both binary classes. Keep censored, unknown and conflicting labels
  separate. Label availability cannot precede the evidence supporting the decision.
- Month-precision closure can establish that an event falls within a horizon only
  if its entire date interval is contained. Do not invent a shutdown day. Datree's
  July 2023 statement is a lead outside the selected cohort; do not append it as a
  handpicked negative. Verify its company identity, source vintage and continuity.
- A retrospective PostHog statement is not automatically a historical financial
  panel or proof of pre-origin availability. Predictors and future label evidence
  have different cutoffs; both retain actual capture and first-availability times.
- Declare acquisition/merger continuity and company-family grouping before splits.
  No current family backfill or duplicate related companies across held-out tests.

## Local models and numerical output

After audited labels and feature coverage pass, propose training-only prevalence
and regularized logistic regression with fold-local preprocessing on local CPU.
A small CatBoost challenger is conditional on sample size and mixed predictors.
No fitting now. Freeze training/validation/test origins, label maturity at fit,
feature schemas, endpoint versions and candidate selection before holdout access.
Report class counts, missingness and comparable held-out calibration/loss/coverage.

The overall utility mapping is still unfrozen. Equal lane weights are a proposal,
not a calibrated probability or proof of balanced performance. Any later learned
combiner requires out-of-fold predictions. Until approved artifacts exist, the
merged `StartupOutlook` contract (#49) returns null predictions and null overall
outlook with reasons. No score, bubble badge or simulated backtest is permitted.

## Mixed-vintage report boundary agreed with backend

The embedded outlook may pin the new immutable research inventory as its
`source_snapshot_id`; keep the saved C1 publication as separate parent lineage.
That inventory must resolve every saved/fresh observation and evidence reference
to the confirmed company, original source/capture and measurement/availability/
collection times. Evaluate saved metric freshness at the report cutoff using
shared `company_metric_state`. Never rewrite saved publications or freshen their
measurement dates. Preserve synthetic provenance and public/review restrictions.
Fresh attention uses its own versioned inventory, not a renamed C1 adoption family.

Bevyn owns job state and provider completeness; Ivan renders shared model fields.
The current known-company research slice is a checkpoint. Unknown-company identity
resolution remains explicitly pending before the full name/domain vision is done.
