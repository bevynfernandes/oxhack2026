# Real C1/C2 publication handoff

The real source `company-vector-20261024-v1` and Dev 2's
`company-public-evidence-v1` assessments now publish together. Raw source and
assessment checksums, exact ID reads, backup and restored reads pass. Neither
company is synthetic. Commercial outcomes remain unavailable; all probabilities
remain null. Public gaps may refer to observed-but-stale/restricted/unreviewed
source metrics: storage verifies their IDs and leaves usability policy to C2.
Fact/risk statements must include evidence supporting their referenced facts.
Public assessment family validation uses `resolve_family(..., public_only=True)`;
source readers can still resolve restricted ownership for authorized use.

Download `company-outlook-vector-20261024-v1.zip` and its checksum from the existing
draft release `data-company-vector-20261024-v1`. This recovery archive contains
published source/assessment graphs, not collector checkpoints or credentials.

- ZIP SHA-256: `ea92fb6167600d182173b08addeef30a3b78615e1678e97162382fd4a84efb4f`
- Source ID: `company-vector-20261024-v1`
- Assessment publication ID: `company-assessments-vector-20261024-v1`
- Dev 2 input array SHA-256:
  `39ad67f0a0aaecb1f9d42bc082e76387261f20477d77d9bc23e8aebea2b9d41a`

Restore with `python -m oxhack2026 data company-restore ZIP NEW_ROOT SHA256`.
Set `SIGNALSHIFT_COMPANY_ROOT=NEW_ROOT` and
`SIGNALSHIFT_COMPANY_PUBLICATIONS=company-assessments-vector-20261024-v1`, then
serve `oxhack2026.api.company_runtime:create_company_app` with Uvicorn's factory
mode. API routes select the exact assessment publication ID, retaining the source
snapshot separately; retired selections fail rather than resolving another policy.

- Source/assessment publication, real API and real browser acceptance are complete.
- Readiness, list, both profiles, three outcome sections, missing financials,
  privacy and 404 checks pass in the API-only environment. Restarting the actual
  server reproduces identical response bytes.
- #44/#45 browser integration at `6cf7f66` passes real company search, list,
  profile, source inspection and comparison, including mobile/keyboard and axe
  checks. Commercial measurements remain unknown and probabilities remain null.
- Retained browser evidence: `tests/outputs/company-first-ui-real/`; details are
  in the [Dev 1 acceptance audit](../../archive/workstreams/dev1/STATUS.md).
- Fresh research and the broader prediction proposal in #46 are separate gates;
  this verifies the existing saved-assessment application only.
