# D2-02: Versioned download features and separate labels

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


`features.builders` consumes the frozen C1 observation projection and explicit
`FeatureRequest` identities/windows. Requests validate the selected package,
ecosystem and download series. Catalogue verification and effective mapping
selection remain prerequisites of the caller, not inferred from source counts.

`downloads-features-v1` computes shared vectorized aggregates on bounded daily
snapshots: 7/28/30/56/60/84-day totals, log reference, adjacent 28/30-day log
growth, sample dispersion of eleven weekly log changes, seven weekday shares,
annual sine/cosine, history coverage and observation age. Totals require complete
windows; eligible learned rows require all 84 days. All-zero weekday shares and
unknown verified package age remain null. C1 has no verified package-creation
field, so tool eligibility dates are never substituted for package age.

`build_labels` uses a separate explicit outcome-vintage cutoff and the exact
30-day or trailing-28-day target. A single missing, partial or unavailable day
keeps both actual count and availability null. Selected source revisions remain
attached; no label enters the feature vector. Aggregate integer calculations use
Int128 to avoid overflowing individual BIGINT daily counts.

Fourteen saved tests cover both horizons, maturity boundaries, collection policy,
zeros, missing history, ordered weekly dispersion, multiple origins, revised
future observations and large counts. These are synthetic software tests. Real
dataset publication, catalogue resolution and baseline handoff follow separately.
