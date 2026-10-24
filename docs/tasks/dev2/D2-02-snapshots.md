# D2-02: C1 daily vintage selection

`features.snapshots` projects validated C1 revisions into a typed Polars frame
and resolves bounded daily requests with an as-of join. Each request supplies
its series, half-open measurement window and knowledge cutoff. Source reads stay
outside the builder; no vendor requests or latest-data lookups occur here.

Reconstructed snapshots permit later retrieval under the recorded availability
policy. Prospective snapshots also require actual first collection by the cutoff.
Equal assumed availability bounds use collection/retrieval time and revision ID
as deterministic tie-breakers. Every expected day survives the join: missing or
partial counts remain null, while complete zeros remain zero.

Twelve saved tests cover revised vintages, exact cutoff boundaries, unavailable
future observations, empty inputs, series isolation and missingness. The full
checkpoint passes Ruff, mypy and 277 tests before integration with new main.
This is the vintage-selection portion of D2-02; it does not publish a dataset or
claim real forecasts. Aggregated features and mature labels are the next step.
