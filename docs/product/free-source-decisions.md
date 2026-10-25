# Free-source decision and model readiness

25 October 2026 (London). Audited main: `f1b7e65`. This implements source selection from
the supplied research, not a claim that universal startup prediction is possible.
The complete goal remains open until the supported forecast population and actual
held-out outcome performance are demonstrated.

## Selection

| Source | Free access now | Use in this product | Historical/model decision |
| --- | --- | --- | --- |
| Official company websites | Four named examples returned HTTP 200 | Primary identity and attributed company disclosures across the five views | Current claims are evidence, not historical training values. Use an actual archived capture for each historical origin. Missing customer/revenue/cash figures remain missing. |
| HN / Algolia | Actual domain query returned records | Optional dated attention, with exact company/domain matching | Preserve story IDs and original dates. Current scores/comments are excluded from historical predictors. Search absence is not zero public attention. Financial-news sentiment weights need a separate HN-domain evaluation. |
| npm | Actual daily-count query returned HTTP 200 | Optional developer-product demand | Existing trained download model remains an auxiliary experiment. Drop it as a business adoption/retention score: downloads do not measure paid retention. Not applicable to most businesses. |
| GitHub | Unauthenticated test returned 403 | Optional official repository evidence, with honest failure state | No required score dependency. Existing release-count model has unreliable held-out results and is not a team-quality model. |
| Common Crawl | Actual domain index returned capture metadata | Candidate historical website evidence and identity | Index availability is not proof that required content, periods or numeric facts exist. Retrieve and inspect the original capture before using it in a backtest. |
| SEC filings / Form D | Contact user-agent now configured locally; actual submissions and five company-facts downloads returned 200 | Conditional issuer financial/financing evidence after exact identity matching | Financial statements can support covered-company models. Form D is financing context, not cash/runway. Preserve accession-specific as-filed values. Public issuers are not representative private-startup training rows. |
| Companies House | Free API key required; none configured | Conditional UK legal identity, filings and disclosed accounts | No universal revenue/cash-flow assumption. Legal dissolution requires continuity review before becoming a business-closure label. |
| Gazette | Public notices, with jurisdiction and legal-entity matching | Candidate legal-event evidence | A notice alone does not adjudicate business continuity. No near-universal coverage or joined outcome panel has been established. |
| GDELT | Probe returned HTTP 200 with an empty object | Optional discovery only; no required numerical score dependency | No usable articles returned in this probe. Do not equate transport success with complete news coverage. |
| ALFRED | Probe timed out | Defer from mandatory retrieval | Macro context does not replace company financials or competitor measures. No working vintage-series integration verified here. |
| Hiring boards | Public for officially linked boards | Optional advertised-opening evidence | Drop from a backtestable headcount/execution score: no complete historical workforce panel. |
| Stripe, ChartMogul, Xero, product analytics, CRM, HR | Company authorization required | Excluded from automatic public company research | Potential direct histories, but inaccessible for arbitrary businesses under the public-only constraint. |
| Crunchbase/PitchBook/Dealroom/Orbis, G2, Similarweb, Revelio | Entitlement/licensing required | Excluded from free automatic dependencies | No new subscription or training rights assumed. |
| Kauffman Firm Survey / ONS | Survey or restricted research access | Methodology/reference only for this workflow | No demonstrated domain join and serving-feature match; do not train an arbitrary-company website model on inaccessible survey fields. |
| FinEntity | Original annotated dataset already captured and fitted | Candidate narrow financial-news sentiment component | Does not label startup success. Existing held-out negative-class coverage is weak. Do not label its score business health or apply it to any discussion without evaluation. |
| Majestic Million | Actual official CSV download succeeded; CC BY 3.0 | Offline, attributed domain-name candidates only, with explicit identity preview | Not a training source or business-health measure. Names must match a listed domain label; incomplete company/alias coverage remains explicit. |
| ECL authors' public filing/label CSV | Actual 26.7 MB download; pinned hash verified | Research-only recorded bankruptcy target and annual-report metadata | Four classifiers genuinely fitted with issuer/time separation. Limited selected public-issuer population, 13 positive holdout issuers, incomplete matched filing history, no independent event/family audit. No private-startup or full financial-health inference. No paid Compustat values used. |

Actual probe responses and SHA-256 hashes are retained locally in
`tests/outputs/final-product-20261024/source-probes/manifest.json`.
These examples are stress checks, not a representative coverage estimate.
Gemini's actual retained-capture audit is
`tests/outputs/final-product-20261024/gemini-real-mapping-audit.json`.
It returned partial results with provider/background-completion errors. Exact
source quotations and independent subject checks remain mandatory; its output
does not become numerical ground truth.
Gemini interpretation is enabled by default alongside deterministic mapping. Set
`SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules` to disable model requests. A global
provider failure ends the optional batch loop immediately while preserving
supported rule-based results. Failed optional interpretation is never presented
as a successful model mapping.

Live name-provider checks rejected DuckDuckGo after four human-verification
responses. Wikidata and the Majestic HTML frontend returned 403; the explicitly
published Majestic CSV endpoint succeeded. Gemini 2.5 Flash requests returned a
retired-for-new-users error, 3.8 Flash was quota-limited, and the separate Live
grounding attempt closed without a usable answer. Bing RSS was excluded because
its response restricts reuse. No CAPTCHA was bypassed or paid service activated.
The shipped Majestic-derived snapshot has 999,742 domains and a source/artifact
hash manifest under `oxhack2026/research/bundled`. Its eight-query live-data audit
is retained in `tests/outputs/final-product-20261024/directory-name-search.json`.
This is a bounded, reproducible identity-discovery compromise, not a claim of
near-universal company-name coverage.

## What the current five fitted models establish

The existing bundle predicts SDK demand growth, SDK peer share, release cadence,
public-issuer cash margin and financial-news sentiment. Only the last target is
itself a direct instance of its named business dimension. None was trained on
startup survival or commercial success/failure. Existing numerical results and
limitations remain in `docs/tasks/dev2/public-dimension-training-20261024.md`.

Do not relabel those models or average their percentiles into a validated startup
success probability. The five groups should organize dated evidence; outcome
models should learn later company outcomes from that evidence on the same rows.

## Target and release decisions

- Keep Growth (24 months) and Survival (24 months) as separate forecasts. Financial
  health remains a dimension, so a third headline financial forecast is redundant
  for the requested revised layout.
- The requested third headline is Overall outlook: the user's selected dimension
  index, with each constituent target and limitation shown. It needs five validated
  business dimension scores. It is not a success probability or an average of
  Growth/Survival probabilities, and cannot be filled with default 50s or silently
  reweighted when dimensions are missing.
- Growth requires comparable revenue or paying-customer observations. Survival
  requires dated closure/operation and acquisition-continuity evidence. Neither
  a reachable website nor missing records supplies the label.
- Start with regularized logistic regression versus training prevalence for
  mature binary outcomes; compare a small tree/boosting model on identical rows.
  Use train-only preprocessing, family separation, temporal splits, label maturity,
  calibration/loss and coverage. LLMs assist extraction, not outcome fabrication.
- No new release of five business scores or top-card probabilities is justified
  by the existing training evidence. Supported research should still work for
  names/domains and show which measurements and predictions are unavailable.

## Remaining evidence needed

A joined historical company panel with supported pre-origin features and mature,
dated business outcomes is still missing. This is an unmet product requirement,
not a reason to call the project complete. Public financial filers may support a
narrower prediction population; arbitrary private-company search must retain
evidence gaps until comparable public disclosures can be verified.

## Latest implementation and data checks

- The SEC collector now retains declared history pages up to eight, checks exact
  response CIKs, and preserves registry facts on independent history failure.
- A checksum-verified 1.24 GB public SEC metadata snapshot exposed real cadence
  differences from the ECL matched subset. Four further models were trained on
  full history; the later 2018–2021 holdout gave ROC AUC 0.603 and the frozen
  validation-loss gate failed. Keep both runs and their limitations visible.
- The 986,914-entity company metadata companion contains **zero** nonempty website
  or investor-website fields. Drop it as a domain-to-CIK resolver; a matching name
  alone cannot establish legal identity.
- After configuring the contact, the official submissions API returned 200 and a
  bounded original financial-statement archive request returned 206. Five real
  company-facts responses, including three historical bankruptcy cases, returned
  200. The actual production Fetcher retained Cloudflare and Salesforce payloads.
  Salesforce needs 4.7 MB, so exact SEC company-facts endpoints now allow up to
  16 MiB, with the existing 32 MiB job cap; ordinary responses remain at 4 MiB.
- The user permits extrapolation. Distinguish an estimate from a measurement,
  show assumptions/uncertainty, and retain missing facts. This does not establish
  validation or make an unrelated proxy the requested business target.
