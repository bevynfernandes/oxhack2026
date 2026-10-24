# Frontend verification

`npm run test` runs saved Vitest component/state tests. `npm run test:e2e` runs
Playwright against the actual FastAPI routes using an explicitly synthetic
repository composition. It covers reveal separation, selection freezing,
missingness, escaping, failures, mobile/keyboard behavior and accessibility.
Browser outputs are retained in unique directories under root `tests/outputs/`.
The company suite also covers search/filter URL state, private/unknown states,
source inspection, invalid snapshots, comparison limits and mobile accessibility.

`npm run test:e2e -- --config playwright.company.config.ts` runs the separate
`tests/real-company/` suite over the actual runtime factory and an explicitly
configured verified root/publication. It checks real list/profile/compare,
financial unknowns, stale metrics, source redaction and immutable reloads.
Set `SIGNALSHIFT_COMPANY_ROOT` and `SIGNALSHIFT_COMPANY_PUBLICATIONS` as documented
in the frontend README. It never downloads or fabricates a source bundle.
