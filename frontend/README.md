# SignalShift frontend

React/TypeScript company research UI backed by published assessments. Search
companies, inspect three separate outcomes and their dated evidence, and compare
up to three relevant peers. The package forecast/replay workflow remains under
`/traction`; it is not a company-success prediction.

## Development

Use Node 24.22.1 (`.nvmrc`) and the committed lockfile:

```bash
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Start the API separately using the
Dev 3 deployment handoff. Production uses the same origin and needs no browser
credentials or VITE-prefixed environment variables. Without a configured API
repository, the UI shows an explicit unavailable state.

The application never imports test fixtures. The browser test command explicitly
starts a synthetic FastAPI composition under `tests/fixtures/api/server.py`.
Synthetic responses are visibly labelled. They cannot satisfy real-data gates.

## Verification

```bash
npm run check:types
npm run format:check
npm run build
npm run test
npx playwright install chromium
npm run test:e2e
```

Install the root Python API/data extras before browser tests. Playwright launches
both the actual FastAPI routes and Vite, using ports 8000 and 4173; stop existing
development servers on those ports before running it. It deliberately refuses
to reuse an unknown server. Outputs and screenshots are retained under a unique
`tests/outputs/browser-*/` directory. CI uploads them for 14 days.

To keep a running development session available, use separate browser-test ports:

```bash
SIGNALSHIFT_TEST_API_PORT=8011 SIGNALSHIFT_TEST_WEB_PORT=4184 npm run test:e2e
```

The test servers require distinct valid ports and refuse to reuse existing
servers. `SIGNALSHIFT_API_ORIGIN` configures Vite's server-side proxy; the browser
continues using same-origin `/api` requests. It defaults to localhost:8000.

Real company acceptance uses a separate configuration, with no mocked repository:

```bash
export SIGNALSHIFT_COMPANY_ROOT=/absolute/path/to/verified-restored-root
export SIGNALSHIFT_COMPANY_PUBLICATIONS=company-assessments-vector-20261024-v1
SIGNALSHIFT_TEST_API_PORT=8011 SIGNALSHIFT_TEST_WEB_PORT=4184 npm run test:e2e -- --config playwright.company.config.ts
```

The API factory is `oxhack2026.api.company_runtime:create_company_app`. Restore the
checksummed bundle using Dev 1's runbook before starting it. Both environment
variables are server-side; no browser credential or fixture fallback is used.

`npm run generate:types` regenerates TypeScript from `contracts/api/openapi.json`.
Do not edit `src/api/schema.d.ts` or format it with another generator. Prettier
ignores that file. The build fails on generated-type drift.

## Product behavior

- `/` lists explicit assessment snapshots, with name/segment search and
  segment/stage/evidence filters. URL state survives reload and browser Back.
- Profiles show three outcome sections, source-linked statements, metrics grouped
  by family, event stages, source dates/review state and expandable provenance.
- `/compare` accepts two or three distinct companies from the selected snapshot.
  It reuses the same profiles and definitions; stage/model unknowns remain visible.
- Decimal values remain exact strings. Missing, restricted, not-applicable,
  conflicting, stale and observed-zero evidence retain different meanings.
- Current assessments are provisional or unavailable, with no numeric success
  probability. `/methodology` explains requirements for future validated models.
- Tables scroll within their regions on mobile. Controls have keyboard focus;
  comparison headers remain visible while scrolling.

## Retained traction research behavior

- Rankings, eligibility, growth, errors and scores come from the API. Local
  filtering only selects supported ecosystem/target combinations.
- Shortlist IDs are stored per immutable batch and included in the URL when
  changed. Browser storage failure is surfaced without blocking the workflow.
- Scorecards capture the exact submitted selection. Editing after reveal creates
  another card. Cards persist during navigation in this application session;
  selection IDs and the already-revealed flag survive a browser reload. A reload
  never reclassifies a previously revealed batch as a blind selection.
- Actual future values arrive only through the reveal request. The forecast
  cache stays unchanged. Chart data contains observed intervals only; missing
  observations remain gaps. Aggregate forecasts have separate text/table displays.
- Evidence text is escaped. External links are HTTPS, credential-free navigation
  links, never automatically fetched. Evaluation keeps baseline wins, rejected
  challengers, failed intervals and inconclusive findings visible.
- Tables support horizontal scrolling on narrow screens; all controls are
  labelled, keyboard-accessible and compatible with reduced motion. Tests also
  run automated accessibility checks.

## Deployment

`npm run build` writes static assets to `dist/`. Serve at `/` with SPA fallback to
`index.html` for client routes. Proxy `/api/v1/*` to FastAPI before the SPA fallback;
API errors must remain JSON errors. Cache hashed assets immutably; revalidate
`index.html`. Dev 1 owns the reverse proxy, TLS, request limits and resource setup.
No offline export or demo server is included in this workstream.
