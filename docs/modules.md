# Module boundaries

Python module docstrings mark future implementation ownership. They contain
no domain functions, classes, adapters, or service startup code.

| Namespace | Intended responsibility |
| --- | --- |
| `oxhack2026.catalog` | Verified identities and effective-dated mappings |
| `oxhack2026.ingest` | Source extraction and provenance |
| `oxhack2026.storage` | Normalized records, artifacts, atomic publication |
| `oxhack2026.features` | Availability-aware feature and label construction |
| `oxhack2026.models` | Baselines, training, prediction, calibration |
| `oxhack2026.evaluation` | Calendar splits, metrics, experiment manifests |
| `oxhack2026.api` | Read-only API and explicit forecast/reveal contracts |
| `oxhack2026.explanations` | Evidence summaries and optional Gemini adapter |
| `oxhack2026.cli` | Explicit batch and administrative commands |

The frontend reserves API, shared-component, and product-page folders.
Contracts, migrations, and configuration remain documentation-only placeholders
until their owning workstream implements them.
