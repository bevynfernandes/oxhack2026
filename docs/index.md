# SignalShift

Company research and startup outlooks from dated adoption, execution, commercial
and financing evidence. The application presents source-linked assessments,
explicit gaps and restricted experimental model outputs. Company-outcome
forecasts remain unavailable until their data and evaluation gates pass.

## Development and runtime

Use Python 3.12, uv and Node 24. From the repository root:

```bash
make install notebooks frontend-install
make check test build docs-test frontend-check
```

- [Local API and container setup](https://github.com/bevynfernandes/oxhack2026/blob/main/deploy/local/README.md).
- [Standalone research, worker storage and provider configuration](tasks/dev3/research-v2.md).
- [Company publication recovery and bounded refresh](tasks/dev1/D1-O6-local-recovery.md).
- [Module boundaries](modules.md) and [CI checks](ci-performance.md).

## Evidence and models

Company sources, assessments and research reports retain dated provenance and
immutable artifact references. Research can operate independently of saved
company publications. Five experimental dimension models have retained training
results and explicit serving restrictions; missing financials remain unknown.

- [Dimension training results and forecast mapping](tasks/dev2/public-dimension-training-20261024.md).
- [Public model research and source limits](tasks/dev2/public-model-research-20261024.md).
- [Company outcome policy](tasks/dev2/company-outcome-policy.md).
- [Product decisions](https://github.com/bevynfernandes/oxhack2026/blob/main/PLAN.md).

Default unit tests and browser fixtures are synthetic software checks. Integration
and real-data acceptance require their explicit local setup. Neither passing tests
nor schema validity establishes predictive performance or cloud deployment.
Historical plans and completed handoffs are in the [project archive](archive/index.md).
