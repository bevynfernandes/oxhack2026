# Company outlook: Dev 2 policy proposal

Tracks [#19](https://github.com/bevynfernandes/oxhack2026/issues/19), following
the user's replacement of the download-only product goal. The user requested
all three outcomes below. This proposal defines their semantics before new
data/model/API schemas are frozen with Dev 1 and Dev 3.

| Outcome | Horizon | Positive evidence | Negative evidence |
| --- | --- | --- | --- |
| Operating and growing | 24 calendar months | Verified operation at the endpoint and growth in a comparable company-level commercial measure | Verified shutdown within the horizon, or verified endpoint operation with nonpositive growth in that same measure |
| Commercial viability | 12 calendar months | Verified operating cash flow at least zero over the ending twelve-month period, with continuing operation | Verified shutdown, or negative operating cash flow over the same fully observed period |
| Financing or acquisition | 24 calendar months | A completed primary equity/convertible financing or completed change-of-control acquisition within the horizon | Explicit verified complete follow-up establishing neither qualifying event occurred |

These labels are separate. A distressed acquisition still records an acquisition
event; it is not evidence of commercial viability. An unannounced funding round,
unknown cash flow or a missing company website does not establish failure.
Commercial viability here is a specific observable endpoint, not a judgement
that every venture-funded company with negative current cash flow is doomed.

For operating/growing, predeclare revenue or active paying customers as the
commercial measure for each cohort, with comparable twelve-month windows ending
at the decision and target endpoint. Product downloads alone cannot satisfy this
company-level label. Currency, accounting and customer definitions must match.
Missing or incomparable windows leave the label unknown. Do not choose the
measure retrospectively according to which one grew.

Horizons use calendar anniversaries, clamping leap-day anniversaries to the last
day of February. Events use `(decision_at, horizon_end]`; events already known
at the decision are predictors, not future outcomes. Dataset availability and
actual collection times remain distinct from the event's occurrence time.

For the initial binary experiments, require the whole horizon to have elapsed
before admitting either positive or negative labels. This avoids evaluating
early-observed successes against incomplete negative follow-up. Retain event
times for later survival/competing-risk analysis. Track immature, unobserved,
ambiguous and contradictory labels separately; none becomes a negative.

Use organization histories including inactive/failed companies, dated effective
ownership and peer groups defined by sector/stage/business model. Split by time,
purge labels unavailable at the fit cutoff, and prevent organization-family
leakage in held-out-company tests. Contemporary surviving npm tools alone cannot
validate company survival predictions.

Fit separate outcome models only after the labelled cohort exists. Compare with
training-only prevalence and a simple regularized classifier. Report Brier/log
loss, discrimination, calibration, class balance, follow-up coverage, time spans
and supported subgroup results. Freeze features and selection before the final
holdout. A reviewed release gate must establish useful calibration and decision
value before any public success probability is served.

The immediately feasible product is a multi-metric evidence assessment with
three explicit outcome sections and unknowns where data is unavailable. Package
traction remains one metric family. It must never be renamed as a company-success
probability. Exact source feasibility, commercial-label access and the shared
contracts await the owner responses in #19; this document is not empirical proof.
