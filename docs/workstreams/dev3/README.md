# Dev 3 implementation and integration

Scope: API, generated contracts, scouting UI, historical reveal, evaluation,
evidence/data health and deployment handoff. Demo export and offline serving are
excluded by the developer's instruction. PLAN.md is unchanged.

## API startup

```bash
uv sync --frozen --inexact --all-extras --group docs
uv run --frozen --no-sync uvicorn oxhack2026.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

This default starts liveness and OpenAPI, with 503 readiness/data reads. There is
no synthetic fallback, live vendor call, training or inference. No API-specific
credential environment variables are required. Dev 1 supplies a composition
factory calling `create_app(repository)` after constructing the actual read
adapter and owns pool shutdown. Do not use this unconfigured factory as a ready
production release.

Implement the port in `oxhack2026/api/repository.py` using existing storage reads
and Dev 2's lightweight scorer. Validate DTOs at the adapter boundary. Translate
unknown resources to `ResourceNotFound`, immature outcomes to `ImmatureOutcome`,
and storage/checksum/schema failures to `RepositoryUnavailable`. Public health
reasons must be stable safe descriptions, never raw database errors or URLs.

The adapter must enforce publication completeness, outcome availability and
immutable artifact hashes. The API additionally checks requested IDs, compatible
versions, unique ranked organizations, history/evidence boundaries, and exact
score-to-selection correspondence. Target definitions, Monday alignment, the
48-hour lag, ranking thresholds and score formulas remain Dev 2's responsibility.
Catalog reads with a batch ID must use that batch's frozen mapping and evidence.

GET `/api/v1/health/live` is process-only. GET `/api/v1/health/ready` requires the
actual schema, storage and artifact checks. All data routes require the adapter.
Run behind Dev 1's same-origin reverse proxy, with TLS and request/body limits.
No cross-origin permissions are enabled by default. Do not expose DB credentials
or signed artifact URLs in DTOs or browser environment variables.

## Checkpoint D3-01 / D3-02

- Ten public routes, strict request/response contracts and safe error mapping.
- Separate forecast and reveal types; no future actuals in pre-reveal graphs.
- Generated OpenAPI and TypeScript with reproducible drift checks.
- Mocked API tests and saved labelled synthetic fixtures.
- Minimal shared CI adjustment: install already-declared runtime extras so global
  imports/type checks work as planned in the team bootstrap. No root dependency,
  storage or numerical-policy changes.
- C3 mapping is provisional pending C1/C2 review (GitHub issue #1).

Verification: `make check test`, `npm --prefix frontend run build` and
`python -m oxhack2026.api.export_contract --check` in the installed environment.

## Remaining integration gate

The model contracts and numerical policy are now merged. Dev 1 has not yet
published C1, a real dataset or a repository implementation on main. D3-05 cannot pass with synthetic fixtures. Required:
real npm catalog/observations, immutable batch/rankings/evidence/evaluation,
mature outcomes, scorer, artifact hashes and portable retrieval instructions.
The full no-vendor-call browser replay must be rerun against that composition.
No LOCAL_COMPLETE or cloud-deployment claim is made by these fixture checks.

## D3-03 / D3-04 / D3-06 and deployment handoff

Implemented views: exact ecosystem/target/cutoff selection, published rankings,
manual shortlist, baseline/exclusion panels, tool identity/history/evidence,
aggregate forecast/interval display, separate historical reveal, evaluation and
data health. The UI supports keyboard use, reduced motion and narrow screens.
Source text is escaped, missing counts stay null, and tests cover baseline wins
and rejected interval validation.

C2 and numerical policy are now merged. `api/model_mapping.py` maps the shared
forecast/evidence artifacts without changing numerical values. It rejects mixed
scope/version metadata, missing or wrong-tool evidence, unsafe links and future
availability. C3 0.2.0 exposes the feature-row ID and C2 `validated` status; that
label does not imply statistical superiority.

`api/numerical_policy.py` calls `rank_forecasts` and `score_shortlist` directly.
The storage composition supplies frozen representatives and the exact candidate
universe. `score_selection` enforces outcome availability as of request time and
raises `ImmatureOutcome` for an incomplete universe. Its returned first score is
mean log growth; place later scores in `Reveal.selection_metrics`. Published
comparator scores remain separate. No calculations are implemented in the API.

C2 currently provides actual counts but no per-tool growth/error diagnostic
artifact. Those public fields must remain null until Dev 2 supplies them. Do not
infer missing diagnostics in the storage adapter or browser. Baseline orderings
and tie-aware comparator scores must also come from the model workstream.

Run the frontend with `npm --prefix frontend run dev`. Vite proxies `/api` to
localhost:8000; production serves `frontend/dist` at `/`, with SPA fallback after
the `/api/v1` proxy. No VITE credential variables are used. See frontend/README.md
for same-origin serving, caching and startup requirements.

Browser verification uses **actual API routes plus a mocked synthetic repository**:

```bash
npm --prefix frontend run test
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

The explicit fixture composition is only in tests/fixtures/api/server.py and is
not packaged or imported by production startup. Playwright starts both servers,
uses local HTTP only, and retains screenshots/traces in unique tests/outputs
folders. CI installs the API/data extras and Chromium for this job and uploads
those artifacts. CI configuration is the second minimal shared integration
exception; Dev 1 retains responsibility for service/deployment integration.

Selection IDs and the already-revealed flag persist per batch in browser storage.
Frozen scorecards remain in the current application session, including navigation
between screens. Reloading retains awareness of an earlier reveal and selected
IDs, but discards the in-memory scorecards. Browser state is for personal scouting,
not an authenticated prospective research ledger.

Remaining: C1 repository/runtime composition, mapping cross-review, actual frozen
npm artifacts, full real-data replay and performance/operational gates. API and UI
are implemented and fixture-tested; D3-05 remains blocked by that upstream handoff.
Demo/export/offline-serving work remains explicitly excluded.
