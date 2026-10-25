# D2-04a: Calendar membership and label-availability purges

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


- Owner: Dev 2; branch `dev/models-calendar-protocol`.
- Paths: `evaluation/splits.py`, saved model split tests, Dev 2 documentation.
- Depends on: C2 label rows and merged shared target definitions.
- Inputs: every expected eligible candidate label, including explicit immature
  rows; one ecosystem/target experiment at a time; fixed UTC evaluation cutoff.
- Outputs: origin-level availability and full chronological protocol membership.

`origin_availability` takes the latest required availability for an entire
origin. One missing candidate label leaves the origin incomplete. The caller
must supply the complete expected feature-row universe rather than complete
cases and must keep ecosystems separate in experiment manifests.

`calendar_protocol` follows PLAN.md section 7.1 backwards: 26 final-test origins,
26 calibration origins available by test start, and three 13-origin development
blocks available by calibration start. Every fit purges unavailable labels and
requires at least 52 earlier training origins. The final training set is frozen
at calibration start. Required blocks contain consecutive Mondays. Gaps and
insufficient history raise a meaningful error; callers must label a separately
defined exploratory experiment honestly rather than shorten this protocol.

The input begins only after the required feature lookback. Split membership
does not itself prove source availability, identity validity, feature integrity,
or preregistration. Feature builders and frozen experiment manifests supply
those remaining checks. No training, outcomes scoring, or final-test selection
occurs here.

Saved tests cover exact membership for both targets, whole-origin purges,
reproduction under reordered input, future-label isolation, missing blocks,
short panels, timestamps, duplicates, complete zero counts, and slow candidates.
These are synthetic fixtures, not model-performance evidence.
