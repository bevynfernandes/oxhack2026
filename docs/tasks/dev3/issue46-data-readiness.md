# #46: delegated data/backend readiness audit

Owner: Bevyn. Audit date: 2026-10-24. Numerical/target decisions remain Daniyal's;
Ivan owns the UI. No training was run. Machine-readable results are in
`startup-data-readiness-20261024.json`; downloaded data and inspected join rows
remain outside Git under `.cache/startup-data-audit-bevyn-20261024/`.

## Decision

**No candidate specialist passes the supervised-training gate.** Dated attention
and domain-popularity observations are feasible narrow evidence inputs, but there
are no approved historical domain/family mappings or joined endpoint labels in
this audit. Financial, retention and broad sector/team coverage is not established.
Use null predictions/outlook with explicit reasons. Do not fit a model on current
directory status or substitute a numerical rubric for a trained prediction.

## Frozen audit scope, not an approved historical cohort

- Commit-pinned YC Winter 2020 discovery JSON: 229 returned entries, hash
  `513ee3fc200dad3f1c8077ba5bc2fd51002b09715266fadff33b4eff1e957825`.
- Before joining predictor values, select current `industry == B2B` and either a
  `SaaS` tag or subindustry Analytics, Productivity, or Engineering/Product/Design.
  Retain all returned statuses. This provisional discovery filter selects 59:
  26 current Active, 19 Inactive, 14 Acquired. These are **not outcome classes**.
- Current taxonomy, names, websites, stage and family are not historical identity.
  All 59 domains and families remain unverified at the proposed origin. Directory
  launch timestamps and current headcount are excluded from historical predictors.
- Inspected join origin: 2022-01-01 UTC. HN observation window is calendar 2021;
  Tranco list V7NN aggregates 2021-12-02 through 2021-12-31 and reports creation
  at 2021-12-31 22:00:02.685016 without a timezone offset. UTC availability needs
  verification before fitting. Raw captures were actually made in 2026.
- No training/validation/test partitions are approved. Candidate later split
  origins 2022/2023/2024 require pre-origin features, elapsed 12/24-month labels,
  availability purging, and dated family separation. Each currently has zero
  approved positive/negative labels; class balance is therefore unestablished.

## Actual joins and coverage

Tranco V7NN full one-million-domain response was downloaded and hash-pinned.
Eleven of 59 current domains match; 48 absent domains are unknown, not zero users.
HN returned HTTP 200 and one complete bounded page for all 59 domain queries.
Twelve have at least one story whose final URL host exactly matches the domain;
47 have no matching retrieved story. This is a narrow link count, not broad
mentions, sentiment, independent endorsement or evidence of customer retention.
Current engagement totals, URL edits, deletions and index completeness are not
historical snapshots and remain excluded/limitations.

| Current directory status | Discovery rows | Tranco matches | HN nonzero |
| --- | --- | --- | --- |
| Active | 26 | 6 | 7 |
| Inactive | 19 | 2 | 2 |
| Acquired | 14 | 3 | 3 |

Coverage by current stage/sector is in the manifest, labelled contemporary
metadata. The audit has one vintage and no adjudicated outcome groups, so temporal
or outcome-stratified coverage cannot be claimed. Staleness uses actual declared
measurement windows, never collection time. Inspected rows include PostHog
(Tranco 74,251; 15 exact-domain story links in 2021), Accord and Finlens (rank
absent and zero matching story links); their current domains are still unverified
at the origin. The three-row joined sample and its hash are retained locally.

## Group decisions

| Group | Data decision | Training decision and blocker |
| --- | --- | --- |
| Adoption/retention | Conditional reach proxy only | Fail: 11 rank matches; no matched historical active/paying customers, churn, retention or comparable growth labels |
| Attention/sentiment | Conditional HN link evidence | Fail: historical identities and outcome labels absent; no broad independent platform/sentiment coverage |
| Financial health | Fail for training | Form D archive verified; zero conservative name candidates in this quarter, no verified issuer/domain join or comparable revenue/cash/burn/margin panels. Financing is not solvency |
| Industry/competition | Fail | No audited dated sector series, historical taxonomy, peer coverage or labels |
| Team/execution | Fail for cohort modelling | Existing two-company release data is applicable evidence only; no historical cohort-wide person/entity matching, continuity or execution panel |

The initial SEC probe used an obsolete path and returned 403; this is retained
as a failed probe, not evidence that the official archive is inaccessible. Daniyal
supplied the correct official-source capture through a private draft release;
the downloaded archive independently verifies to
`c8101d66b5c1070f249c2b7a26500e48a1dd490e70b4b18bbcf5b836948ebe3e`.
Actual ISSUERS/OFFERING/FORMDSUBMISSION columns were inspected. Joining by
accession and retaining primary non-fund issuers gives 5,542 filing rows and
4,886 distinct CIKs; 1,171 are amendments. Revenue is declined in 4,435 rows,
reported as no revenue in 576, and otherwise categorical/possibly inapplicable.
These are archive counts, not matched startup financial observations.

Conservative normalized full-name candidate matching against the 59 current and
former-name sets yields **zero candidates**, leaving all 59 without a candidate
in this quarter and zero verified legal-entity matches. This does not establish
that the companies never filed: legal names, subsidiaries, other quarters and
non-US issuers require explicit mapping. No fuzzy name is accepted as an issuer.
A 2024 Q1 filing is also too late for the 2022 feature origin. Pre-origin archives,
CIK/domain proof and amendment-chain adjudication are required before committing
financing features. Use filing availability; never sum amended offering totals
as new cash. No cash balance, runway or operating-cash-flow label is inferred.

The first-party PostHog history provides retrospective claims of revenue growth,
customer totals and cashflow positivity. It does not provide a matched historical
trailing operating-cash-flow panel or independently establish first availability.
Datree's primary repository explicitly reports closure in July 2023, but a month
interval and retrospective capture still require endpoint adjudication; it is a
separate lead outside the frozen 59-row filter, not an added handpicked negative.
Neither source is automatically an approved training label.

## Model recommendation and next action

Defer fitting. Once a group has both classes, adequate chronological coverage and
reviewed labels, compare training-only prevalence with regularized logistic
regression using training-only preprocessing. Consider CatBoost only after cohort
size/mixed predictors justify it. Local CPU compute is sufficient for these
candidates; compute availability does not resolve missing data.

Send Daniyal the compact manifest for target/data approval, resolve pre-origin
issuer identities and archive coverage, and agree the additive
[research-job/report contract](research-job-contract.md) with Ivan. A failed data
gate permits a sourced evidence report with explicit untrained status, not an
invented outlook or a claim of validated success prediction.

## Primary source references

- [SEC Form D datasets](https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets)
  and [table definitions](https://www.sec.gov/files/Form_D.pdf).
- [Tranco historical metadata API](https://tranco-list.eu/api_documentation) and
  [V7NN metadata](https://tranco-list.eu/api/lists/id/V7NN).
- [HN search API](https://hn.algolia.com/api).
- [Pinned W20 discovery](https://raw.githubusercontent.com/yc-oss/api/d7ecae893271b38e6f4d74ff550cd2488d9b7305/batches/winter-2020.json).
- [PostHog first-party history](https://posthog.com/handbook/story) and
  [Datree primary closure statement](https://github.com/datreeio/datree).

Source access/reuse: public access does not grant unrestricted redistribution.
Keep raw third-party datasets outside Git; verify source-specific licensing and
retention before dataset adoption. Tranco provider/version changes, HN deletions,
and the unofficial YC mirror limit comparability and representativeness.
