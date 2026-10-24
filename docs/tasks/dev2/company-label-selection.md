# Company label eligibility at training time

`evaluation.company_labels.select_company_labels` selects one company endpoint
at one UTC fit cutoff. It preserves explicit observed negatives and excludes
unknown/conflicting follow-up, incomplete horizons, stale immature source vintages,
late label availability and reserved ownership families. One label vintage per
company/outcome/origin is required; input order or truth cannot choose a revision.

The result contains deterministic chronological labels and immutable, exhaustive
exclusion counts for that outcome. Held-out families take precedence so a related
company cannot re-enter training through another company ID. Other outcome types
are outside the requested scope rather than pooled into the target.

Upstream must still adjudicate source facts, validate family identity and actual
collection policy, and select explicit immutable vintages. Advancing the calendar
does not repair an old unknown label. This helper neither constructs a historical
cohort nor claims a model can be trained from the current surviving-tool sample.

Saved tests cover full follow-up, exact availability, missing/conflicting labels,
family leakage, mixed endpoints, ambiguous vintages and exclusion accounting.

Validation: Ruff, mypy and 430 Python unit tests pass; six opt-in integrations
are excluded. Logs: `tests/outputs/dev2-company-label-selection-20261024/`.
