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
location, hashes and coverage are recorded below.

## Real dataset handoff

Dataset `npm-initial-20261024-v1`: 17,570 selected daily records, ten series,
1,757 complete vendor days per series, zero absent requested days. Measurement
window is `[2022-01-01, 2026-10-24)`. Fifty bounded extraction checkpoints include
actual collection timestamps. npm rate-limited one attempt; the resumed job reused
30 completed checkpoints. A subsequent full rerun produced the identical manifest.

The compressed bundle is attached to the repository's draft release
`data-npm-initial-20261024-v1`, accessible to authenticated collaborators:

```sh
gh release download data-npm-initial-20261024-v1 \
  --repo bevynfernandes/oxhack2026 --dir artifacts/received
cd artifacts/received
shasum -a 256 -c npm-initial-20261024-v1.sha256
unzip npm-initial-20261024-v1.zip -d bundle
cd ../..
uv run --frozen --no-sync python -m oxhack2026 data dataset-validate \
  artifacts/received/bundle
```

ZIP SHA-256: `ce80d3e637b77fec8528ba319c0846d3b41de9414736351daea26508706bf023`.
Manifest SHA-256: `062478ab3a5abe05b04ebf5a68c6bb96ecde5a8f942d4a13927ab6839c25d2f4`.
The 862,703-byte ZIP includes raw responses, normalized Parquet, catalogue,
coverage, source/checkpoint metadata and an already published local index. It has
no credentials. `LocalDatasetStore(Path(root)).bundle("npm-initial-20261024-v1")`
loads its complete validated contents; the C1 reader methods work unchanged.

First positive registry counts vary from 2022 to 2025. Neither first-positive
dates nor vendor zeros prove historical product ownership or eligibility. In
particular, current package names may have earlier usage. This remains a labelled
contemporary reconstruction suitable for the integration path.

Validation after merging current main: `make check test build docs-test` passes
341 unit tests; six explicit filesystem integration tests pass. Local logs and
the saved extraction/transfer checks are retained under
`tests/outputs/dev1-dataset-20261024/`.

## Attribution review correction

The validator now binds each npm series to the canonical package ID and the
hashed extraction request, then checks the package inside the verified raw
response. Reassigning a valid package or forging only the request metadata is
rejected. Regression cases cover both attacks and a noncanonical series ID.
The original real bundle passes the stricter checks unchanged.

New assemblies explicitly pin `downloads-features-v1` / `targets-v1`, matching
Dev 2's definitions. The already published v1 retains its original
`features-v1` / `downloads-v1` metadata; consumers must not silently reinterpret
it. Its frozen extraction run must be replayed with its recorded code revision;
adding configuration fields does not authorize changing the persisted run.

Post-review validation: 344 unit tests and six explicit filesystem integration
tests pass; Ruff and whole-repository mypy pass. Retained logs are under
`tests/outputs/startup-outlook-20261024/`.

A metadata-only `npm-initial-20261024-v2` bundle is now attached to the **same**
draft release `data-npm-initial-20261024-v1`. Download with
`--pattern 'npm-initial-20261024-v2.*'`. It pins the corrected consumer definitions
and records the source manifest plus reissue configuration. All 17,570 observations,
raw bytes, collection times and catalogue mappings are unchanged; v1 is retained.

V2 ZIP SHA-256: `a8f3a4cc2d13dc2e3ee3450e1c507a34f05c279e6432566ccad854e89a781928`.
V2 manifest SHA-256: `c5af606a5e2c3795faf39a4b92623d046e8c01d4e065ab704c0c4a0b0eca4a34`.
The ZIP is 838,296 bytes. Use v2 for the current Dev 2 definition contract; this
is still download evidence, not a startup-outcome model or training cohort.
