# Company evidence builder

`explanations.deterministic.build_company_assessments(snapshot, first_recorded_at)`
consumes an exact `CompanySourceSnapshot` loaded through C1's validated reader.
Raw-byte verification and source adjudication remain C1 responsibilities. The
builder performs no HTTP or persistence operations; Dev 1 owns publication and
Dev 3 projects the resulting C2 records into company list/profile/compare views.

The versioned `company-public-evidence-v1` policy:

- Requires verified public company identity; invalid identity fails explicitly.
- Emits neutral, evidence-linked metric facts with exact values, units and
  product/repository scope. Boolean observations remain yes/no, not scores.
- Keeps missing, conflicting, restricted, unverified and stale measurements as
  explicit gaps; inapplicable definitions do not become gaps. Private values and
  free-form source assertions are excluded from generated statements.
- Uses the frozen cutoff for freshness. A later execution cannot freshen evidence.
- Preserves announcement/completion and event-date distinctions. Product retirement
  is not company shutdown. Explicit supersession removes older event statements;
  restricted/unverified replacement events are withheld rather than asserted.
- Resolves effective family membership from verified public relationships;
  unresolved membership remains explicit.
- Includes all three outcome IDs and calendar horizons. Relevant facts yield
  `evidence_only`; gap-only sections are `unavailable`. Probabilities remain null.

Traction/execution/commercial facts inform the operating section; commercial
facts inform cash-flow self-sufficiency; market/financing facts inform the third
section. This is evidence organization, not a predictive feature-weighting scheme.
The outputs are reconstructed because they are recorded after the source cutoff.
Pin the actual first recording time for retries; source/policy/company/time produce
stable immutable assessment IDs. Source table order does not change results.

## Real integration checkpoint

Verified the ZIP SHA-256 from Dev 1's `data-company-vector-20261024-v1` release and
loaded `company-vector-20261024-v1` through `LocalCompanyStore`. The two nonsynthetic
profiles retain current SDK activity and selected historical financing events.
Both commercial sections remain unavailable; all six commercial gaps survive.
Weaviate's historical financing amount stays stale even though its dated funding
announcement remains visible in the timeline. Neither company has an established
family in this source publication. No success/failure label is inferred.

The builder-produced array is `company-assessments-vector-20261024-v1.json`, with
SHA-256 `39ad67f0a0aaecb1f9d42bc082e76387261f20477d77d9bc23e8aebea2b9d41a`.
The corresponding checksum and local check logs are retained under
`tests/outputs/dev2-company-evidence-20261024/`. Assessment publication validation
and application composition remain separate checkpoints.

Validation: 16 focused tests cover exact values, observed zero, privacy/review,
frozen freshness, applicability, shutdown versus retirement, announcements,
supersession, family unknowns, identity/time rejection and deterministic replay.
