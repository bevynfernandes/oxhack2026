# Generated contracts

Python types are the source of truth for the committed contract snapshots:

- [api/](api/README.md): OpenAPI and frontend TypeScript export workflow.
- [datasets/data/](datasets/data/README.md): identities, observations, source
  coverage, manifests and immutable artifact references.
- [datasets/models/](datasets/models/README.md): features, labels, assessments,
  forecasts and evaluation artifacts.

Regenerate affected exports from the repository root:

```bash
uv run --frozen --no-sync python -m oxhack2026.api.export_contract
uv run --frozen --no-sync python -m oxhack2026.storage.export_contracts
uv run --frozen --no-sync python contracts/datasets/models/export.py
npm --prefix frontend run generate:types
```

Saved tests check schema/OpenAPI drift, and frontend builds check generated types.
Review breaking field, version or meaning changes together with their consumers
and fixtures. Keep future labels/reveal payloads separate from features/forecasts.
