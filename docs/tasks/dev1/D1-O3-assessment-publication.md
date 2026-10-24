# D1-O3: source-bound company assessment publication

`storage.company_assessments.CompanyAssessmentReader` supplies the Dev 3
publication boundary. `LocalCompanyAssessmentStore(root)` reads/writes the same
artifact root as `LocalCompanyStore`; the source publication must already exist.

- `publications()` enumerates verified public-safe batch metadata.
- `manifest(publication_id)` returns the exact internal pinned manifest.
- `assessments(publication_id)` reads the complete published C2 company array.
- `company(publication_id, company_id)` selects an exact company, never a fallback.

`publish(publication_id, assessments, expected_current)` validates the complete
source-company set, unique assessment IDs, one model policy, exact source cutoff,
synthetic status, first-recorded bounds and effective family resolution. Statement
references must belong to the same company and include the evidence supporting
referenced observations/events. Source snapshot IDs and their hash-pinned manifest
must agree. The published content is sorted deterministically and an identical
retry is idempotent. CAS, immutable IDs and previous readable versions follow the
source-store rules. Reads verify C2 bytes and the underlying C1 raw evidence.

Publication metadata `recorded_at` is the latest model `first_recorded_at`, not an
invented forecast time. This checkpoint aligns assessment and source cutoffs and
supports the current reconstructed evidence-assessment handoff. It does not
implement a future prospective forecasting publication or a probability gate.
The C2 owner produces the statements/interpretation; this layer only validates
and stores them. Outcome truth remains separate and is never merged into source
or pre-outcome assessment payloads.

```sh
python -m oxhack2026 data assessment-publish \
  artifacts/company-root exact-batch-id /path/to/model-produced-assessments.json
python -m oxhack2026 data assessment-health artifacts/company-root exact-batch-id
```

Unknown IDs raise KeyError; incompatible/corrupt content raises ValueError;
filesystem failure raises OSError. No vendor collection, source refresh, model
training or synthetic fallback occurs in the read path. The public API must
project these records and exclude internal artifact locations/restricted data.

Saved synthetic C1/C2 composition fixtures exercise successful reads and rejection
of wrong source/company/family/time/synthetic identity, missing support, mixed
policies and incomplete company coverage. Opt-in filesystem tests cover exact
reads, repeated publication, failed pointer writes, lost CAS and raw corruption.

For Dev 3's source-scoped read port, inject
`SourceScopedAssessmentReader(store, ("explicit-publication-id",))`. It implements
`snapshot_ids()` and `assessments(source_snapshot_id)`. The configuration selects
one exact assessment policy publication per source; ambiguous duplicate source
selections fail. Publishing a newer policy never changes this selection. This
adapter contains no model policy or public DTO mapping.
