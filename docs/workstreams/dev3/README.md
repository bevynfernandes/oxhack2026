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

Dev 1/2 have not yet published a real dataset, C1/C2 contracts or a repository
implementation on main. D3-05 cannot pass with synthetic fixtures. Required:
real npm catalog/observations, immutable batch/rankings/evidence/evaluation,
mature outcomes, scorer, artifact hashes and portable retrieval instructions.
The full no-vendor-call browser replay must be rerun against that composition.
No LOCAL_COMPLETE or cloud-deployment claim is made by these fixture checks.
