# Numerical policy handoff

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


Use `features.definitions.target_windows(decision_at, target_id)` for exact
half-open boundaries. C2 validation calls this same implementation. The 84-day
history, 1,000-download threshold, top-five size and ten-organization headline
minimum are named constants in that module. Recording at/after the cutoff is
too late for a prospective forecast.

API/storage adapters import lightweight pure functions:

```python
from oxhack2026.evaluation.shortlists import rank_forecasts, score_shortlist

ranking = rank_forecasts(forecasts, representatives)
score = score_shortlist(
    forecasts, mature_outcomes, selected_organization_ids,
    representatives, candidate_universe_id,
)
```

`representatives` maps organization IDs to tool IDs from the **batch's frozen
catalogue**, scoped to its ecosystem. Never derive it from forecast or outcome
growth. Nonrepresentative tools are excluded even when their prediction is larger.
Mixed datasets, mappings, targets, origins, duplicate IDs, missing mappings,
invalid selections and mismatched outcome windows/feature IDs raise `ValueError`.

`rank_forecasts` is a display ordering: growth descending, tool ID for stable
ties. Equal predictions must use tie-averaged/random selection for scientific
baseline comparisons; display order does not provide evidence of superiority.

`score_shortlist` accepts organization IDs, matching C3's reveal request. It
returns C2 `ShortlistScore` with the corresponding forecast IDs. The caller
provides exactly one available outcome vintage per forecast and checks reveal
availability as of its request time. If any eligible candidate lacks truth,
`complete_outcomes` is false and all scores are null. Dev 3 should translate this
to unavailable reveal (409), not zero or a partial-universe score.

Mean realized growth is mean `log1p(actual)-log1p(reference)`. Full five-item
lists get precision/recall against >=50% actual growth and regret versus the
oracle five on the same universe. No-positive precision is zero; recall is
null. Smaller selections have descriptive mean only; they never enter headline
top-five evaluation. Fewer than ten eligible organizations also excludes the
origin from headline evaluation.

Verification: `make check test`. Tests consume labelled synthetic C2 fixtures;
they do not establish model performance. Real feature building/evaluation still
requires Dev 1's frozen, verified C1 observation bundle.
