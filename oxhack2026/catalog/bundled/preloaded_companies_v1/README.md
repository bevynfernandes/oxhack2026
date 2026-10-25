# Dated Qdrant and Weaviate input bundle

This package contains real, curated public inputs for the two saved examples.
It works in a fresh checkout and in the installed wheel, without search, provider
credentials, a research worker, or ignored local datasets. It contains no trained
model predictions. The normal company repository verifies content-addressed input
artifacts, and the existing portable models run on profile reads.

- Source: `company-preloaded-20261025-v1`.
- Assessment: `company-assessments-preloaded-20261025-v1`.
- Two companies, 11 definitions, 22 observations, two original funding events,
  and 25 public evidence records. Three private financial/customer measures per
  company remain explicitly missing.
- SDK counts and stable release measurements retain the original 24 October 2026
  captures and windows. Additional company and HN inputs were captured on
  25 October 2026. Dates are frozen, not refreshed on each page request.

The source index points to a digest-verified manifest and normalized snapshot;
the assessment index points to the existing deterministic evidence builder's
publication. These narratives are source summaries with null outcome probabilities,
not stored AI outputs. The manifest and every attached artifact have SHA-256 and
byte-size checks. No restricted attachments are distributed.

## Input sources and meaning

| Input | Qdrant | Weaviate | Interpretation |
| --- | --- | --- | --- |
| Company and offering | [About](https://qdrant.tech/about-us/), [pricing](https://qdrant.tech/pricing/) | [About](https://weaviate.io/company/about-us), [pricing](https://weaviate.io/pricing) | Open-source vector database, paid managed cloud and enterprise offerings. Prices are not revenue. |
| Adjacent 30-day SDK windows | `@qdrant/js-client-rest`: 3,136,826 previous; 3,234,270 current | `weaviate-client`: 1,486,225 previous; 1,310,400 current | Original npm daily records; previous 25 August–24 September, current 24 September–24 October 2026, ends excluded. Downloads are not customers. |
| Stable SDK releases in 90 days | Two, `qdrant/qdrant-js` | One, `weaviate/typescript-client` | Existing verified GitHub captures; not team quality or future execution. |
| Financing | [12 March 2026 Series B](https://qdrant.tech/blog/series-b-announcement/), USD 50 million | [21 April 2023 Series B](https://weaviate.io/company/about-us), USD 50 million; [Ricoh disclosure](https://www.ricoh.com/release/2026/0616_1), investment on 13 March 2026, amount undisclosed | Selected dated announcements, not total funding, cash, revenue, runway or solvency. |
| Named leadership | Company about page identifies Andre Zayarni and Andrey Vasnetsov | Ricoh identifies Bob van Luijt and Etienne Dilocker | Attributed identity context, not an execution score. |
| Industry/competition | [Qdrant vendor benchmark](https://qdrant.tech/benchmarks/) includes both products | Same vendor comparison explicitly includes Weaviate | Category and peer context; not independent performance or a representative market cohort. |
| Attention sample | Five distinct retrieved titles naming Qdrant | Five distinct retrieved titles naming Weaviate | Exact-domain HN story records from the public Algolia API. Historical selected sample; retrieval reported non-exhaustive results. No complete/current attention total is claimed. |

Company pages and GitHub data are retained as compact reviewed fact summaries
with source URL, collection time and original capture digest, rather than full
articles or code. HN artifacts retain the selected story-title summary and selected
record digest; evidence URLs identify the corresponding public item JSON. Original
npm daily records are retained for independent summation of both input windows.
Full acquisition captures are retained locally under ignored
`tests/outputs/preloaded-companies-20261025`; the bundle is self-contained for
source-integrity checks and serving without that directory.

## What the models can and cannot do

SDK demand uses the existing trained Ridge/persistence component and exact matched
npm windows. Title sentiment uses the unchanged FinEntity TF-IDF/logistic weights,
exact company-name spans and the five retained titles. Its financial-news-to-HN
transfer is unvalidated; these mostly historical titles are not current public
opinion. No output is serialized in this input bundle.

The public-issuer financial model does not apply to either private startup.
Competition lacks a complete matched peer cohort. Execution inference is withheld
because its benchmark failed. Growth, survival and Overall remain unavailable;
adding source context does not create missing trained models. Available evidence
in a dimension is distinct from model eligibility.

## Runtime and verification

The application selects this exact bundle when both company configuration
variables are absent. `SIGNALSHIFT_PRELOADED_COMPANIES=0` disables that default.
An explicit root/publication selection always takes precedence, including its
errors; there is no fallback from a broken custom publication.

```sh
uv run --frozen --no-sync uvicorn \
  oxhack2026.api.company_runtime:create_company_app --factory --port 8000
npm --prefix frontend run dev
```

Open `/`, choose either saved company, inspect all five dimensions and their
sources, export the input-backed profile, or compare the two. Offline API and
weight-sensitivity tests are in `tests/unit/api/test_preloaded_companies.py`.
The real packaged browser replay is:

```sh
cd frontend
npx playwright test --config playwright.preloaded.config.ts
```

To publish a refresh, create a new source/publication ID with new measurements and
actual collection times. Do not edit frozen artifacts or make older data appear
fresh. Changing model weights must produce results through inference, never by
editing the bundled observations.
