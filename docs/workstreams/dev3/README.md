# Dev 3 implementation and integration

Scope: company API, generated client, company list/profile/compare, evidence
presentation and deployment handoff. The active company plan supersedes the
retained download-specific notes below. Demo/export/offline serving is excluded.

## Company runtime

Restore the verified source/assessment archive with Dev 1's `data company-restore`
command. The current real handoff is documented in
[D1-O5](../../tasks/dev1/D1-O5-real-assessment-handoff.md). Keep the original archive,
external checksum and restored root; runtime reads never collect or retrain.

```bash
export SIGNALSHIFT_COMPANY_ROOT=/absolute/path/to/restored-company-root
export SIGNALSHIFT_COMPANY_PUBLICATIONS=company-assessments-vector-20261024-v1
uv run --frozen --no-sync uvicorn oxhack2026.api.company_runtime:create_company_app --factory --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

The application requires explicit canonical assessment publication IDs. Saved
list/profile/compare URLs pin that exact policy publication; the source snapshot
ID remains separate metadata. Multiple policies may use the same source. Retired
selections return 404 and never select another policy. Missing configuration, corrupt
bytes or incompatible source/assessment references stay unavailable. No latest
policy is inferred and no synthetic fixture is loaded. A company-only factory
uses company readiness; legacy download reads remain unavailable unless a
separate legacy repository is injected.

`/` offers explicit snapshot selection, company search and segment/stage/evidence
filters. Filter and up-to-three-company selection state live in the URL. Profiles
are `/companies/{snapshot_id}/{company_id}`; `/compare` reuses those exact profiles.
`/methodology` explains outcome meanings; `/traction` retains package research.

All three outcome sections remain present. Cash-flow self-sufficiency, operating
growth and financing/acquisition are separate targets. The current C2 publication
is evidence-only/unavailable with null probability. The API/browser performs no
numerical assessment or success scoring. Unknown company context and commercial
measurements remain explicit; stale measurements retain their dates.

Public projection removes raw locations, locators, private source assertions and
restricted derived values/events/relationships. Withheld metric states and
coverage are separate from missingness and observed zero. Family resolution uses
public evidence only. External text is escaped and links are navigation only.

## Company verification and handoff

```bash
uv run --frozen --no-sync pytest tests/unit/api
npm --prefix frontend run build
npm --prefix frontend run test
SIGNALSHIFT_TEST_API_PORT=8011 SIGNALSHIFT_TEST_WEB_PORT=4184 npm --prefix frontend run test:e2e
uv run --frozen --no-sync pytest -m integration tests/integration/api/test_real_company_api.py
SIGNALSHIFT_TEST_API_PORT=8011 SIGNALSHIFT_TEST_WEB_PORT=4184 npm --prefix frontend run test:e2e -- --config playwright.company.config.ts
```

The last two commands require the real-root/publication variables above. The
default browser suite uses explicitly synthetic mocked readers; the separate
real configuration launches the actual environment-configured API. Test servers
refuse occupied ports. Production static assets are `frontend/dist`; route `/api`
to FastAPI before SPA fallback. `SIGNALSHIFT_API_ORIGIN` changes Vite's server-side
proxy target without putting credentials into browser configuration.

Real acceptance uses Qdrant and Weaviate with multiple metric families, all three
sections, six commercial gaps, unresolved families and dated/stale financing.
The combined archive SHA-256 is
`ea92fb6167600d182173b08addeef30a3b78615e1678e97162382fd4a84efb4f`.
Real API reads and list/profile/compare browser tests pass. Screenshots and test
reports are retained under `tests/outputs/browser-company-real-final-20261024/`; source
archive, checksum and restored bytes are in `tests/outputs/dev3-company-real-20261024/`.
These are evidence-product checks, not model calibration or cloud deployment.

Dev 1 owns shared environment/container/CI/deployment wiring. Dev 2 owns labels,
assessment generation, models/evaluation and probability eligibility. Dev 3's
completion does not assert those separate research/operational gates are done.

## Historical download API handoff

```bash
uv sync --frozen --inexact --all-extras --group docs
uv run --frozen --no-sync uvicorn oxhack2026.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

This default starts liveness and OpenAPI, with 503 readiness/data reads. There is
no synthetic fallback, live vendor call, training or inference. No API-specific
credential environment variables are required. Dev 1 supplies storage interfaces and pool lifecycle. Dev 3 composes the API
adapter over those interfaces; Dev 1 wires its factory into runtime startup. Do not use this unconfigured factory as a ready
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

C1, C2 and numerical policy are now merged. The production repository, published
forecast reads and real datasets still require their upstream implementation. D3-05 cannot pass with synthetic fixtures. Required:
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

Dev 2 now supplies per-tool diagnostics via `outcome_diagnostics`. The API maps
those values without calculating formulas itself. Baseline orderings and
tie-aware comparator scores must also come from the model workstream.

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

Remaining: production repository/runtime composition, mapping cross-review, actual frozen
npm artifacts, full real-data replay and performance/operational gates. API and UI
are implemented and fixture-tested; D3-05 remains blocked by that upstream handoff.
Demo/export/offline-serving work remains explicitly excluded.

## C1 integration and C3 0.3.0

C1 is now merged. `api/data_mapping.py` presents verified effective catalogue
mappings, exact selected observation vintages and public source coverage.
`map_history` rejects wrong package/series identities, future availability,
late prospective collection and multiple vintages for the same day. It does not
select a new revision or fill missing observations with zero.

C3 0.3.0 allows an unknown freshness timestamp to remain null. It also preserves
C1's actual catalogue recording and mapping inspection dates. Reconstructed
catalogue evidence verified after the decision is explicitly retrospective in
the API and UI; prospective catalogues reject it. This narrow mapping-provenance
exception does not apply to numeric forecast evidence, which remains bounded by
the observation and decision cutoffs.

Dev 2's `outcome_diagnostics` is now available. `map_outcomes` delegates per-tool
growth/errors to it; `map_reveal` combines those diagnostics with the shared
shortlist scorer, exact outcome vintage and same-universe comparators. Missing
outcomes stay null and incomplete eligible universes return 409.

Dev 1 owns the actual storage implementation and application lifecycle. Dev 3
owns the adapter composing those storage reads with these pure C1/C2 mappings.
Remaining production dependencies are batch enumeration, forecast/evidence/
evaluation/outcome reads, selected history-vintage publication and real npm
artifacts. No parallel persistence or numerical implementation is introduced.

## Contemporary catalogue integration

PR #17 supplies an exact-version local dataset reader and a transferable real npm
bundle. Its catalogue mappings start at their actual 2026 inspection date. For a
reconstructed batch explicitly using this contemporary cohort, the composition
must call `map_catalog(snapshot, batch, allow_contemporary_reconstruction=True)`.
This selects effective mappings at `snapshot.recorded_at` and sets C3 0.4.0
`membership_basis` to `contemporary_reconstruction`. Strict cutoff-based mapping
selection remains the default. The opt-in is rejected for prospective batches
and historical-eligibility cohorts; dates and version checks are retained.

The API and both catalogue views expose that historical membership is unverified
and subject to survivorship bias. Membership selection and evidence inspection
are separate facts: old evidence may still be genuinely available before the
cutoff even when a cohort is selected retrospectively.

The real dataset archive and manifest hashes were independently checked during
review of #17, and its published bundle loaded with ten series and 17,570 daily
observations. The source-package attribution review finding remains with Dev 1.
C2 forecast/evaluation/outcome publication and production API composition are
still required for D3-05; the dataset alone is not a complete real-data replay.
