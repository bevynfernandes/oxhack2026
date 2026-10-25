# D2-04b: Model-owned per-tool reveal diagnostics

> Historical implementation record. See the [current overview](../../../index.md) for setup and runtime instructions.


- Owner: Dev 2; branch `dev/models-outcome-diagnostics`.
- Paths: evaluation contracts/metrics, schema exporter, model schemas/tests,
  and Dev 2 documentation.
- Inputs: C2 forecast, separately selected mature outcome vintage, UTC cutoff.
- Outputs: additive `OutcomeDiagnostics` artifact, separate from forecast DTOs.
- Dependencies/cost: existing lightweight C2 types only; no services.

`evaluation.metrics.outcome_diagnostics` checks forecast/feature/window identity
and actual availability at the requested cutoff. It returns count and log-count
absolute errors for available model/baseline estimates. Realized percentage
growth remains null below the shared 1,000-reference threshold. Missing model
estimates produce null errors, while explicit complete zero outcomes are valid.

Dev 3 can call this helper after selecting one outcome vintage, or read saved
diagnostics. It owns public DTO conversion; numerical formulas stay here.
Forecast payloads remain unchanged. The additive contract has its own exported
schema and does not add actuals to any pre-reveal type.

Saved checks cover independent calculations, exact availability boundary,
missing estimates, low reference activity, identity mismatch, and zero truth.
All records are synthetic; no research-performance result is claimed.
