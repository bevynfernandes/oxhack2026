# Local company runtime

- For the two packaged Qdrant/Weaviate examples, no restore is needed: leave both
  company root/publication variables unset. The API selects the exact dated
  [real input bundle](../../oxhack2026/catalog/bundled/preloaded_companies_v1/README.md).
  Set `SIGNALSHIFT_PRELOADED_COMPANIES=0` to disable this default.
- For a custom publication, restore its verified bundle using the
  [recovery runbook](../../docs/tasks/dev1/D1-O6-local-recovery.md).
- Custom stores select exact assessment publication IDs. The application never guesses latest,
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
For a local research process with settings in `.env`, use
`uv run --env-file .env --frozen --no-sync uvicorn ...` to load them explicitly.
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

`deploy/local/Dockerfile.api` includes API/data, research and explanation
dependencies plus Chromium, and runs as a non-root user. Training libraries and
source data are excluded; the collection worker requires explicit runtime opt-in.
Build from repository root, mount the verified data root read-only at `/data`,
set the two environment variables above and bind port 8000. Make the mount readable
by UID 10001.

Docker is unavailable in this workspace: this recipe has not passed a container
build/runtime gate. No cloud resources, TLS endpoint, PostgreSQL migration or
managed backup is claimed. Deployment requires verified provider access/credits
and its own acceptance checks.

## On-demand standalone research

Enable the local worker with `SIGNALSHIFT_RESEARCH_ENABLED=1` and mount a persistent,
writable `SIGNALSHIFT_RESEARCH_ROOT` owned by container UID 10001. The root defaults
to `SIGNALSHIFT_COMPANY_ROOT` when set. Standalone research requires no saved company
publications. Use one ASGI process; an exclusive lease prevents two workers sharing
the same research store. The API image includes Chromium; set
`SIGNALSHIFT_RESEARCH_BROWSER=1` to enable its isolated fallback. Keep the artifact
volume when restarting; reports remain readable with collection disabled.

```sh
docker run --rm -p 8000:8000 \
  --mount type=bind,src=/absolute/writable-research-store,dst=/research \
  -e SIGNALSHIFT_RESEARCH_ROOT=/research \
  -e SIGNALSHIFT_RESEARCH_ENABLED=1 \
  -e SIGNALSHIFT_RESEARCH_BROWSER=1 signalshift-api
```

See the [v2 API, limits and provider configuration](../../docs/tasks/dev3/research-v2.md).

## Experimental dimension models

The packaged baseline bundle is verified when the API starts. Saved profiles and
new v2 reports attach separate `dimension_models` metadata. Complete, matching npm
windows support experimental SDK-demand inference. Other dimensions expose trained
status with explicit input, population or quality restrictions; company-outcome
forecasts remain null. No training libraries or pickle are needed for this path.
`SIGNALSHIFT_DIMENSION_MODELS_ROOT` can select a different exact verified portable
bundle. Restart the API after changing the bundle. Existing immutable reports keep
their original contents.

For evidence interpretation, install `--extra research --extra explanations` in
addition to the API/data profile (the API image includes both). Gemini Live
interpretation is enabled by default. Set `SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules`
explicitly for deterministic mapping without model calls. Existing installations
with that override must remove it or set it to `rules_gemini` and restart the API
to enable Gemini interpretation. A personal `GEMINI_API_KEY` overrides
the private repository's backend default; an explicit empty environment value
disables it. `GEMINI_MODEL` changes the model only by explicit configuration.
To re-map existing reports without fetching sources, enable
`SIGNALSHIFT_RESEARCH_MAPPING_ENABLED=1` and keep collection disabled. The same
single-process lease, writable artifact root and durable report rules apply.


Research defaults to the Thorough profile (up to ten minutes); Fast and Deep are
explicit UI choices. Preserve writable captures, source checkpoints and mapping
cache together in the research volume. Continue, Refresh and Re-map create new
reports. Restart the container after updating its image and set
`SIGNALSHIFT_RUNTIME_REVISION` to the deployed commit. Capabilities expose revision,
process start time, resolved profiles and interpretation mode without contacting
providers. Local browser pages and model turns are bounded independently; missing
credentials, rate limits and unverified identifiers remain report limitations.
