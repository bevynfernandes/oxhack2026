# Module boundaries

SignalShift separates source provenance, numerical models, research orchestration
and presentation. Package initializers are lightweight; application factories and
CLI commands select the implementations explicitly.

| Namespace | Responsibility |
| --- | --- |
| `oxhack2026.catalog` | Verified company/tool identities, mappings and availability contracts |
| `oxhack2026.ingest` | Bounded source collection, retained raw captures and checkpoints |
| `oxhack2026.storage` | Local immutable artifacts, validated publications, exact readers and recovery |
| `oxhack2026.features` | Availability-aware company/download features and separate outcome labels |
| `oxhack2026.models` | Baselines, training, model contracts and portable dimension inference |
| `oxhack2026.evaluation` | Temporal splits, outcome metrics, calibration comparisons and shortlist scores |
| `oxhack2026.research` | Identity confirmation, durable jobs, bounded collectors and immutable reports |
| `oxhack2026.explanations` | Deterministic evidence summaries and optional Gemini interpretation |
| `oxhack2026.api` | Application factories, validated HTTP contracts and repository adapters |
| `oxhack2026.cli` | Administrative data collection, publication and model commands |

The React frontend consumes the API through generated TypeScript types and a
same-origin client. Company, research and retained traction routes share the
presentation and motion components. Production startup does not import synthetic
test repositories.

Python contract types generate the committed JSON schemas and OpenAPI export.
Frontend builds check generated-type drift. Models own numerical calculations;
API adapters and UI components present their results and preserve missing values.
Outcome labels and historical reveal responses remain separate from pre-outcome
features and forecasts.

The API/data installation can read publications and load portable model bundles
without training libraries. Research collectors and Gemini interpretation require
their explicit extras and runtime configuration. Storage currently uses local
artifacts and publication records; database/cloud adapters are not implemented.
