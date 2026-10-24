# Final demo talking points — work in progress

This file records verified claims and remaining work. It is not a completion sign-off.

## What we should demonstrate

1. Search by company name or website from the main search bar.
2. Resolve the exact company; show ambiguity instead of guessing a domain.
3. Retrieve available public evidence and open its actual source excerpts.
4. Explain the five business views and distinguish measurements, company claims,
   missing information and predictions.
5. Show Growth, Survival and Overall outlook only under their explicit supported
   definitions, with model/data versions and measured validation.

## Claims currently supported

- The backend retains source artifacts, hashes and attributable evidence.
- Main includes Gemini-assisted source mapping with independent quote validation.
  A real Qdrant mapping audit was partial; provider failures do not justify invented
  measurements or successful mapping claims. Deterministic mapping is now the
  default; Gemini interpretation remains an explicit opt-in.
- Existing local ML models were actually fitted, but their targets are narrow
  proxies. They do not establish startup success or survival prediction.
- A separate business-event experiment fitted three regularized logistic models
  and one small boosted-tree classifier using the public ECL bankruptcy dates.
  Validation selected boosting. On 660 held-out issuers it achieved ROC AUC 0.717
  and average precision 0.0386 versus 0.00747 for prevalence. There were only 13
  positive test issuers; probability-loss improvement was small. These results
  concern next-year recorded Chapter 7/11 filings among selected public filers,
  not private-startup growth, permanent closure, or complete financial health.
  The experiment remains excluded from live scores pending source/history parity
  and independent label/population review. See the
  [experiment and reproducible results](docs/product/disclosure-bankruptcy-experiment.md).
- Public websites, npm, HN and a Common Crawl domain index were accessible in
  retained probes. These checks do not prove coverage for nearly every business.
- The main search now accepts names and URLs. A bundled, attributed Majestic
  Million directory supplies name candidates without a live search provider.
  Multiple matches require a choice; aliases and missing names require a URL.
- A real ElevenLabs browser run completed search, candidate choice, website
  preview, explicit confirmation, collection and report rendering in about 43
  seconds. It retained 306 excerpts, reported partial sources, had no browser
  exceptions and no horizontal overflow at 390px. This run used deterministic
  mapping because the separate Gemini audit did not complete reliably.
- Follow-up browser checks verified candidate rows at 1440px, 390px and 320px
  without overlap/overflow, and reached a real PostHog preview from URL input.
  Two focused fixture-browser checks also passed for evidence accessibility and
  dossier layout across laptop/mobile sizes.
- Top cards now show Growth, Survival and Overall. Financial Health remains one
  of the five dimensions. Overall is the requested dimension index, not another
  outcome probability. Unsupported scores remain unavailable.

## Work still required before a final-product claim

- Establish the historical features and later business outcomes needed to train
  and backtest the requested dimension/outcome models.
- Verify population coverage and model-input compatibility beyond the named
  examples. The eight directory queries and one new full browser run do not
  establish near-universal coverage.
- Complete independent review of extracted subjects, dates and measurements;
  source quotations establish provenance, not factual truth or complete coverage.

## Retained demo evidence

`tests/outputs/final-product-20261024/live-browser-result.json` records the live
run and exact identity/job/report IDs. Screenshots beside it show the candidate
list, identity preview and desktop/mobile report. The matching durable backend
store is `tests/outputs/final-product-20261024/browser-live`.

To read that report with the local worker disabled:

```sh
SIGNALSHIFT_RESEARCH_ROOT=tests/outputs/final-product-20261024/browser-live \
SIGNALSHIFT_RESEARCH_ENABLED=0 \
uv run --no-sync uvicorn oxhack2026.api.company_runtime:create_company_app --factory
```

Use the normal frontend development server and open
`/research/v2/reports/b0ca044f57f743b7baba63b023c4b441`.
This local report store is ignored by Git; do not expect it on another checkout.

Do not demonstrate an SDK-download percentile as a business success score. Do not
claim universal private-company financial data, validated probabilities, or a
completed backtest unless the corresponding retained evidence exists.

Source selection and current blockers: [free-source decisions](docs/product/free-source-decisions.md).
