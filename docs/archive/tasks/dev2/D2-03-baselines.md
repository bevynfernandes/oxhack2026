# D2-03a: Baseline formulas and comparator expectations

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


- Owner: Dev 2; branch `dev/models-baselines-v1`.
- Inputs: complete frozen reference/previous-window counts, exactly 28 anchored
  daily counts, validated C2 target windows, common organization score maps.
- Owned paths: `models/baselines.py`, `evaluation/comparators.py`, model unit tests,
  and Dev 2 documentation.
- Dependencies: merged C2. No new dependencies, network calls, or root edits.

Implements persistence, four-week weekday seasonal totals, adjacent log growth,
and damped trend. Trend clips to +/-log(2), damps by 0.5, and uses the exact
reference/target midpoint distance: 32/30 for the short target, 93/28 for the
medium-term target. Missing or invalid counts fail; complete zeros remain valid.

`selection_weights` averages boundary ties exactly in O(n log 5), including
uniform-random/persistence ties. `expected_shortlist_growth` requires identical
candidate keys and complete finite realized log growth for every comparator.
Popularity supplies current reference counts as scores; recent-growth and
damped-trend comparators supply their own numerical scores on the same keys.

Saved tests independently check target weekdays, midpoint scaling, clipping,
zero/missing histories, exact ties, and candidate-universe equality. Fixtures
and counts are synthetic; these tests establish formulas, not predictive value.

The real-data forecast/reveal handoff portion of D2-03 remains pending C1's
frozen verified npm bundle and the feature/label builders. No real experiment,
learned model, or empirical improvement is claimed.
