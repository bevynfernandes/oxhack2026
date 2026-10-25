# Integrated frontend validation — 25 October 2026

- Base: `f5974c5` (`main`, including PRs #98, #99 and #100).
- Local app: `http://localhost:5174`; retained company and research stores preserved.
- No backend code, generated types, API contracts or model/data semantics changed.

## Fixes

- A queued native dialog `close` event could refocus the opener after the user had moved to another control. The shared dialog now restores focus only when it is still inside the dialog or on the body.
- Added a deterministic regression test reproducing the native close-event ordering.
- Updated saved/fresh dossier tests to expect the integrated decision-brief heading. Saved-company tests additionally assert all three unavailable forecast labels; legacy report expectations remain unchanged.
- Installed existing frontend dependencies within the isolated checkout to avoid Vite rejecting symlinked font assets. No dependency versions changed.

## Validation

- Frontend unit suite: 111 passed.
- Full Playwright suite: 75 passed, including desktop/mobile, accessibility, keyboard, reduced motion, drawer/disclosure lifecycle, loading/error states and mixed comparison.
- Repeated drawer-to-disclosure keyboard regression: 10/10 passed across desktop/mobile.
- Provider/backend regression tests: 185 passed across Gemini text, Google search, interpretation, evidence mapping, research analysis and profiles.
- Generated-type check, TypeScript, production build and Prettier: passed. Existing >500 kB bundle warning remains.
- Real Playwright journeys at 1440px and 390px: saved Qdrant, all five dimension drawers, retained ElevenLabs SDK forecast, supporting evidence, keyboard disclosures, export, reload and refresh confirmation passed; no page errors or automated accessibility violations.
- Real saved/fresh comparison: ElevenLabs and Qdrant, notes persistence, watchlist, dated measurements and missing-report feedback passed at both widths.
- Live new research: ElevenLabs domain → identity confirmation → Fast job → partial report. No mocked responses or altered report data were used for live checks.

## Remaining service/data blockers

- Follow-up: [#101](https://github.com/bevynfernandes/oxhack2026/issues/101).
- New report `60b28f0ce1574fc4aab3be34ccf76807`: model synthesis and Google discovery returned HTTP 500; GitHub returned 403; news returned 429; npm lacked verified package mapping.
- SEC, Companies House and browser-assisted collection remain unconfigured locally.
- Growth, survival and financial-health outcome predictions remain unavailable. An SDK forecast percentile is not a startup-success probability.

## Presentation evidence

- Slide 6 uses genuine retained report `6c29b0fa697c40a0aca299a14f2c978f`, showing ElevenLabs' experimental 31.3/100 next-30-day SDK-demand forecast percentile.
- Screenshot captured with Playwright, cropped only; no generated numbers or synthetic fixtures.
- Deck/PDF exported separately from the repository. Slides 1–5 and 7–8 are pixel-identical to the preceding deck.
- Raw browser logs, screenshots and exports are retained under ignored `tests/outputs/final-runtime/` and `tests/outputs/final-*`.
