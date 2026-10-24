# C3 public API contract (0.3.0)

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

`tests/fixtures/api/scouting.json` is wholly synthetic, including identities,
measurements, forecasts and comparison values. It is test input only and is never
loaded by production startup. It deliberately demonstrates missing observations,
stale evidence, low reference counts, unavailable forecasts, a baseline win and
failed interval validation. It is not evidence of research performance.
