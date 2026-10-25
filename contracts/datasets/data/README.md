# C1 generated data schemas

Source types live in `oxhack2026/catalog/schemas.py` and
`oxhack2026/storage/contracts.py`. Regenerate from the repository root with:

```sh
uv run --frozen --no-sync python -m oxhack2026.storage.export_contracts
```

`tests/unit/data/test_data_contracts.py` checks drift. See
[the archived C1 handoff](../../../docs/archive/workstreams/dev1/C1.md) for
availability semantics, consumer mapping,
serialization and implementation boundaries. Contracts are lightweight and
perform no storage, network, model-training or paid-service initialization.
