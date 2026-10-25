# Tests

- `test_package_imports.py`: lightweight package namespace smoke checks.
- `unit/`: isolated contract, data, model, research and API tests with external
  dependencies mocked.
- `integration/`: explicitly enabled local-storage and API persistence checks.
- `fixtures/`: saved, clearly labelled synthetic inputs and API compositions.
- `outputs/`: ignored retained outputs organized by run ID.

Run the default Python suite with `make test`. Integration tests are excluded
unless explicitly selected with `make test-integration`; follow the relevant
runbook before selecting tests that require configured publications or services.

The [frontend test guide](../frontend/tests/README.md) covers Vitest, synthetic
Playwright tests and the separately configured real-company suite. Synthetic
fixtures are never a fallback for production startup or real-data acceptance.

Save tests before running them. Preserve test-created outputs; do not add automatic
cleanup. Keep secrets out of fixtures, logs and committed outputs.
