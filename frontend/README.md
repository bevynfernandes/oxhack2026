# SignalShift frontend

React, TypeScript, and Vite project template. The only rendered screen is a
static scaffold notice. Product views, routing, API integration, charting,
shortlist state, and forecast behavior are not implemented.

## Development

Use Node.js 24 LTS (`.nvmrc`). After dependencies have been locked, install with:

```bash
npm ci
npm run dev
```

When initially creating or intentionally updating the lockfile, use
`npm install` instead of `npm ci`. Commit `package-lock.json` with dependency
changes.

## Verification

```bash
npm run build
```

The build includes TypeScript checking. Use `npm run typecheck` separately for a
quick check without bundling. `npm run preview` serves the built static template
locally. Unit/browser test
scripts will be added with actual tests rather than returning a false pass.

## Structure

```text
src/
  App.tsx          Static template screen
  main.tsx         React mount
  styles.css       Minimal template styles
  api/             Future OpenAPI types and API client
  components/      Future shared components
  pages/           Future product views
tests/
  unit/            Future component tests
  e2e/             Future browser tests
```

Refer to the repository-root `PLAN.md` for product and interface decisions.
Add routing, query, and chart packages only when their corresponding work starts.
Do not place secrets in browser code or variables prefixed with `VITE_`.
