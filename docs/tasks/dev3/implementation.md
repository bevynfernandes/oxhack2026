# Dev 3 checkpoints

## Active company-outlook acceptance

The active scope is [PLAN.md](https://github.com/bevynfernandes/oxhack2026/blob/main/PLAN.md)
and D3-O1 through D3-O5 in
[the role plan](https://github.com/bevynfernandes/oxhack2026/blob/main/plans/DEV_3_API_FRONTEND.md). Demo/export/offline serving
is excluded. The original download checklist below is historical.

| Checkpoint | State | Evidence |
| --- | --- | --- |
| D3-O1 visual system | Merged | #21 neutral surfaces, compact navigation/tables; #27 methodology and exact outcome wording |
| D3-O2 public API/client | Merged | #32 C1/C2 projection, privacy and generated types; #41 canonical assessment publication URLs |
| D3-O3 list/profile/compare | Implemented and verified | Company landing, URL search/segment/stage/coverage filters, exact profiles and two-to-three-company comparison |
| D3-O4 real adapter | Merged | #32 storage composition, #39 local runtime; #41 exact policy selection and rollout/retirement regression |
| D3-O5 real acceptance | Verified locally | Restored Qdrant/Weaviate C1/C2 bundle, real API/browser, all three outcomes, four metric families, mobile/keyboard/axe |

Validation after publication pinning and main integration: 562 Python tests
(including 104 API cases), real API
acceptance, 14 frontend unit tests, 12 browser cases and one separate real-data
browser flow. Ruff, mypy, generated-contract drift, TypeScript, formatting and
production frontend build pass. Reports/screenshots are retained under ignored
`tests/outputs/`; [the runtime handoff](../../workstreams/dev3/README.md) records
the immutable archive checksum, configuration and reproducible commands.

The real data contains two companies, fourteen metric observations and six
missing commercial measurements. Unknown stage/business model/family and stale
financing remain visible. No validated probability, overall success score,
future label, private attachment contents or private derived measurement is
served. This proves the evidence-product checkpoint; historical modelling and
operated cloud deployment remain separate owners' gates.

## Product scope revision

The user redirected the product to multi-metric startup success/failure assessment
on 2026-10-24. [Issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19)
coordinates source/outcome contracts and the shared specification update, owned
by Dev 1. The checklist below describes reusable implementation from the original
download-scoping phase; it is not completion of the revised product.

The current Dev 3 design and dependency sequence are documented in
[STARTUP_OUTLOOK.md](../../workstreams/dev3/STARTUP_OUTLOOK.md). Immediate work:
restrained visual revision, company list/profile/compare, agreed additive C3
contracts, production multi-family company reads and real browser acceptance.
Unknown/private metrics and unvalidated outcome probabilities remain explicit.

The neutral visual foundation shipped in #21. The additive `/methodology` page
explains the three calendar-horizon outcomes, cash-flow self-sufficiency,
evidence-only versus validated assessments, source timing and incomplete
follow-up. It works without a published repository and makes no claim that a
company prediction model is available. The company landing/profile/compare
checkpoint now consumes the concrete C1/C2 classes and real storage readers.
#23 and #25 established their specification; #28, #31/#34 and #33 delivered
source, storage and assessment generation.

## Reusable original checkpoints

| Task | State | Evidence / dependency |
| --- | --- | --- |
| D3-01 C3 | Implemented, C1 mapping review pending | Pydantic/OpenAPI/generated TypeScript; synthetic fixtures; C2 mapping tests |
| D3-02 API/UI | Implemented against injected reads | Ten routes, unavailable startup, safe failures, contract drift checks |
| D3-03 rankings/detail | Implemented | Exact batch selection, one representative per selection, baseline/exclusion states, bounded history |
| D3-04 replay/evaluation | Implemented | Separate outcomes, immutable scorecards, shared scorer, explicit evidence limitations |
| D3-05 real artifacts | Blocked upstream | Production reads and real published npm batch unavailable; GitHub issue #1 |
| D3-06 evidence/health/accessibility | Implemented | Escaped evidence, source quality, keyboard/mobile/reduced motion, automated accessibility checks |
| D3-07 deployment handoff | Documented | API factory/ports, static build/proxy, readiness, tests and prerequisites |
| D3-07 demo/export/offline | Excluded | Explicit developer instruction |

No source extraction, cloud provisioning, numerical training or paid calls were
performed. PLAN.md is unchanged. Synthetic values are never research evidence.

PR #2 delivered the API checkpoint and merged after CI passed. Dev 3 consumed C2
from PR #3 and the policy checkpoint from PR #4 through main. PR #7 delivers the frontend and C2 presentation adapters. Integration checks
include the other developers' merged model/baseline tests.

The unconfigured production factory always fails readiness/data reads. Only the
explicit test composition loads fixture files. Dev 1 must supply and lifecycle-
manage the production read repository; it must verify artifact/schema/checksum
compatibility before returning ready. The final real-data gate is not waived by
passing synthetic browser tests.

C1 and C2 presentation mapping now use C3 0.3.0. Retrospective mapping inspection
is labelled explicitly; per-tool outcome diagnostics delegate to Dev 2. The next
checkpoint closes contract-mapping gaps without claiming real-data completion.

C3 0.4.0 adds an explicit contemporary-membership opt-in for reconstructed
catalogues, with survivorship notices on rankings and tool detail. PR #17 now
provides the real npm dataset handoff and local exact-version C1 reads; its ZIP
and manifest checksums were independently verified. Source-package validation
review, C2 publication and production API composition remain outstanding.
