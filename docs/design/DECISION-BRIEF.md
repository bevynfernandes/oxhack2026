# Decision report presentation

- Fresh `/research/v2/reports/:reportId` reports use the homepage's warm paper panels, technical grid, orange background and existing typefaces.
- Reading order: company and collection date; a concise decision brief; forecast availability; five fundamentals; expandable research details; notes and source ledger.
- The brief displays the first published finding and its supporting source, or the first usable observation when interpretation is unavailable. It does not rank either as the strongest predictor.
- Conflicting evidence or missing dimensions stay visible. Missing evidence is never treated as failure.
- An eligible SDK demand index, otherwise eligible title sentiment, is explicitly experimental. Ineligible or unreliable estimates are withheld. All model details remain in the dimension drawers.
- Token counts, batch statistics, full citations and continuation controls remain under **Research findings, citations & continuation**. Refresh, export, mapping, notes, source drawers and keyboard focus restoration retain their existing behaviour.
- Failed terminal interpretation is labelled unavailable; terminal processing is not presented as successful analysis.
- Saved/legacy reports retain their existing compact layout. No backend, routes, contracts, model outputs or motion tokens change.

## Validation

- Full frontend unit suite: 107 passed.
- Full browser suite: 72 passed, including research, saved reports, accessibility, motion and navigation.
- Generated types, TypeScript and production build passed; existing chunk-size warning remains.
- Focused desktop/mobile coverage verifies disclosure, explicit continuation, error feedback, keyboard focus, 200% text zoom and accessibility.
- Real ElevenLabs screenshots: `tests/outputs/decision-page/` (local ignored artifacts), before and after at 1440px and 390px.
- Gemini provider recovery and trained company outcome forecasts remain separate workstreams; this change supplies no synthetic verdicts or replacement predictions.

## Changed files

- `frontend/src/main.tsx`: load the scoped decision theme.
- `frontend/src/pages/research/CompanyDossier.tsx`: integrate the brief and progressively disclose operational detail.
- `frontend/src/pages/research/DecisionBrief.tsx`: source-backed findings, gaps and eligible experimental signal.
- `frontend/src/pages/research/ResearchWorkflow.tsx`: accurate terminal interpretation labels.
- `frontend/src/theme/decision.css`: paper/grid styling and responsive layout.
- `frontend/tests/unit/decision-brief.test.tsx`: signal eligibility and supported citations.
- `frontend/tests/unit/research-workflow.test.tsx`: failed-interpretation wording.
- `frontend/tests/e2e/research.spec.ts`: desktop/mobile decision journeys and accessibility.
- `docs/design/DECISION-BRIEF.md`: presentation contract and validation record.
- Final keyboard validation caught a queued drawer-close callback stealing newly moved focus. The dossier now restores focus only when it remains in the closing dialog or on the body; native restoration and deliberate user focus are respected.
