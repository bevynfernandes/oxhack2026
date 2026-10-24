# Test scaffold

test_scaffold.py checks package namespace imports only. It does not validate
product functionality.

- unit/: future isolated tests with external dependencies mocked.
- integration/: future explicitly enabled local-service tests.
- fixtures/: saved, clearly labelled test inputs.
- outputs/: ignored retained outputs organized by run ID.

Save tests before running them. Preserve test-created outputs; do not add
automatic cleanup. Frontend test placeholders live under frontend/tests/.
