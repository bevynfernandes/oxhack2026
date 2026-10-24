# Company prevalence baseline

`models.company_baselines.prevalence_company_forecasts` is the training-only
prevalence comparator required before testing a learned company classifier.
It reuses outcome-specific mature-label selection, availability purging and
explicit held-out-family exclusions. Every requested origin must follow or equal
the fit cutoff. Duplicate requests fail; sorted inputs reproduce the same result.

The result retains its training selection and exclusion counts. Its constant
probability is the eligible training positive fraction; neither test prevalence,
future labels nor another outcome enters the fit. Empty training fails explicitly
instead of inventing a 50% prior. One-class training retains zero/one for honest
proper scoring. Use the shared company metrics on identical evaluation rows.

These are internal experimental predictions, not public assessment artifacts.
Chronological feature/model selection, source evidence and historical cohort/family
verification remain prerequisites. Current public observations and unresolved YC
directory follow-ups do not supply training truth. No empirical success-prediction
accuracy or public probability eligibility is claimed.

Validation: seven baseline cases and fourteen metric cases pass, including future
test-label changes, held-out families, delayed support, endpoint separation,
empty/one-class training, exact fit/request boundaries and duplicate requests.
