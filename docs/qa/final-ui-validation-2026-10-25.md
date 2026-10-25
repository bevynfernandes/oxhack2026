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

- Frontend unit suite after comparison update: 112 passed.
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

## Comparison follow-up

- Comparison now preserves eligible SDK-demand and title-sentiment model outputs from each exact immutable resource instead of always showing a blanket unavailable label.
- Model targets, dates, architectures and limitations remain attached to each output; no winner or company-success odds are derived. Fresh reports never inherit model output from older saved context.
- Real Playwright comparison at 1440px and 390px: Qdrant 34.8/100 and Weaviate 34.2/100 SDK forecast percentiles, model-detail disclosures, no overflow or automated accessibility violations.

## Presentation evidence

- Slide 6 retains its original comparison title, layout and sidebar copy. Only its comparison screenshot and source notes are updated.
- Screenshot shows real Qdrant and Weaviate experimental SDK forecasts from `company-assessments-vector-20261024-v1`; cropped only, without generated values.
- Slides 1–5 and 7–8 remain pixel-identical to the original Phronesis deck.
- Raw browser logs, screenshots and exports are retained under ignored `tests/outputs/`.
