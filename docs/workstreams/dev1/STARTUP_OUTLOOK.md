# Dev 1: company evidence contract proposal

Coordination: [#19](https://github.com/bevynfernandes/oxhack2026/issues/19).
This is the source contract proposal for consumer review, not an implemented
model or proof of company-success prediction. Existing C1 artifact references,
UTC windows, strict identifiers and immutable publication remain reusable.

## Proposed C1 records

Use `company_id` equal to the existing company-backed `organization_id` where
verified; do not remint an unrelated identity. Community/reference organizations
are not automatically companies. Effective parent/family ownership must be dated.
A present-day family assignment must not leak into historical features.

| Record | Proposed fields / invariants |
| --- | --- |
| `CompanyProfile` | `company_id`, `display_name`, `website_url`, `segment`, nullable `business_model`, nullable `stage`, `context_as_of`, `evidence_ids`; profile context is snapshot-specific |
| `CompanyRelationship` | `relationship_id`, `company_id`, `subject_kind` (`legal_entity`, `tool`, `package`, `repository`, `parent_company`), typed subject identifier, `valid_from`, nullable `valid_to`, `evidence_ids`; effective windows cannot silently overlap for the same exclusive relationship |
| `MetricDefinition` | versioned `metric_id`, `family` (`traction`, `commercial`, `execution`, `market_financing`), label, definition, unit, value type, measurement scope, applicability rule, freshness policy; currency/accounting/customer definitions belong in separate definitions |
| `SourceEvidence` | `evidence_id`, provider, public-safe URL or restricted attachment reference, raw `ArtifactReference`, locator/assertion, nullable `published_at`, `available_at`, `collected_at`, availability basis (`dated_publication`, `first_observed`), evidence kind (`registry_record`, `company_reported`, `platform_observed`, `user_supplied`), review state (`unreviewed`, `verified`, `disputed`); verification is not a numeric confidence score |
| `CompanyMetricObservation` | `observation_id`, `company_id`, `metric_id`, period (`TimeWindow` or explicitly typed point-in-time), strict typed value or null, state (`observed`, `missing`, `not_applicable`, `conflicting`), reason code, `evidence_ids`, `available_at`, `collected_at`, nullable `supersedes_id`; finite values, zero distinct from missing |
| `CompanyEvent` | `event_id`, `company_id`, kind, occurrence date/precision, stage (`announced`, `completed`, `reported`), `evidence_ids`, `available_at`, `collected_at`, nullable `supersedes_id`; separately type funding, acquisition, company shutdown, product retirement, release and ownership changes |
| `CompanySourceManifest` | schema/snapshot/cohort versions, recorded time, actual code/config hashes, references to normalized profile/relationship/definition/evidence/metric/event/coverage artifacts, synthetic flag, reconstruction mode, limitations |

No future outcome labels or model probabilities belong in these records. Dev 2
imports these source records and owns outcome/assessment classes. Dev 3 projects
published source/assessment data into its API rather than creating a third model.
Use distinct metric value variants (integer, decimal, Boolean) rather than a
coercing float/string union. Decimal monetary values need currency, scale and
period semantics; keep unparsed company claims as evidence until normalized.

`available_at <= collected_at`; publication may be unknown. Unknown publication
uses first observation as availability, never an invented earlier timestamp.
Actual collection is never replaced by the event or announcement date. Unknown
event time uses explicit missingness/date precision rather than midnight precision
fabricated from prose. A future announced closing date is not a completed event.

Dataset validation checks IDs, relationships, source hashes, metric types/units,
missingness, all evidence foreign keys and effective ownership. Coverage carries
expected applicable definitions, observed/missing/conflicting counts, last success
and reasons by family. Exclude inapplicable metrics from denominators; freshness
is computed at the assessment cutoff using versioned policy, not a moving clock.

Reader proposal: `manifest(snapshot_id)`, `companies(snapshot_id)`,
`company(snapshot_id, company_id)`, `metrics(snapshot_id, company_id)`,
`events(snapshot_id, company_id)` and evidence lookup. All reads are exact-version;
selection for historical features additionally applies availability/collection
policy and preserves the reconstruction label. A newer snapshot never repairs a
historical query silently. Reuse atomic publication and integrity checks.

## First metric/source set

| Family | Initial evidence | Access and feasibility | Limit |
| --- | --- | --- | --- |
| Traction | Windowed npm downloads; model-owned growth/change calculation | Existing real ten-company catalogue, raw/checksummed dataset and extractor | Re-downloads/CI activity are not customers; mapping dates and package migrations matter |
| Execution | Published release count/dates and time since release for verified repositories | Public GitHub REST releases, paginated, bounded/cached requests | No releases may reflect release practice, not inactivity; deleted/edited releases limit historical completeness |
| Market/financing | Dated financing, acquisition and ownership events | Reviewed primary company/investor announcements with captured source bytes | Self-reported, selective disclosure; announcement is not completion and silence is not zero events |
| Commercial | Disclosed revenue/pay customers/cash flow with explicit periods | Primary reports or user-supplied accounting exports, separately reviewed | Mostly unavailable for private firms; no metric fabricated from funding or downloads |
| Legal/operating context | Company status, filings, insolvency/dissolution evidence | Companies House API after UK legal-entity match and API-key setup | Legal active status does not establish commercial growth; dissolution of a subsidiary is not a parent shutdown |

The first real checkpoint can contain traction, execution and financing evidence
plus explicit missing commercial observations. It cannot establish all three
outcome probabilities. Prefer one completely traceable company to many loosely
matched names; compare requires at least two real profiles before its real-data
acceptance gate passes.

Official access documentation checked 2026-10-24:

- [GitHub releases](https://docs.github.com/en/rest/releases/releases): public
  releases can be read without authentication, list pages have at most 100 rows,
  and ordinary Git tags are not automatically releases. Paginate to exhaustion
  or flag truncation; retain the exact repository ID and raw response.
- [GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api):
  standard unauthenticated budget is 60 requests/hour; authenticated user budget
  is generally 5,000/hour. Respect response headers and secondary limits; no key
  rotation to evade limits. Read credentials without logging them.
- [GitHub statistics](https://docs.github.com/en/rest/metrics/statistics): computed
  statistics can return 202 while pending and exclude merge commits. Treat that
  as pending, never zero. Initial work uses published releases instead of silently
  mixing incompatible activity measures.
- [Companies House profile](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/company-profile/company-profile)
  and [filing history](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/filing-history/list)
  require API-key access. The documented budget is
  [600 requests per five minutes](https://developer-specs.company-information.service.gov.uk/guides/rateLimiting).
  Keep dated filing evidence; today's status is not a historical time series.
- [SEC data APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
  expose filer submissions and XBRL without API keys. This is conditional coverage
  for actual filers, not a universal private-startup financial database. Follow
  [fair-access rules](https://www.sec.gov/about/developer-resources), including an
  identifying user agent and no more than ten requests/second.

These are verified access mechanisms, not claims that every company has data.
No registry credentials or private financial exports have been supplied for this
checkpoint. No paid vendor is required for the first snapshot. Do not make social
scraping, proprietary traffic estimates, Google Analytics or an unidentified
Kaggle dataset a core dependency. A specific external dataset needs license,
field definitions, vintage, selection and label provenance review first.

## Historical cohort procedure

1. Freeze sector, geography, founding/eligibility dates and discovery-source rule
   before looking at later outcomes. Record a complete dated directory snapshot
   or another auditable enumeration; today's catalogue is insufficient.
2. Resolve legal/company/product identities with dated evidence. Maintain an
   inclusion/exclusion ledger with reason and source, retaining inactive/failed
   companies that qualified at the historical cutoff.
3. Obtain predictors actually available at each cutoff. Mark reconstructed
   histories and never backdate current funding, repository counters or ownership.
4. Independently obtain endpoint follow-up and dated evidence. Record source
   disagreement and failed retrieval as unknown, not company failure.
5. Hand Dev 2 company-level follow-up/coverage and raw evidence. Dev 2 applies
   outcome definitions, calendar horizons and censoring. Freeze the cohort before
   train/validation/test separation and record any later corrections as revisions.

No sufficiently labelled historical company cohort has been acquired yet. The
commercial targets may require consenting companies' historical records or a
properly licensed dataset. If ascertainment is selective, report it and restrict
claims; adding selected famous shutdowns does not solve survivorship bias.

## Immediate Dev 1 acceptance

- Consumer-reviewed additive C1 classes/schema fixtures and invariant tests.
- A real snapshot with several metric families and honest commercial unknowns.
- Portable source bytes/hashes and exact-version reader, independently loaded by
  Dev 2/3; company/package attribution remains validated.
- Integration of separately published Dev 2 assessments with Dev 3 company views.
- Separate accounting for evidence-product completion, label coverage and model
  validation. Older download progress is not revised-product completion.

## Concrete first profile candidate

LangChain already has a verified npm/repository mapping in the current catalogue.
Combine its dated SDK download windows, public `langchain-ai/langchainjs` release
records (labelled SDK execution activity), and the company's
[20 October 2025 financing announcement](https://www.langchain.com/blog/series-b).
That primary announcement reports a $125 million raise; record it as a dated
company-reported financing event, without asserting that it is the latest round
or that funding establishes runway or profitability. Cash flow, retention and
comparable paying-customer histories remain unknown without further evidence.
This is a proposed real-source profile, not a normalized/published company bundle.
