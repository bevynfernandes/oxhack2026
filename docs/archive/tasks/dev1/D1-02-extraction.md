# D1-02a: bounded npm extraction and local raw artifacts

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


Owner: Dev 1. Branch: `codex/dev1-npm-ingestion`. No dependencies added.

`ingest.npm` accepts one canonical npm package and explicit UTC dates, splits
long ranges into at most 365-day requests, and encodes scoped package paths.
Inclusive vendor dates become half-open daily C1 windows. Returned zero counts
remain zero; missing dates become null observations and incomplete coverage.

Raw responses have a 2 MiB limit. Requests use a 20-second timeout, at most three
attempts for transport/429/5xx errors, and bounded jittered backoff. Retry-After
over 60 seconds defers the job. Permanent HTTP and malformed-payload failures do
not retry. The caller owns concurrency and must persist returned checkpoints.

`NpmCheckpoint` pins the exact request, retrieval time, raw size and SHA-256.
Passing it to `fetch_range` replays the same revision IDs without HTTP. A fresh
retrieval creates a distinct extraction/revision vintage; this adapter does not
yet reconcile supersedes links or persist a checkpoint/job ledger.

`FileArtifactStore` writes content-addressed bytes with fsync and atomic rename,
verifies reads and repeated writes, limits size, and rejects resolved paths
outside its root. This is raw artifact storage, not dataset pointer publication.

Availability retains the plan's explicit 48-hour assumption and actual collection
time separately. Vendor publication is unknown. Contemporary catalogue evidence
does not establish historical eligibility; no pre-release eligibility is inferred
from vendor zero counts.

Validation covers scoped URLs, inclusive boundaries, leap-year chunking,
zero/missing records, invalid payloads, corruption, replay, fresh vintages,
rate limits, transport failures and oversized responses. Opt-in filesystem tests
exercise concurrent identical writes, corruption rejection and symlink containment.

A saved live smoke retrieved seven days (2024-01-01 through 2024-01-07 inclusive)
for the officially documented `@qdrant/js-client-rest` package and replayed it
identically. Raw SHA-256:
`fb120bd1affa1a885209d58e0e74121e7817652b976b8d0663c53dbe61e87d3b`.
Local smoke artifacts and verification logs are retained under ignored
`tests/outputs/dev1-npm-20261024/`; this is not a transferable dataset handoff.

Next: freeze the verified ten-tool catalogue, persist extraction checkpoints,
produce the real candidate bundle and coverage report, then implement validated
dataset publication. Official review found deprecated/replaced packages in the
initial candidate list; current mappings must be recorded without splicing old
and new package histories.
