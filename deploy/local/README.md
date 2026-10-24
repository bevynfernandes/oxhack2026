# Local company runtime

- Restore the verified company bundle using the [recovery runbook](../../docs/tasks/dev1/D1-O6-local-recovery.md).
- Select exact assessment publication IDs. The application never guesses latest,
  loads synthetic fallback data, collects sources or trains models.
- Dev 3 owns the shared API factory and its readiness behavior. Missing
  configuration leaves company data unavailable; no fixture fallback is selected.

## Run the API

```bash
uv sync --frozen --no-dev --extra data --extra api
export SIGNALSHIFT_COMPANY_ROOT=/absolute/path/to/restored-company-store
export SIGNALSHIFT_COMPANY_PUBLICATIONS='company-assessments-vector-20261024-v1'
uv run --frozen --no-sync uvicorn oxhack2026.api.company_runtime:create_company_app \
  --factory --host 127.0.0.1 --port 8000
```

Use a separate environment for development/model tests. API configuration reads
only explicit environment variables; it does not implicitly load `.env` files.
The API dependency profile excludes model-training libraries. Mount the publication
root read-only for an API worker; use a separate writer for refresh and recovery.

- Liveness: `/api/v1/health/live`.
- Readiness: `/api/v1/health/ready`.
- Published snapshots: `/api/v1/company-snapshots`.
- List: `/api/v1/company-snapshots/company-vector-20261024-v1/companies`.
- Profile: append `/qdrant` or `/weaviate` to that list URL.
- Compare: Dev 3's UI reuses the exact two profiles from one selected snapshot.
- Access logs go to the process console. Source payloads, secrets and raw artifact
  paths must not be added to public responses or error messages.

Verified locally with the real restored two-company bundle: readiness, list,
both profiles, all three outcomes, missing financials, redaction and unknown-ID
responses. Two separate API processes return identical publication bytes.
The dedicated API-only environment contains no training libraries.

Restart the process with the same root/IDs to reproduce the same publications.
To roll back, restore/select a previous verified bundle; never edit frozen bytes.
The current evidence assessments are reconstructed and contain no probabilities.

## Container recipe

`deploy/local/Dockerfile.api` packages only the API/data profile and runs as a
non-root user. It excludes collector/model jobs and source data from the image.
Build from repository root, mount the verified data root read-only at `/data`,
set the two environment variables above and bind port 8000. Make the mount readable
by UID 10001. The root Dockerfile remains a development shell.

Docker is unavailable in this workspace: this recipe has not passed a container
build/runtime gate. No cloud resources, TLS endpoint, PostgreSQL migration or
managed backup is claimed. Deployment requires verified provider access/credits
and its own acceptance checks.
