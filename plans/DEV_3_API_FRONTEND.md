# Dev 3: API, frontend, historical replay, and demo

**Branch:** `dev/api-frontend`

**Role:** Deliver the scout's complete workflow using immutable artifacts from
the data and modelling workstreams.

Read [team coordination](README.md), [PLAN.md](../PLAN.md), and
[AGENTS.md](../AGENTS.md). Follow PLAN.md sections 2 and 8 for product and API
behavior, and section 3 for the time semantics shown to users.

## 1. Outcome and ownership

Your completed work lets a scout select an ecosystem/cutoff, inspect a ranked
five-company shortlist, understand the evidence, reveal mature outcomes, and
compare model performance with baselines.

Own:

- `oxhack2026/api/**`.
- `frontend/**`, including its dependencies and lockfile.
- `contracts/api/**`, `configs/api/**`.
- New `oxhack2026/demo/**`, `oxhack2026/cli/demo.py`, and root `demo/**`.
- `tests/{unit,integration,fixtures}/api/**`.
- Frontend unit/browser tests.
- `docs/workstreams/dev3/**`, `docs/tasks/dev3/**`.

Do not edit ingestion, storage implementations, database migrations, model
training, numerical policy, or root Python dependency files.

Dev 1 supplies repositories and runtime integration. Dev 2 supplies typed
forecast/evidence artifacts and lightweight ranking/scoring helpers.
Do not duplicate those implementations in the API or browser.

## 2. Start your branch and environment

After the common scaffold is committed and published:

```bash
git fetch origin
git switch --create dev/api-frontend origin/main
uv sync --frozen --inexact --all-extras --group docs
make notebooks
npm --prefix frontend ci
make check test frontend-check
```

The current frontend is a static placeholder. Current Python modules define no
API application or endpoints. Frontend test scripts do not exist yet; add them
with real saved tests.

All extras support whole-repository checks after teammate merges. Dev 1 keeps
the production API image narrower; lightweight public-contract and scoring
imports must work there without training libraries or cloud credentials.

Request any Python test/tool dependency from Dev 1. You may add frontend
packages and update package-lock.json within your owned paths.

## 3. D3-01: Publish C3 public API contracts

Draft against C1/C2 while their owners finish review, then freeze against the
merged contracts.

Implement public Pydantic request/response schemas and export OpenAPI for:

| Route under /api/v1 | Purpose |
| --- | --- |
| GET /health/live | Process liveness |
| GET /health/ready | Required service/artifact readiness |
| GET /catalog | Verified catalogue/filter metadata |
| GET /cutoffs | Supported ecosystem/target/cutoff combinations |
| GET /tools/{tool_id}/history | Batch-bounded observed history |
| GET /forecasts/{batch_id} | Saved forecast batch |
| GET /rankings/{batch_id} | Ranking, exclusions, and baseline rankings |
| POST /replays/{batch_id}/reveal | Mature outcomes and submitted-shortlist scores |
| GET /evaluations/{evaluation_id} | Immutable evaluation report |
| GET /data-health | Source freshness/quality summary |

Keep forecast and reveal DTOs separate. Pre-reveal payloads must contain no
actual future values, even if the frontend would hide them.

Return 422 for invalid inputs, 404 for unknown resources, and 409 for an
unmatured reveal. Do not silently substitute another cutoff/model.

Generate frontend types from OpenAPI. Put schema exports and labelled API
fixtures under your owned contract/test paths; do not hand-maintain competing
TypeScript interfaces.

Cover ready, partial, low-history, low-denominator, stale, unvalidated,
unavailable, and immature-reveal cases. Keep availability and evidence status
separate.

**Done when:** C3 and its fixtures merge, generated types are reproducible, and
the other owners approve the mapping from stored artifacts to public responses.

## 4. D3-02: Independent API and UI development

Develop against dependency-injected repositories and saved contract fixtures.
Use mocks in tests rather than building a competing persistence layer.

Implement:

- Application factory/lifecycle without vendor calls at import time.
- Route validation and error mapping.
- Repository-backed catalogue/history/forecast/evaluation reads.
- Response metadata for dataset, mapping, target, model, and evidence versions.
- Clearly separated development fixture mode, if needed for local UI work.
- Generated client types and request helpers.
- Loading, empty, partial, error, and stale states.

Synthetic mode must be explicit and visibly labelled. It cannot silently replace
failed real data or be included in a real-data demonstration.

The public API must never trigger ingestion, training, SQL execution supplied
by the user, or paid LLM calls. Serve persisted explanations and artifacts.

## 5. D3-03: Rankings and tool detail

Implement the main scout workflow:

- Ecosystem, supported target, and cutoff selection.
- Organization/tool/package identity with verified mapping evidence.
- Forecast count, reference count/window, growth, baseline, and freshness.
- Five-company recommendation and manual alternative shortlist.
- One representative per organization.
- Visible exclusions and insufficient-coverage reasons.
- Baseline ranking comparison.
- Selection state keyed to immutable forecast batch.

Use Dev 2's ranking/eligibility policy. If local client sorting is offered for
display, it must not silently redefine the scored shortlist policy.

For detail views:

- Bound observed history by the selected batch's permitted cutoff.
- Show aggregate-window forecast estimates and available intervals.
- Label actual reference-window dates, including the reporting-lag gap.
- Show evidence links, source coverage, and mapping details.
- Separate observed, forecast, and reconstructed/prospective status.

Do not interpolate aggregate predictions into invented daily trajectories.
Do not display generic confidence scores or unvalidated causal claims.

## 6. D3-04: Historical reveal and evaluation

Implement a reveal workflow that:

1. Displays the saved forecast before outcomes.
2. Accepts at most five distinct organization selections.
3. Preserves the pre-reveal selection for its score.
4. Requests separate mature outcomes.
5. Calls Dev 2's lightweight shortlist scorer or reads published comparator
   scores; does not copy the formulas.
6. Shows actuals, model/baseline errors, and shortlist comparisons.
7. Leaves the original forecast payload and version unchanged.

Changing a selection after reveal creates a distinct scored selection. It does
not rewrite the earlier blind selection.

The evaluation view must show:

- Actual test periods, sample/origin/organization counts, and exclusions.
- Baseline and model comparisons.
- Source ablations on their stated common rows.
- Exploratory, inconclusive, rejected, and confirmed statuses.
- Measured interval coverage and its limitations.
- Manifest/report links and model/data versions.

Do not claim broad superiority from an insufficient evaluation or hide a
baseline win.

## 7. D3-05: Connect to real published artifacts

After the data and baseline checkpoints merge:

- Replace development repositories with Dev 1's actual read interfaces.
- Load Dev 2's real published forecast batch.
- Verify all schema and version references match.
- Run one complete npm historical forecast/reveal.
- Confirm no vendor call is needed to serve that workflow.
- Confirm revised source data cannot change the frozen replay.
- Keep future outcomes absent from pre-reveal network responses, not merely
  hidden in the DOM.

Raise storage-interface gaps with Dev 1 and output-contract gaps with Dev 2.
Do not implement parallel DB tables or alternate model calculations to bypass
a missing handoff.

**Done when:** the browser workflow uses real versioned artifacts and its
end-to-end tests pass with known fixture provenance.

## 8. D3-06: Evidence presentation, data health, and accessibility

Render deterministic explanations from Dev 2 and later validated cached Gemini
briefings if available. The UI never asks an LLM for numeric forecasts.

Keep numerical values bound to authoritative typed fields. Render measured
changes, predictive interpretations, and limitations distinctly.

Add:

- Source freshness and completeness panel.
- Mapping provenance and original evidence links.
- Coverage warnings and unavailable-source states.
- Keyboard navigation and accessible table alternatives.
- Color-independent observed/forecast distinctions.
- Reduced motion and narrow-screen layouts.
- Robust error/loading states.

Treat external source text as untrusted and escape it. Do not embed credentials
in browser code or VITE-prefixed configuration.

## 9. D3-07: Offline demo and deployment handoff

Implement the exporter and read-only offline adapter under the new
`oxhack2026/demo/` package, with `oxhack2026/cli/demo.py` as the thin wrapper.
The wheel packages `oxhack2026`; executable code placed only in root `demo/`
would not be installed. Reserve root `demo/` for documentation and approved
sample manifests/artifacts. Reuse Dev 1's artifact validation/read interfaces.
Dev 1 registers your CLI group and updates generated-output ignore rules.

The export includes:

- A compatible published dataset/forecast/evaluation selection.
- Required evidence and outcome artifacts.
- Contract/version metadata and checksums.
- Attribution and provenance.
- A reproducible loading instruction.

Use real licensed observations for the product demo. Keep synthetic component
fixtures separate and visibly labelled.

The offline serving adapter must use the same API contracts and frontend
components. Block all third-party network access, including explanation
fallback calls, during its acceptance test.

Provide Dev 1:

- Actual API startup command and environment variable names.
- Static frontend output and serving/base-path requirements.
- Liveness/readiness endpoints.
- Local and integrated startup instructions.
- Expected database/artifact prerequisites.
- Smoke and browser-test commands.

Dev 1 owns Docker/Compose, cloud resource creation, TLS, schedules, and rollout.
Do not provision a separate web stack independently.

## 10. Tests and acceptance

Save API tests under your owned Python test paths and UI/browser tests under
frontend/tests. Add test scripts only when tests are implemented.

Required cases:

- Pydantic/OpenAPI/generated-TypeScript compatibility.
- Valid/invalid catalogue IDs, targets, cutoffs, and shortlist inputs.
- Per-tool partial availability.
- No future fields before reveal.
- Unmatured reveal returns 409.
- Forecast payload unchanged after reveal.
- Duplicate organization selections rejected.
- Low-reference/missing data displays as unavailable, never fake zero.
- Shared numerical-policy helper results displayed correctly.
- Synthetic fixture mode never silently becomes real mode.
- Baseline wins and failed interval validation render honestly.
- Browser selection/cutoff state and post-reveal selection behavior.
- Escaped source text and absence of browser secrets.
- Keyboard/reduced-motion behavior.
- Full no-network real-artifact replay/export.
- Repository failure and stale published artifacts.

Run current checks plus implemented suites:

```bash
make check test frontend-check
uv run --frozen --no-sync pytest tests/unit/api
uv run --frozen --no-sync pytest -m integration tests/integration/api
npm --prefix frontend run test
npm --prefix frontend run test:e2e
```

The final two scripts must be added with actual Vitest/Playwright suites.
Coordinate CI installation and service setup with Dev 1. Do not claim the
current scaffold's missing scripts already work.

## 11. Handoff and completion

Every handoff includes:

- Commit/task and API contract versions.
- Required dataset/model/batch IDs.
- Generated-type update and schema compatibility results.
- Routes/screens completed and known states not yet supported.
- Screenshot or browser-test artifacts where useful.
- API/UI startup and environment instructions.
- Tests run and retained output locations.
- Real versus synthetic fixture provenance.
- Deployment prerequisites for Dev 1.

Your branch is complete when the real scouting workflow, historical reveal,
evaluation, evidence, and offline demo work through the shared contracts and
passing browser/API checks.

## 12. Copy-paste Codex starting prompt

```text
Implement the Dev 3 workstream in plans/DEV_3_API_FRONTEND.md.
Read AGENTS.md, PLAN.md, and plans/README.md first. Work on dev/api-frontend
from the committed shared scaffold.

Own public API, frontend, API contracts, packaged demo export/offline serving
under oxhack2026/demo/, and cli/demo.py only. Root demo/ is for documentation
and approved sample manifests/artifacts, not executable implementation.
Do not edit ingestion, storage implementations, migrations, numerical policy,
root Python dependencies/lockfiles, or PLAN.md.

Start with D3-01: public API schemas/OpenAPI and generated TypeScript types
aligned with the merged data/model contracts. Use saved labelled fixtures and
dependency-injected repositories to develop independently.

Implement rankings/detail/replay/evaluation without inventing forecasts.
Call Dev 2's lightweight numerical helpers instead of duplicating calculations.
Keep actual future outcomes out of pre-reveal responses. The API must not
collect data, train models, or make paid LLM calls during requests.

Connect to real published artifacts when available. Add meaningful API/browser
tests and an offline demo using the same contracts and components. Request
shared changes from their owners, record handoffs, and deliver small reviewed
checkpoints. Do not merge or publish without the developer's instruction.
```
