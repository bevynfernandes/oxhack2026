# Startup prediction: shared delivery plan

## Confirmed product and compute

Choose one startup by name/domain, research it, inspect fundamental metrics and
specialist predictions, then see its overall outlook. Focus on **Software/SaaS**
first, with a **balanced outlook across growth, survival and financial health**.
The working-demo budget is **two hours**. Keep the interface clean and intuitive.

**Training and inference run locally on the backend CPU.** Do not substitute
hosted LLM calls or an arbitrary rubric for trained predictions. Build data and
model contracts alongside the application; do not implement a large unsupported
metric catalogue first. **No training now:** first establish which historical
inputs and outcome labels can actually support each model, then confirm choices.

This direction updates #19 and the product scope in PLAN.md. Existing provenance,
privacy, immutable publications and temporal safeguards remain. Existing v1 target
IDs must not silently change meaning when adding survival/financial-health targets.

## Data diligence completed on 24 October 2026

These are actual downloaded samples, not promises based on API documentation.
Raw responses, capture times, HTTP statuses and SHA-256 hashes are retained locally
in `.cache/startup-data-audit/manifest.json`. Samples are discovery evidence;
none is an approved training dataset. Downloaded third-party data stays out of Git.

| Source checked | Actual structured evidence | Historical suitability and decision |
| --- | --- | --- |
| HN Algolia | A bounded PostHog domain query before 2024 returned five stories and reported 94 matches; JSON has story ID, URL and creation time | Candidate attention event counts after domain matching and pagination/completeness audit. Current points/comments are not their historical values. Coverage of a startup community is not general social sentiment. |
| Tranco | The 2024-01-01 API response supplies permanent list ID `V929N`, creation time, provider configuration, a 2023-12-03 to 2024-01-01 window and download URL | Historical domain-popularity proxy is feasible. This audit verified metadata, not company rank coverage or the full rank archive. Absence is unknown, not zero users. Provider/window changes need versioning. |
| SEC Form D | Downloaded 2024 Q1 archive, 3,428,140 bytes. Inspected actual TSV headers: filing date/accession, issuer CIK/legal name, amendment link, sale date, amount sold, offering amount and revenue range | Structured historical financing inputs are feasible for matched US issuers. Resolve legal entities, remove funds, deduplicate amendments and use filing availability. Offering amounts are not cash balances, ARR or runway; revenue bands can be undisclosed. Cohort match coverage remains unmeasured. |
| YC Bench | Downloaded early-mentions CSV: 198 rows, domain/count fields. Traction CSV: 11 rows, ARR/pilot revenue/LOI/users/activity/growth columns | Useful research lead, not a balanced-success training set. One small batch, self-disclosures, zeros needing missingness review, no verified survival/financial-health labels. Short-term ranking uses a heuristic traction/attention proxy. Resolve 198-row file versus 196-company paper, row provenance, availability and reuse rights before adoption. No license file appeared in the inspected repository root. |
| Existing project publications | Two real company profiles, fourteen metric rows; six commercial unknowns and one stale financing observation. YC discovery ledger has 229 companies and 687 unresolved outcome follow-ups | Reuse contracts and collection machinery. These are insufficient for supervised startup prediction. Current active/inactive/acquired directory status does not establish historical features or dated outcome labels. |

Audit hashes: SEC archive `c8101d66b5c1070f249c2b7a26500e48a1dd490e70b4b18bbcf5b836948ebe3e`;
Tranco metadata `ea93cb5ae953460a14c092ad41cbb6853a0d3371cacffca2c0d72d00baaa987d`;
YC early mentions `b8ff077c21bfeddf6944627bbcc71aedf95150cc1824d7190b7a37e31177b71d`.

**Conclusion:** structured historical attention and financing inputs exist. We have
not established a representative joined cohort, enough dated failure/survival
labels, or broad private-company revenue/retention/runway coverage. The full
balanced prediction is therefore **not training-ready**. Local compute is feasible;
data coverage is the limiting question. Do not promise every group a trained model
until its audit passes. A failed data gate must narrow or defer that model.

## Fundamental groups and parallel data/model work

| Group | Preferred metrics | Data gate before implementation/training |
| --- | --- | --- |
| Adoption and retention | Active/paying customers, growth, retention/churn, conversion; traffic/downloads as explicitly labelled proxies | Verify dated first-party/public disclosures or permissioned structured records. Tranco can supplement reach; it cannot establish retention. Audit SaaS types beyond developer tools. |
| Attention and sentiment | Mention velocity, independent coverage, sentiment, source concentration, divergence from adoption | HN event counts are a feasible narrow start. Obtain historically dated text and independent platform coverage before claiming broad sentiment or hype. Exclude future engagement totals. |
| Financial health | Revenue growth, gross margin, burn, cash/runway, unit economics; financing history as context | SEC Form D supports financing context, not solvency. Audit public accounts/disclosures and comparable accounting periods. Private unavailable values remain unknown; no invented burn/runway. |
| Industry and competition | Market demand, sector growth, peer adoption, competitive concentration, regulatory changes | Identify a dated structured sector series and stable taxonomy, then measure startup cohort coverage. Current reports and retrospective summaries alone do not pass historical training gates. |
| Team and execution | Relevant experience, continuity, delivery cadence, customer execution | Verify historical availability and entity/person matching. Product releases can support applicable firms; current headcount/bios are not historical snapshots. Avoid demographic proxies. |

Specialist models must predict defined outcomes using their group's supported
features; they must not simply assign a score to the metric's magnitude. Keep the
five UI groups, but allow `insufficient_data` and `model_not_trained` independently.
Train fewer defensible models before inventing five weak ones. Do not assume a
pretrained language model knows future startup outcomes reliably or without leakage.

Recommended candidates, pending data approval: existing prevalence comparator,
then regularized logistic regression with training-only preprocessing. Consider
one small CatBoost challenger only if mixed types/nonlinearity and cohort size
justify it. These can train and infer on local CPU; no GPU, hosted inference or
new deep-learning stack is required. Existing local sklearn/CatBoost installations
were verified; installation does not establish model quality.

## Required training-readiness deliverable

For each candidate metric group, Bevyn and Dev 2 publish one compact manifest:

- Source/access/reuse conditions, exact fields/types/units, historical date range,
  observation and first-availability timestamps, raw capture/hash and parser version.
- Frozen Software/SaaS cohort rules, domain/legal-entity/family mapping and counts
  matched/unmatched. Include failed/inactive companies, not just today's survivors.
- Feature missingness/staleness and coverage by stage, sector, vintage and outcome.
  A few attractive examples do not establish cohort coverage.
- Explicit outcome definition/horizon and label evidence. Separate known positives,
  negatives, censored and unknown; missing records are not failures or survival.
- A small inspected joined sample, leakage exclusions, chronological split dates,
  family separation and class counts per split. Check label maturity at fit time.
- A pass/conditional/fail decision, model recommendation and concrete blocker.

A runnable fit requires both classes and defensible temporal coverage; tiny class
counts must not masquerade as statistical validation. Freeze dataset/features/
endpoints/splits before final holdout access. Fit transformations on training only.
Evaluate on the same held-out companies against prevalence using Brier/log loss,
calibration, discrimination and coverage. Existing evaluators can be reused.
Backtesting stays unavailable until an actual reproducible evaluation exists.

## Overall outlook semantics

Growth, survival and financial health are three different endpoints. Proposed
horizons are 24 months for growth/survival and 12 months for financial health;
precise definitions, thresholds and stage treatment remain to be frozen with data.
Funding, acquisition, attention and temporary losses are not automatic success or
failure. Do not silently relabel the existing cash-flow/financing endpoints.

A balanced combination could use equal component weights, but this is a proposal,
not an approved success probability. Define and version the utility mapping after
endpoint feasibility is known. Avoid double-counting correlated specialists. A
learned combiner needs chronological out-of-fold predictions and untouched testing.
Until trained/validated artifacts exist, return a null numerical outlook with its
reason and show sourced observations/risks. Missing components are not zero and
must not be silently reweighted. A potential hype/fundamentals gap is a hypothesis,
not proof that a company is a bubble.

## Ownership and application contract

**Dev 2 / Daniyal:** own this plan, data/model audit with Bevyn, target definitions,
feature policy, local model interface, numerical outlook and evaluation. Keep model
and product contracts aligned now; hold fitting until the readiness gate passes.

**Bevyn — delegated data/backend:** prioritize the readiness manifest and joined
historical coverage audit above. Start with Form D entity matching, dated attention
and verified outcome evidence; investigate financial/adoption coverage before
committing implementation. Report which groups fail. Alongside that audit, propose
an additive company/domain research-job API using existing source/publication
storage. Bounded public-source collection, actual timestamps, identity confirmation
and partial/error states are required. No hosted AI provider dependency.

**Ivan — continue existing UI assignment:** #43/#45 already establish single-company
search, warm neutral surfaces, restrained teal, accessible disclosures and short
reduced-motion-aware transitions. Keep that work; no reassignment or redesign.
The next UI should accept a startup/domain, distinguish saved reports from fresh
research, show actual research status, then present the five groups and overall
outlook. Metrics/evidence, unknowns, model status and validation must be visible.
Backend-provided numbers only. Leave prediction placeholders readable and honest;
no fake progress, invented score or browser-side scoring. Comparison is secondary.

Suggested additive report fields: company identity/context, research job state,
source publication ID, specialist sections, overall outlook, model/data versions,
coverage and limitations. Each section carries observed metrics/evidence IDs,
applicability and model status, prediction/horizon when available, and explanations.
Use `null` with a reason when unavailable. Preserve current v1 saved links. Bevyn
and Ivan agree the narrow API payload before either independently implements it.
Local model artifacts must record feature schema, target, training snapshot, split
and validation version; inference loads compatible approved artifacts only.

## Two-hour sequence and acceptance

1. First checkpoint: acknowledge ownership, deliver the source/label readiness
   matrix and narrow report contract. Merge compatible existing UI work in order
   (#44 before stacked #45). Avoid building a wider metric catalogue during audit.
2. Next checkpoint: complete one real company research path and historical join
   sample while Dev 2 freezes feasible model features/targets and Ivan wires states.
   Models remain placeholders where the gate fails; training is a later decision.
3. Integrate and verify the actual API/browser flow, sources, partial failures,
   missing data, mobile and keyboard behavior. Reserve the final 15 minutes for
   fixes and a stable demonstration; keep PRs small and descriptions short.

Done means one real Software/SaaS company can be selected and researched, all
applicable facts are traceable, model readiness is explicit, and the overall
outlook honestly reflects available trained artifacts. The demo must not claim
validated success prediction if the data gate is still open. Defer broad sector
expansion and a polished backtesting workspace. Retain personal-email sign-offs.

## Primary references

- [SEC Form D datasets](https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets)
- [Tranco API and historical list metadata](https://tranco-list.eu/api_documentation)
- [HN search API](https://hn.algolia.com/api)
- [YC Bench data repository](https://github.com/benstaf/ycbench)
- [Logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
- [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [CatBoost categorical features](https://catboost.ai/docs/en/features/categorical-features)

Source accessibility and model capabilities do not establish predictive skill.
