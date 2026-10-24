# D1-02b / D1-03a: verified npm candidate and local publication

The initial catalogue freezes ten official npm mappings across six categories.
Selection precedes historical download extraction. Package migrations are not
spliced, LlamaIndex.TS is retained as deprecated, and Langfuse's current family is
ClickHouse. This is a contemporary reconstruction with current inspection dates,
not a dated historical discovery cohort. Earliest historical tool eligibility is
unknown; source zeros do not establish that a product existed.

The pipeline uses four request workers, explicit 365-day chunks and persisted
per-request checkpoints. Run IDs bind exact catalogue/dates/code. Retry uses the
same raw bytes and revision IDs. Use a new run ID for an intentional source refresh.

`storage.build.write_candidate` writes JSON catalogue/series/coverage and Parquet
observations. Parquet types retain Int64 counts, nulls and UTC microsecond instants.
Cross-artifact validation checks identities, source/policy provenance, raw hashes,
exact coverage and one selected revision per series/day. No publication is inferred
from a successful vendor request.

`LocalDatasetStore` implements the C1 readers and filesystem publisher. It validates
all artifacts, locks a local index, compares the expected current dataset and
atomically advances the pointer. Old version references remain readable; repeated
identical publication is idempotent. Index failures before rename leave the old
pointer in place. A durability error after rename requires reconciliation by
reading the index; retry does not blindly republish.

Readers always select an explicit dataset. Observation queries apply both assumed
availability and optional actual-collection cutoffs without substituting vintages.
Dev 3 can use `series(version)` and `bundle(version)` without parsing files.

CLI: `uv run --frozen --no-sync python -m oxhack2026 data --help`.
Available commands: `catalog-validate`, `extract-npm`, `dataset-validate`, `publish`,
`artifact-verify`, and `health`. Extraction takes catalogue, output root and a JSON
`NpmRun`; publication takes an explicit expected-current value when replacing a
previous dataset.

This checkpoint does not implement PostgreSQL migrations, forecast/outcome storage,
scheduled model jobs, the model-owned baseline generation, or the API-owned adapter.
It is a working local dataset layer, not completion of every Dev 1 task. Real-bundle
location, hashes and coverage will be recorded here after extraction/verification.
