# SignalShift

Company outlooks from dated traction, execution, commercial and financing
evidence. Three separate outcomes cover operating growth, cash-flow
self-sufficiency, and financing/acquisition. The current product organizes
verified evidence and explicit gaps; it does not serve validated probabilities.

## Implemented data path

- Strict company source contracts, effective identities and raw provenance.
- Resumable npm/GitHub/primary-announcement collection and frozen source coverage.
- Immutable source/assessment publication with exact readers and atomic pointers.
- Real two-company evidence/assessment bundle with verified backup and recovery.
- Public 229-company discovery cohort retaining inactive/acquired records and
  unresolved follow-up, plus primary closure evidence for Datree.

## Operations and status

- [Dev 1 acceptance audit](workstreams/dev1/STATUS.md).
- [Company collection](tasks/dev1/D1-O2-company-collection.md).
- [Public cohort discovery](tasks/dev1/D1-O4-public-cohort-discovery.md).
- [Real assessment handoff](tasks/dev1/D1-O5-real-assessment-handoff.md).
- [Recovery and bounded refresh](tasks/dev1/D1-O6-local-recovery.md).

The repository-root PLAN.md defines team scope. Run `make install notebooks
frontend-install` for development and `make check test build docs-test` for shared
Python checks. Run data filesystem acceptance explicitly with
`uv run --frozen --no-sync pytest tests/integration/data -m integration`.
No cloud deployment or predictive calibration is established by these checks.
