# UI alignment with the startup research roadmap

- Authority: Daniyal's [issue #46](https://github.com/bevynfernandes/oxhack2026/issues/46),
  [delivery plan](../dev2/startup-prediction-reset.md), model payload PR #49 and
  Bevyn's research-job proposal in PR #48. Reviewed 2026-10-24.
- Keep the company-first layout, warm neutral surfaces, restrained teal,
  accessible disclosures and reduced-motion-aware transitions from #45.

| Roadmap requirement | Current UI / next integration |
| --- | --- |
| Choose a Software/SaaS company by name or domain | Homepage searches saved names/sectors and exact normalized website domains. Each result shows its saved domain. Unknown domains cannot select a similar company. |
| Distinguish saved analysis from fresh research | Explicit View saved analysis action and saved profile label. Search does not collect data. |
| Confirm identity before research | Next job action shows exact company/domain and requests explicit confirmation. POST only after confirmation, never on typing or page load. |
| Actual job state | Await additive generated API types. Render queued/running/partial/completed/failed with per-source states and dates. No synthetic percentage, timer or fabricated completion. |
| Five specialist sections | New research report order: adoption/retention, attention/sentiment, financial health, industry/competition, team/execution. Render Daniyal's shared payload; do not map v1 metric families in the browser. |
| Independent data and model readiness | PR #49 has available/insufficient_data/not_applicable, separate model_not_trained and null prediction. Available means usable observations, not enough training data. The earlier API proposal's partial data enum must not be invented by UI. |
| Overall outlook | Display unavailable with backend reasons while overall_outlook is null. No score, weights, progress gauge or success/failure badge. |
| Metric and evidence references | Use the report's public resolved measurements and source links. Preserve missing/stale/restricted states and original dates. References alone must not produce fabricated facts. |
| Stable saved reports | Existing v1 links and all three outcome definitions remain unchanged. New growth/survival/financial-health endpoints are not aliases for old cash-flow/financing outcomes. |
| Model/data provenance | Report details show backend versions, source date, collection date and limitations. Planned local CPU execution does not mean a model ran. |

## Intended report layout

1. Company name, confirmed domain, research date and saved-context date.
2. Real job status or partial-results notice, with source-specific failures.
3. Overall outlook and explicit unavailable reason.
4. Five readable specialist sections: data status, model status, sourced metrics,
   limitations and expandable evidence. Use textual status, not color alone.
5. Sources and version details. Comparison remains secondary.

## Integration boundary

- Agreed to Bevyn's known-company first slice in #46. Use POST research-jobs,
  GET research-jobs/{id} and GET research-reports/{id} once actually implemented.
- Consume generated OpenAPI types embedding StartupOutlook from Dev 2. Do not
  duplicate Python model policy, create client-side forecasts or invent endpoints.
- Unknown identity, missing worker, partial provider results, no useful result,
  refresh/restart and exact saved links need browser acceptance after integration.
- Current milestone adds domain search, explicit saved-report labels and a
  methodology explanation. Fresh research and a rendered five-section report
  remain pending the additive API; this document does not claim they work.
