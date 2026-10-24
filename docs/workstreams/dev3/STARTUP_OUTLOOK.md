# Company outlook: Dev 3 design and integration

Coordination: [issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19).
This records the user's revised objective. The old download-only task checklist
does not measure completion of the company-outlook product. Shared outcome and
source contracts are reviewed and integrated in #32/#39/#41. The company
list/profile/compare implementation has passed real API/browser acceptance.
The implementation PR supplies independent review and CI before release.

## Product decision

Help a researcher assess a startup's prospects, understand the evidence and
compare it with relevant companies. A company is the primary entity; packages,
repositories, products, financing events and financial observations are evidence
about that company. Downloads contribute to traction when applicable.

Present three assessments independently:

| Assessment | Horizon | Questions the view must answer |
| --- | --- | --- |
| Operating and growing | 24 months | Is the business continuing to operate, and what supports its growth outlook? |
| Cash-flow self-sufficiency | 12 months | Is the company operating with nonnegative operating cash flow over the ending twelve months? What remains private or unknown? |
| Funding or acquisition | 24 months | What financing or acquisition outcome is assessed? What would the event establish, and what would it leave unknown? |

Dev 2 owns precise labels, censoring and model semantics. A funding round is not
profitability; an acquisition may be distressed. No funding announcement is not
a failure label. A missing company or immature outcome stays unknown. Public
metrics alone may be insufficient to estimate commercial viability.

## Information architecture

Primary navigation: **Companies**, **Traction research**, **Methodology**.
Comparison starts from the company selection bar. Source health
is available within evidence/methodology. Existing download forecast screens
remain identifiable traction research; they must not masquerade as company
success predictions. Do not move the landing page to the company workflow until
its additive API contract and repository handoff are available.

### Company list

Use a compact title and one sentence explaining the workspace. Search, peer-group
filters and the assessment date sit immediately above a table. Avoid a decorative
hero, repeated summary cards and an aggregate success gauge.

| Company | Context | Outlook | Supporting signal | Main risk | Evidence | Updated |
| --- | --- | --- | --- | --- | --- | --- |
| Published identity | Segment, stage, business model | Model-owned summary or insufficient evidence | Strongest published statement with source | Principal published concern or evidence gap | Available/required metrics by family | Actual snapshot date |

Search name and segment. Filters include segment, business stage, evidence
availability and assessment date. Stage/business model may be unknown. Keep
filter state in the URL and display the result count. Use explicit empty and
unavailable states. Default order is company name or update date until the model
owner defines a defensible assessment ordering.

Rows open company profiles. Compare checkboxes use company IDs, with a compact
selection bar and an explicit action. Limit the first compare view to three
companies so it remains legible. Do not replace missing companies with examples.

### Company profile

1. **Identity:** name, website, segment, business model/stage and assessment date.
   Show ownership/family changes with their dates when relevant.
2. **Outlook:** three horizontal assessment rows, each with horizon, published
   conclusion, evidence sufficiency and a short supporting explanation. An
   unvalidated assessment is labelled provisional. Probabilities are absent
   unless the model-owned publication gate permits them.
3. **Evidence and risks:** a concise list of evidence-linked supporting factors,
   concerns and critical unknowns. Do not generate reassuring copy from missing
   observations or convert a model explanation into a causal claim.
4. **Metrics:** a compact table grouped by traction, commercial health, execution,
   and market/financing. Show value, unit, period, comparison context, source and
   freshness. Unknown, inapplicable, stale and observed zero remain distinct.
5. **Events:** dated financing, acquisition, shutdown, product/release and team
   events where supported. Display the source and the date the system learned
   about the event; announcement dates and collection dates remain separate.
6. **Methodology:** collapsed provenance, cohort limitations, label definitions,
   model/evaluation versions, censoring and detailed metric definitions.

The first screen answers what the outlook is, why, and what is unknown. Technical
artifact IDs belong in the expandable provenance section rather than the main
decision flow. A chart is included only when a measured time series supports it.

### Compare

Compare the same immutable assessment date where available. Otherwise disclose
the differing dates and require the reader to interpret that limitation. Rows
are outcome assessments followed by the same applicable metric definitions.
Columns are companies. Show units, horizons, source dates and missingness in
place. Do not force unlike business models onto a package-download ranking.

Pin the selected company names on narrow screens and allow the comparison table
to scroll horizontally. Keep an accessible caption and explicit row/column
headers. Changing selection cannot rewrite a saved assessment or historical
comparison. Actual matured outcomes use a separate reveal/read boundary.

## Visual system

- White content surfaces on a neutral light background; dark readable text and
  one restrained blue accent for links and primary actions.
- Compact top navigation and a small wordmark. Sentence-case headings around
  24–32 pixels, normal tracking, no decorative all-caps eyebrow copy.
- Tables and divided rows carry dense research information. Use a panel only
  for a meaningful grouped task; avoid a card for every metric or badge.
- Minimal corner rounding, thin borders and no gradients, glowing effects or
  decorative shadows. Consistent spacing makes the hierarchy clear.
- Status always has a plain-language label/reason. Colour is secondary; green
  must not imply success without a supported outcome assessment.
- Visible keyboard focus, readable contrast, 44-pixel primary controls, semantic
  tables, mobile layouts and reduced-motion support remain acceptance criteria.
- No remote font or bitmap dependency is necessary for the first revision.

## Contract ownership and proposed C3 projection

Dev 1 supplies source metric/event/snapshot contracts and typed storage reads.
Dev 2 supplies outcome definitions, assessment semantics, evaluation and the
probability gate. Dev 3 maps those into public DTOs and generated TypeScript.
This document intentionally does not define a competing Python model or score.

Required published facts for API alignment:

| Area | Needed facts |
| --- | --- |
| Identity | Company/family IDs, display name, website, segment, business model/stage, dated ownership |
| Snapshot | Exact assessment ID/version, as-of date, mode, cohort and source/model references |
| Outcome | Definition/version, horizon, model-owned conclusion/status, evidence sufficiency, supporting/risk statements, probability only if eligible |
| Metric | Definition/version, family, unit, measurement window, value or missingness, applicability, comparison context, evidence references |
| Source | Original public URL, observation/availability/collection dates, reliability and retrieval/version provenance |
| Event | Type, dated occurrence/announcement, source, when known, and implications bounded by the evidence |
| Coverage | Available/required evidence by applicable family, stale records and critical gaps, never an invented health score |

Proposed public reads are a snapshot-scoped company list and company profile.
Compare reuses those profiles. Search/filter parameters are bounded; IDs remain
opaque and snapshots immutable. API requests never collect vendors, train a
model or call a paid explanation service. Missing production data returns an
explicit unavailable response rather than loading a synthetic fixture.

## Implementation sequence and dependencies

1. Record the UX proposal and revised acceptance in #19/#1. Deliver the neutral
   visual system independently; preserve current route behavior while contracts
   are coordinated.
2. Agree source and outcome contracts with Dev 1/2. Update the shared plan through
   the designated coordination PR; do not let independent workstreams rewrite
   contradictory product specifications.
3. Add C3 company list/profile DTOs and generated types against those contracts.
   Keep outcome truth separate and cover all unknown/provisional/stale states.
4. Implement company list, profile and comparison against injected repositories
   and explicitly synthetic saved component fixtures. Replace the landing page
   only when the complete company workflow exists.
5. Compose the production adapter over real multi-family company snapshots. Verify
   metric dates, units, applicability, versions and public-safe sources.
6. Run the real-company acceptance flow, leakage checks, accessibility/mobile
   browser suite and package checks. Update the checklist with actual evidence.

## Revised acceptance

One real company must have an assessment using several dated metric families,
all three outcome sections, clear critical unknowns and inspectable sources.
The company list/profile/compare workflow must be intuitive and accessible.
No numeric success probability is published without mature historical labels,
chronological evaluation and the model-owned calibration gate. Existing npm
download tests are reusable infrastructure, not proof this product is complete.

Demo/export/offline serving remains excluded by the user's instruction. Data
acquisition, paid integrations and cloud rollout retain their existing owners.
