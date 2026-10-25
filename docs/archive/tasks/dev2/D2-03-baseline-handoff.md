# D2-03: Frozen catalogue resolution and baseline batch handoff

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


`features.catalog.catalog_requests` resolves verified primary download packages
and frozen organization representatives without inspecting forecast outcomes.
Missing or ambiguous series fail explicitly. Community/reference organizations
stay outside company selection. Requests have deterministic IDs tied to dataset,
mapping, target, decision, mode and feature schema.

Decision-time mapping selection is the default. For a contemporary reconstructed
cohort only, callers can explicitly pass `contemporary=True` to select mappings
effective at `catalog.recorded_at`. Actual evidence dates remain unchanged and
the returned limitations disclose retrospective membership and survivorship bias.
Prospective cohorts cannot use this override. A known future tool eligibility
date still excludes that tool from an earlier decision.

`models.predict.baseline_forecasts` produces C2 pre-reveal results for persistence,
weekday-seasonal and damped-trend baselines, reusing their shared numerical
functions. One batch has one dataset, ecosystem, target and decision origin.
Every requested tool survives; fewer than 84 complete days yields an unavailable
forecast. Low-reference tools retain count estimates with no percentage/ranking.
All baseline results are exploratory with absent intervals. Research comparator
ties must still use the tie-averaged evaluation helpers.

The callable pipeline is vendor-independent. Artifact publication, model manifests
and a real npm run are separate acceptance steps. This checkpoint does not claim
validated learned performance or a completed real-data handoff.
