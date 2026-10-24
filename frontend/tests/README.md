# Frontend verification

`npm run test` runs saved Vitest component/state tests. `npm run test:e2e` runs
Playwright against the actual FastAPI routes using an explicitly synthetic
repository composition. It covers reveal separation, selection freezing,
missingness, escaping, failures, mobile/keyboard behavior and accessibility.
Browser outputs are retained in unique directories under root `tests/outputs/`.
Real artifact integration is a separate gate tracked in GitHub issue #1.
