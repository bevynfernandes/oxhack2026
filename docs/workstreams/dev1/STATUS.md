# Dev 1 acceptance audit

Updated 2026-10-24 against [issue #19](https://github.com/bevynfernandes/oxhack2026/issues/19).

| Task | Status | Evidence / remaining acceptance |
| --- | --- | --- |
| D1-O1 company contracts | Complete | #28; strict source schemas, timing/identity checks, coverage and exact readers; reviewed by Dev 2/3 |
| D1-O2 multi-family evidence | Complete for initial cohort | #30; real Qdrant/Weaviate source bundle, 14 metrics, ten sources, two funding events; independently downloaded and verified |
| D1-O3 source/assessment publication | Complete | #34/#36; real Dev 2 array published, exact C1/C2 lineage, public-gap/family validation, atomic CAS and retained versions |
| D1-O4 cohort discovery/follow-up | Complete discovery handoff; training data unresolved | #38; all 229 public W20 records, 61 inactive, 34 acquired, 687 unresolved outcome checks; separate primary Datree closure evidence |
| D1-O5 real company flow | Real API complete; browser acceptance pending | Real restored bundle passes API list/both profiles, all three outcomes, redaction and identical process restart; Dev 3 screens remain the browser gate |
| D1-O6 local operations | Local recovery/refresh/runtime verified | #35; safe bounded backup/restore, network-free replay, CLI, frozen configuration, conditional publication; API-only environment and exact factory selection verified; container recipe remains untested |

## Verified handoffs

- Source: `company-vector-20261024-v1`.
- Assessments: `company-assessments-vector-20261024-v1`.
- Combined recovery archive SHA-256:
  `ea92fb6167600d182173b08addeef30a3b78615e1678e97162382fd4a84efb4f`.
- Real collector replay makes no HTTP calls and returns identical bytes.
- Real source/assessment backup restores exact records; corruption fails before
  activation. Synthetic tests additionally cover historical assessment versions.
- Public cohort capture/replay retains every upstream row; independent release
  downloads verify raw hashes and normalized company inventory.
- API-only environment contains no NumPy, sklearn or CatBoost. Readiness, list,
  both real profiles, missing financials, redaction and 404 behavior pass across
  two real server processes with identical response bytes.
- 528 unit tests, 13 data filesystem integrations and the real API integration
  passed after API composition. These are correctness checks, not forecasting
  validation.

## Unresolved external/product gates

- Historical feature vintages, dated ownership and sufficient mature outcome labels
  are not available yet. Directory statuses are discovery leads, not target labels.
- Private revenue/cash flow remains unknown; the user requested public data only.
- The current assessments are evidence-only/unavailable with null probabilities.
- No cloud credentials/credits have been verified. No paid resources were started.
- PostgreSQL migration/restore, TLS, managed scheduling and cloud monitoring are
  not implemented or claimed. The supported current store is local filesystem.
- Docker is unavailable locally; the API container recipe requires a separate
  build/runtime check. Local Python runtime verification is distinct.

## Runbooks

- [Source contracts](../../tasks/dev1/D1-O1-company-source.md).
- [Collection](../../tasks/dev1/D1-O2-company-collection.md).
- [Assessment publication](../../tasks/dev1/D1-O3-assessment-publication.md).
- [Public cohort](../../tasks/dev1/D1-O4-public-cohort-discovery.md).
- [Real assessment handoff](../../tasks/dev1/D1-O5-real-assessment-handoff.md).
- [Recovery/refresh](../../tasks/dev1/D1-O6-local-recovery.md).
