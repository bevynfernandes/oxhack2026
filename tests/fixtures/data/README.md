# Synthetic C1 fixtures

All examples here are synthetic contract tests. `example.com`, numeric repository
IDs, timestamps, counts and hashes are invented. They do not establish real
source coverage, identity evidence or model performance.

- `catalog.json` / `catalog-changed.json`: effective package migration and stable
  repository identity across a rename.
- `observation-states.json`: complete, zero, missing, partial, late, revised and
  vendor-publication observations. The original revision remains distinct.
- `series.json`, `coverage.json`, `availability-policy.json`: source scope and
  explicit gaps/availability assumptions.
- `dataset-manifest.json`: metadata shape only; artifact hashes are placeholders.
