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

- The previously fitted FinEntity TF-IDF/logistic sentiment model now consumes
  exact company-name spans in retained, exact-domain HN story titles. Its original
  weights are unchanged; portable inference agrees with scikit-learn to floating
  point precision. A fresh ElevenLabs HN probe retrieved four titles and only one
  explicitly named ElevenLabs; that title produced **48.3/100 text valence**.
  The report shows the one-title sample, exact quotation, canonical story link,
  formula, source/model provenance and transfer warning. This is unvalidated
  transfer from financial news, not representative public opinion or a business
  forecast. Original held-out negative recall was only 1/11; do not demonstrate
  this component as accurate risk screening. Missing entity spans abstain.
  The source-replay report (fresh HN, retained other-source checkpoints) is
  `/research/v2/reports/d8e831f150f7448880c0a2c635bb7562`. Desktop/mobile checks
  passed; tracked sentiment audits under `docs/product` record the exact scope.

- ElevenLabs now follows its linked official SDK documentation before collecting
  npm inputs. A fresh run on the normal `localhost:5173` / API `8000` setup passed
  in 61 seconds and displayed **SDK component trained** with an experimental
  **SDK-demand index of 31.3/100**. The fitted Ridge model consumed one package's
  complete adjacent 30-day windows; multiple packages are evaluated separately,
  selecting the largest eligible current SDK rather than adding their counts.
  This forecasts technical demand, not customers, retention or startup success.
  Provider 403/429 responses remain explicit, and the fresh report rendered with
  no browser errors or mobile horizontal overflow. Local report:
  `/research/v2/reports/f8a93102a81a4d5e8746921de3c84bce`.
  See `docs/product/elevenlabs-sdk-browser-audit.json` and
  `docs/product/elevenlabs-sdk-model-audit.json`. Earlier immutable reports keep
  their earlier missing-input results; use **Refresh research** for a fresh run.

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
- A follow-up fixed a measured SEC-history mismatch, fitted four further models
  and tested on later 2018–2021 origins. ROC AUC fell to 0.603 on 689 issuers with
  14 positive cases. The frozen validation-loss gate failed. Retain that result;
  do not present the earlier 0.717 figure as the final model's performance.
  Estimates may be extrapolated under the user's chosen compromise, with their
  assumptions and uncertainty shown. Missing company facts stay missing.
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
- Latest main's editorial theme was merged (`a409428`). Name candidates still fit
  at 1440/390/320px and the live PostHog URL preview works. A 375x667 card-clipping
  regression was corrected by sizing and shortening the Overall explanation.
  Both focused dossier/accessibility browser checks pass, with 67 frontend unit
  tests and typechecking also passing after the merge. Retained evidence is under
  `tests/outputs/theme-merge-business-models-20261025` and
  `tests/outputs/theme-model-merge-fixed-20261025`.

## Work still required before a final-product claim

The latest complete Cloudflare run passed in 32 seconds: primary name search,
candidate selection, website confirmation, live source collection, and the
trained annual cash-flow component displayed at 95.3%. The probability concerns
positive operating cash flow next fiscal year, conditional on a future report;
it is not a startup survival probability or a complete financial-health score.
Desktop and 390px mobile passed without browser exceptions or horizontal overflow.
See `docs/product/sec-full-search-browser-audit.json`; the retained local report is
`/research/v2/reports/d82de792a93a4dc9ac0c1d3b85af8462`.

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
uv run --env-file .env --no-sync uvicorn \
  oxhack2026.api.company_runtime:create_company_app --factory
```

Use the normal frontend development server and open
`/research/v2/reports/b0ca044f57f743b7baba63b023c4b441`.
This local report store is ignored by Git; do not expect it on another checkout.
The local SEC contact is in the ignored `.env`; `uv run --env-file .env` loads it
without committing it or putting it in the command text. A five-issuer official
SEC financial-data pilot succeeded, including historical bankrupt issuers.
The production Fetcher also retained real Cloudflare and Salesforce financial
responses. The shared annual financial parser now reconstructs nine measures
from original accessions: 747 metric rows across 83 annual filings in the five
pilot issuers. Missing and conflicting values remain explicit; this includes
pre-XBRL reports and unsupported custom concepts. See the
[extraction audit](docs/product/sec-annual-financial-pilot-audit.json).
These five source-access stress tests are not a training or evaluation cohort.
A separate fixed 320-issuer historical cohort produced 290 official financial
responses. Eight classifiers were fitted across two annual financial targets.
Regularized logistic regression for next-year positive operating cash flow passed
the statistical gate: test ROC AUC 0.869, Brier 0.134 versus baseline 0.213, on
49 rows from 25 held-out issuers. This remains an exploratory reporting-company
component, conditional on observed follow-up; it is not survival or unrestricted
runway. The two-fiscal-year revenue-growth candidates lost to the prevalence
baseline and were rejected. See the [cash-flow evaluation](docs/product/sec-cash-flow-evaluation.json)
and [growth evaluation](docs/product/sec-revenue-growth-evaluation.json).
The cash-flow model's fitted JSON weights are bundled in
`oxhack2026/models/bundled/financial_components_v1`; portable local inference
matches the original pipeline across all 4,462 panel rows with maximum absolute
probability difference 2.22e-16. This proves weight/transform parity, not complete
production identity mapping or approval to score private companies.

The live SEC collector now retains normalized original financial observations
with exact JSON locations and can run the cash-flow component for reviewed issuer
mappings with recent usable revenue, cash flow and assets. The Cloudflare probe
retrieved four real captures and nine annual financial observations, published an
immutable report, and read it back with its model/evaluation hashes intact.
The report shows a **research estimate** of next-fiscal-year positive operating
cash flow. This is not a complete financial-health score. The packaged catalog
contains the reviewed Cloudflare domain/CIK link; unfamiliar companies do not
inherit that mapping. All nine values matched an independent inline-XBRL parse
of the original annual filing, including sign, scale, dates, currency and entity.

Retained report: `/research/v2/reports/3558851a874b4be3a59527e92c170259`.
Desktop/mobile checks passed with four supporting source documents, no browser
exceptions, no horizontal overflow and no accessibility violations in the new
component. See the [live report audit](docs/product/sec-live-cash-flow-report-audit.json),
[numeric review](docs/product/sec-original-filing-numeric-review.json) and
[browser audit](docs/product/sec-cash-flow-browser-audit.json).

Do not demonstrate an SDK-download percentile as a business success score. Do not
claim universal private-company financial data, validated probabilities, or a
completed backtest unless the corresponding retained evidence exists.

Source selection and current blockers: [free-source decisions](docs/product/free-source-decisions.md).
