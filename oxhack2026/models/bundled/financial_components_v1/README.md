# Experimental annual operating-cash-flow component

`positive_operating_cash_flow_1fy.model.json` contains actual fitted regularized
logistic regression weights, not rules or synthetic training. It includes the
training-only median imputer, missingness indicators, scaler and class-1 weights.
No executable pickle is needed for inference.

The target is positive operating cash flow in the next fiscal-year report,
conditional on an observed original follow-up. The training population is a fixed
historical SEC reporting-issuer sample. It does not supply paid retention,
operating survival, unrestricted runway, private-startup validation or an Overall
score. `eligible_for_serving` remains false while source/scope, identity and
population-transfer checks are unfinished.

The fixed model comparison selected logistic regression with C=0.1 using validation
log loss. On 49 test rows from 25 issuers, ROC AUC was 0.869 and Brier 0.134 versus
prevalence Brier 0.213. The 95% issuer-bootstrap log-loss improvement interval was
[0.0024, 0.3692]; this is a small exploratory sample. Revenue-growth models from the
same experiment failed their gate and are not packaged as usable forecasts.

Shared input preparation is `annual_financial_features` in
`oxhack2026.features.sec_financial_panel`. Portable inference is
`AnnualCashFlowModel` / `predict_annual_cash_flow` in
`oxhack2026.models.financial_inference`. The caller must supply original-accession
SEC observations for a verified CIK, through the proper availability cutoff.
The model must not be applied directly to website text, inferred ARR or SDK data.

For reproduction, the repository retains the cohort CIKs and source hashes in
`docs/product/sec-financial-cohort-v1.json` and `sec-financial-acquisition.json`,
the frozen design in `sec-financial-model-plan.md`, full validation/test results
in `sec-cash-flow-evaluation.json`, and numeric inference parity in
`sec-cash-flow-portable-parity.json`.

Acquire the pinned [SEC submissions metadata mirror](https://github.com/iangow/sec_submissions_data/releases/download/2026-09-30/filings.parquet)
and public [SEC companyfacts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
for the frozen cohort. Retain source failures; do not replace them with survivors.
For each verified issuer, select original 10-K metadata and rename accessionNumber,
filingDate and reportDate to accession_number, filing_date and period_end.
Call `sec_annual_financials(payload, filings, cik, date(2026, 9, 30))`, concatenate
the results, then call `annual_financial_component_panel` for each target and
`train_financial_component(panel, new_output_directory, source_hashes)`.
`uv.lock` pins the actual training dependencies. This uses local scikit-learn
classifiers; an LLM is not involved in financial prediction.
