# Research API acceptance — 24 October 2026

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


- Backend: PR #52. Data audit: merged #48; shared model payload: merged #49.
- Python checks: 30 focused research units plus the existing suite; mypy and Ruff.
- Durable integration: completed and partial jobs, retained HTTP bytes, unchanged
  saved links, reopen, idempotent report publication, immutable-ID rejection and
  raw-capture corruption returning 503. Test outputs remain ignored and retained.
- Live provider: real Qdrant identity from
  `company-assessments-vector-20261024-v1`, copied to a separate output root.
  Observed queued, running, partial. HN reported `exhaustiveNbHits: false` with
  zero returned hits; the backend correctly retained a null count rather than
  asserting there were no links. No general sentiment/adoption inference follows.
- Live capture SHA-256:
  `1758b83fe35443e4d251aa60626cec374af3d29b0ed8846169357d6226f5615e`.
  Actual collection: `2026-10-24T17:08:48.995977Z`; window ends
  `2026-10-24T17:08:47Z` (exclusive), starts 30 days earlier.
- Five shared specialist groups resolve saved/fresh IDs; all predictions and
  overall outlook are null. Report bytes remain identical after app restart;
  the existing saved company endpoint remains byte-identical before/after.
- Local retained evidence:
  `/tmp/signalshift-issue46-backend/tests/outputs/research-live/2920c616ef1c47f9b2119b30440cc5f4`.
  Downloaded provider data is not committed to Git.
- Frontend type generation, TypeScript, production build and formatting pass.
  Actual research-job browser acceptance belongs to Ivan's integration after #52;
  this API acceptance does not claim that pending UI already works.
- Known-company scope only. Historical identities/outcome labels remain
  unapproved; all five training gates fail. No model fitting or hosted AI ran.
