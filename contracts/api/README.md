# C3 public API contract (0.4.0)

## Company outlook additions

`company-api-v1` adds three read-only routes alongside the download contracts:

- `GET /api/v1/company-snapshots`: explicit published assessment/source choices.
- `GET /api/v1/company-snapshots/{snapshot_id}/companies`: name-ordered company rows.
- `GET /api/v1/company-snapshots/{snapshot_id}/companies/{company_id}`: a profile
  with all three outcome sections, exact source metrics/events, frozen coverage,
  effective family and redacted provenance. Comparison reuses these profiles.

`PublishedCompanyRepository` composes `CompanySourceReader` with the lightweight
`storage.company_assessments.CompanyAssessmentReader` read port and an explicit
tuple of assessment publication IDs. Route `snapshot_id` parameters and saved UI
selections identify the **assessment publication**, never a source-only alias.
Public metadata includes `assessment.publication_id`, its policy/recording time,
and the separate `source.snapshot_id`. Two assessment policies may reference the
same source while retaining distinct URLs. Removing a configured publication
returns 404 for its saved URL; it never resolves to a replacement. Construction has
no I/O. Reads validate company/source identity, dates, synthetic/family state,
foreign keys and evidence support. API code never creates assessments or scores.
Unknown IDs are 404; corrupt or incomplete publications are 503.

Inject the adapter through `create_app(company_repository=...)`. Company-only
composition uses that adapter for readiness while legacy reads remain explicitly
unavailable. A factory without either adapter serves no synthetic data. The
application owner supplies and manages the actual storage readers.

Source definitions, values, states, windows and event stages remain C1-owned;
assessment text/status and horizons remain C2-owned. This assessment version
only permits `evidence_only`/`unavailable` with null probability. Future outcome
labels are outside this API. Raw artifact locations, locators and restricted
source assertions are absent from public responses. Financial decimals serialize
as exact strings. The existing download contract version remains 0.4.0.

Restricted derived metric values/reasons are withheld using the explicit
`restricted` public state. Private events and relationships are omitted; effective
family uses public evidence only. Public coverage excludes restricted states and
lists withheld metric IDs separately. Source/C2 composition delegates to Dev 1's
`validate_company_assessments`; source-observed stale/private/unreviewed metrics
can legitimately be C2 evidence gaps. The API does not infer that policy.

Local runtime (the operator supplies a verified, restored root):

```sh
export SIGNALSHIFT_COMPANY_ROOT=/absolute/path/to/company-root
export SIGNALSHIFT_COMPANY_PUBLICATIONS=company-assessments-vector-20261024-v1
uv run uvicorn oxhack2026.api.company_runtime:create_company_app --factory
```

Missing/invalid configuration keeps readiness/data unavailable. Publication IDs
are explicit; publishing a newer policy never silently changes the selection.

`oxhack2026/api/schemas.py` is the source of truth. `openapi.json` and
`frontend/src/api/schema.d.ts` are generated, not independently edited.

```bash
uv run --frozen --no-sync python -m oxhack2026.api.export_contract
npm --prefix frontend run generate:types
uv run --frozen --no-sync python -m oxhack2026.api.export_contract --check
npm --prefix frontend run check:types
```

The API tests compare the committed OpenAPI byte for byte. The frontend build
checks generated TypeScript drift before compiling. Breaking field or enum
changes require a contract-version change, regenerated exports, reviewed C1/C2
mappings and fixture updates in the same PR.

Batch-level time, ecosystem, target and provenance fields apply to every result.
Forecast DTOs cannot contain future actuals. Outcomes and realized errors exist
only in the separate reveal response. Rankings carry current reveal availability;
this avoids mutating the frozen forecast when outcomes mature.

Counts retain zero versus null. Forecast availability is distinct from evidence
status. Only validated intervals belong in forecast responses; experimental
coverage belongs in Evaluation. The adapter supplies numerical values, ordering,
eligibility and scores using Dev 2's policy. The API does no numerical modelling.

Public IDs are bounded opaque identifiers, not filesystem paths. Evidence/report
links are HTTPS without credentials, query parameters or fragments. Storage
locations and signed links must be converted into public report references by the
publisher; never pass them through. Source text is untrusted plain text.

C2 is merged and `api/model_mapping.py` provides tested forecast/evidence mapping.
C3 0.2.0 aligns evidence status to C2 (`validated`, not a superiority claim)
and adds the required feature-row reference. C1 is merged; `api/data_mapping.py` provides typed catalogue/history/coverage
mapping. C3 0.3.0 adds explicit retrospective mapping verification and nullable
freshness timestamps. Numeric forecast evidence remains cutoff-bounded. `PublishedRepository` is the proposed
read/scoring boundary for Dev 1's adapter, not a second persistence system.
Cross-owner mapping approval and real artifact acceptance remain tracked in
https://github.com/bevynfernandes/oxhack2026/issues/1.

C3 0.4.0 adds catalogue `membership_basis`. `decision_time` selects mappings at
the forecast cutoff. `contemporary_reconstruction` explicitly selects at the
frozen catalogue's `recorded_at`, only for reconstructed contemporary cohorts.
The API rejects this membership basis for prospective batches or historical
eligibility cohorts. Actual mapping verification dates remain unchanged and are
independent of the membership-selection basis. The UI displays the survivorship
limitation in both rankings and tool detail.

`tests/fixtures/api/scouting.json` is wholly synthetic, including identities,
measurements, forecasts and comparison values. It is test input only and is never
loaded by production startup. It deliberately demonstrates missing observations,
stale evidence, low reference counts, unavailable forecasts, a baseline win and
failed interval validation. It is not evidence of research performance.
