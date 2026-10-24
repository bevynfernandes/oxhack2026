# SignalShift scaffold

This repository contains the project template for SignalShift. Product behavior
is not implemented. The repository-root `PLAN.md` defines the intended system;
`AGENTS.md` defines implementation standards.

## Available now

- Python package namespaces and empty module templates.
- Static React / TypeScript / Vite frontend.
- Dependency manifests and lockfiles.
- Formatting, type-checking, packaging, and scaffold import checks.
- Development container and CI configuration.

## Development

Run `make install notebooks frontend-install` from the repository root.
Use `make check test build docs-test frontend-check` to verify the scaffold.
The only browser preview is `npm --prefix frontend run dev`.

There are no API routes, data ingestion jobs, database migrations, model
implementations, or deployed services yet.
