# Company evidence assessment interchange

`models.company_assessments` supplies the pre-outcome handoff for the company
list/profile/compare workflow in #19. `CompanyAssessment` pins company/family,
source publication, policy, cutoff, recording time, mode and synthetic status.
It contains all three outcome sections, including unavailable ones, and separate
source-linked observation/risk/gap statements.
Unresolved family ownership stays null with explicit reasons rather than removing
the company. Source-to-label/training eligibility must separately require the
family identity needed for leakage controls.

Every fact or risk needs C1 evidence IDs. A gap identifies its missing/conflicting
metric definitions. Internal statement IDs must resolve uniquely. An outcome
with only gaps stays unavailable; observed facts produce an evidence-only section.
Calendar horizons match the shared outcome definitions. A later reconstruction
cannot be presented as an assessment recorded before its cutoff.

This first `company-assessments-v1` version supports `evidence_only` and
`unavailable`, with `probability` constrained to null. The planned
`validated_probability` state needs a separate validated prediction publication
and release gate; this version deliberately cannot serve it. This is a contract
for the first evidence-product checkpoint, not completion of outcome research.
Source metrics/events remain C1 records, and future truth remains the separate
`CompanyOutcomeLabel` contract. There is no overall success score.

The producer must validate all C1 foreign keys, company/family attribution,
definition semantics, source dates, actual collection, source snapshot and
synthetic status before composition. The schema cannot establish those facts.
Statements must be generated from the versioned deterministic assessment policy;
the contract does not make arbitrary prose reliable.

The saved synthetic profile demonstrates explicit commercial unknowns alongside
traction and financing evidence. Saved tests reject probability/label injection,
missing sections, unresolved statements, unsupported warnings, gap-only claims
and inconsistent dates. It is not real company evidence or model performance.

Validation: Ruff, mypy and 420 Python unit tests pass; six opt-in integrations
remain excluded. Logs are under `tests/outputs/dev2-company-assessments-20261024/`.
