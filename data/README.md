# Data layout

- `catalog/`: versioned source identities, cohort records and discovery follow-up.
- `raw/`: ignored source captures and extraction manifests.
- `processed/`: ignored published datasets and derived feature/label artifacts.

Collection, immutable publication and recovery are implemented in
`oxhack2026/ingest` and `oxhack2026/storage`. Collection recipes live in
`configs/data`; runtime roots are selected explicitly rather than inferred from
these directory names. See the [local runtime runbook](../deploy/local/README.md)
and [recovery procedure](../docs/tasks/dev1/D1-O6-local-recovery.md).

Generated observations and publication bundles stay out of Git. Synthetic test
inputs belong in `tests/fixtures` and retain their synthetic provenance.
