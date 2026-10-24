# Dev 3 checkpoints

| Task | State | Evidence / dependency |
| --- | --- | --- |
| D3-01 C3 | Implemented, C1 mapping review pending | Pydantic/OpenAPI/generated TypeScript; synthetic fixtures; C2 mapping tests |
| D3-02 API/UI | Implemented against injected reads | Ten routes, unavailable startup, safe failures, contract drift checks |
| D3-03 rankings/detail | Implemented | Exact batch selection, one representative per selection, baseline/exclusion states, bounded history |
| D3-04 replay/evaluation | Implemented | Separate outcomes, immutable scorecards, shared scorer, explicit evidence limitations |
| D3-05 real artifacts | Blocked upstream | No merged C1 repository or real published npm batch; GitHub issue #1 |
| D3-06 evidence/health/accessibility | Implemented | Escaped evidence, source quality, keyboard/mobile/reduced motion, automated accessibility checks |
| D3-07 deployment handoff | Documented | API factory/ports, static build/proxy, readiness, tests and prerequisites |
| D3-07 demo/export/offline | Excluded | Explicit developer instruction |

No source extraction, cloud provisioning, numerical training or paid calls were
performed. PLAN.md is unchanged. Synthetic values are never research evidence.

PR #2 delivered the API checkpoint and merged after CI passed. Dev 3 consumed C2
from PR #3 and the policy checkpoint from PR #4 through main. The frontend and
C2 presentation adapters form the following Dev 3 checkpoint. Integration checks
include the other developers' merged model/baseline tests.

The unconfigured production factory always fails readiness/data reads. Only the
explicit test composition loads fixture files. Dev 1 must supply and lifecycle-
manage the production read repository; it must verify artifact/schema/checksum
compatibility before returning ready. The final real-data gate is not waived by
passing synthetic browser tests.
