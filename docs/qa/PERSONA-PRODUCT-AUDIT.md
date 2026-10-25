# Persona product-quality audit

## Environment and method

- Live frontend: port 5174; live research API: port 8000.
- Browser interaction and captures use the installed Microsoft Playwright MCP server over stdio. The session did not expose new tools directly, so a persistent client connects to that same server; it does not substitute a separate browser engine.
- MCP transcript and screenshots: `tests/outputs/persona-audit/`.
- Integration branch: `codex/persona-product-quality`, based on #88; integrates current main/#86 and the #90 favicon activity indicator.
- Preserve existing backend contracts and data semantics. No client-derived success scores, artificial forecasts, fabricated source evidence or automatic background refreshes.

## Persona goals

| Persona | Specific goal | Relevant journey |
| --- | --- | --- |
| Founder | Understand what public evidence supports their company's progress and what records are missing | Domain → identity → research → evidence/limitations → refresh → notes/history |
| Angel investor | Screen an unfamiliar startup without confusing publicity with customers or success | Name/domain → identity → research → summary → source verification → shortlist |
| VC analyst | Compare two shortlisted companies using dated evidence and retain their research | Saved dossiers and fresh reports → shortlist → comparison → source detail |
| Accelerator | Triage applicants on mobile without treating missing public data as failure | Search/filter → dossier → missing evidence → notes and shortlist |
| Strategy analyst | Revisit competitor research and explicitly refresh it | Research → retained report → watchlist → review date → refresh/history |
| Researcher/journalist | Verify attribution, original sources and collection dates | Dossier → dimensions → source excerpts → limitations → export |

## Reproduced findings

- Homepage promises outlooks even though validated Growth/Survival predictions remain unavailable.
- Fresh reports have no discoverable history, watchlist or comparison entry point.
- Saved and fresh dossiers share a visual frame but are disconnected in navigation.
- No decision summary explains outcome definitions, coverage, evidence gaps and freshness together.
- Company-name search returns 404 on the live API; exact domain discovery works. Names must not be converted into guessed domains.
- Saved results briefly show zero matches while publication-company requests are still loading.
- Live research status shows source progress but no clear company name or retained return path.
- Homepage favicon request returns 404.
- #88 review identifies oversized decorative artwork when the root theme class is removed; add layout coverage to the existing rollback test.
- UI branches diverged: resolve on the integration branch without discarding tested homepage fixes or shared motion.

## Verification and limitations

- Audit completed against live public-source research plus controlled browser fault tests. Fixture regressions are recorded separately below.
- Account-backed watchlists, cross-device history, background schedules and notifications are not exposed by the existing API. Browser-local workflow must be labelled honestly.
- Browser-rendered collection, reviewed financial-entity mappings and validated outcome models are unavailable in the live service; UI changes cannot create those data.

## Results after fixes

| Persona | Live result | Decision limit |
| --- | --- | --- |
| Founder | PostHog domain discovery, explicit identity confirmation, progress, completed partial report, mobile evidence, JSON export, refresh and reopening from history | Can inspect public claims and missing records; cannot obtain validated growth/survival predictions |
| Angel investor | ElevenLabs name lookup → source-backed candidate → identity → completed report; SDK measurements, experimental proxy explanation, notes and watchlist | SDK downloads are not customers or recurring revenue; coverage is not predictive confidence |
| VC analyst | Qdrant/Weaviate published-cohort comparison; fresh ElevenLabs versus saved Qdrant comparison, then two fresh Qdrant/ElevenLabs reports from the watchlist, desktop and mobile; exact report/source navigation | Different dates/definitions are retained; no artificial common cohort, ranked winner or inferred peer suitability |
| Accelerator | Qdrant name research → confirmation → live partial report; mobile Financial Health drawer, missing-data explanation, applicant notes and watchlist | Missing public financial/customer data cannot be used as evidence that the applicant will fail |
| Strategy analyst | PostHog refresh with keyboard confirmation, a new immutable report, old report still accessible, dated browser-local notes/watchlist | Manual review dates only; no background monitoring, scheduled refresh or notifications |
| Journalist | Qdrant original-source navigation; PostHog export; ElevenLabs measurement definitions, dates, source limitations, identity and mapping provenance | Attributed company claims, demonstrations and experimental estimates require independent verification |

- Shared flows were exercised across these personas using real PostHog, ElevenLabs and Qdrant research. This is task-based browser QA, not a usability study with six human participants.
- Live reports completed with **partial** source coverage. The UI retains successful sources and reports missing/failed collectors; partial is not presented as complete evidence.
- Founder refresh: `59cce9e662ba45a2b1f27e9983666637` → `979b8ba7c0f745c2bfada63c5770af48`; both exact report resources remain separate.
- Name-based ElevenLabs report: `6c29b0fa697c40a0aca299a14f2c978f`; applicant Qdrant report: `5127136546c14641913da0225afd0cdf`.
- These identifiers reference the local research store, not production guarantees or public dataset releases.

## Problems resolved

- Revised the homepage promise to dated evidence research with validated predictions explicitly unavailable.
- Added **Your research** to Compare & explore: visited immutable reports, saved dossiers, jobs, local search, saved-search filters, watchlist filtering, notes and manual review dates.
- Added a decision-summary dialog explaining definitions, coverage versus confidence, a usable observed signal, unestablished business risk, missing evidence, source freshness and comparison caveats. It deliberately does not invent the strongest predictor or largest business risk.
- Added evidence comparison for two or three exact fresh/legacy/published records. Retained observation definitions, units, periods, collection dates and report limitations; preserved the original same-publication comparison.
- Restored comparison navigation on narrow screens; retained native link behaviour, modal focus and the shared Material motion primitives.
- Suppressed misleading zero-result flashes while saved-company queries load. Exact known names use their published website, while unfamiliar names require candidate selection. Exact domains never depend on history or name search.
- Added actionable name-search errors for unavailable endpoints/server failures, preserving a direct-domain recovery path.
- Added company context and history links to live progress; storage failure warns users to retain the durable URL.
- Preserved a known report date when revisiting a completed job; reopening reports does not erase notes/watchlist metadata.
- Corrected legacy comparison to use its actual report observations, saved context and research date, without assigning a new outcome horizon.
- Added the missing app favicon and verified existing company-icon fallback behaviour.
- Integrated #86/#88 work locally and merged #90 remotely into `codex/home-ui-motion-polish` (merge `a98c2b9`). Preserved this branch's tested homepage fixes when reconciling that merge.
- Fixed #90's inherited header-height shift, decorative mobile overflow and forced-colour background regression. Updated the obsolete navy-colour assertion to the approved peach palette; kept accessibility and overflow assertions intact.

## Runtime integration findings

- The original local API process was serving an older sibling checkout. It returned a name-search 404 and real research jobs failed with `worker_storage_or_composition_failure`.
- Restarted the API from the integrated checkout using the same published and research stores and existing provider configuration. Subsequent live jobs produced reports. No backend implementation, API contract or generated schema was edited for this audit.
- Name search then exposed `ModuleNotFoundError: tld`. Installed the already-declared, lockfile-pinned `tld==0.13.2` in the local virtual environment; name lookup then returned ElevenLabs and reached identity review.
- Startup/runtime setup must include the existing research extra. A working frontend cannot supply an absent backend Python dependency.
- PR #92 was inspected: it introduces research-depth/continuation contracts and describes follow-up collector/UI work. It is not required for these frontend fixes and is not represented here as completed scheduled monitoring.

## Validation

- Frontend unit suite: **96 passed** (15 files).
- Full Chromium suite: **64 passed**, including generated fixture workflows, mobile layouts, automated accessibility, error states, shared motion, rapid reversal, disabled controls, polling, keyboard focus and immutable report export.
- After the final summary/history correction and merge reconciliation, reran the affected report/library browser coverage: **13 passed**; see `browser-summary-regression.log`.
- Saved-search follow-up: text/watchlist filters persist across reloads; MCP mobile check and desktop/mobile browser regressions pass without submitting research. Final full-suite log: `browser-saved-search.log`.
- Generated TypeScript contract check, TypeScript typecheck, Prettier check, production build and `git diff --check`: passed.
- #90 independently: **86 unit tests and 54 browser tests passed**, production build and formatting passed before merge; GitHub checks subsequently all passed.
- Playwright MCP live checks: desktop 1440×900; mobile 375×812; narrow/zoom-equivalent 320×740; keyboard activation, Escape/focus restoration, tab Home/End, live reduced-motion preference, source navigation, downloads, history persistence after browser restart and horizontal overflow.
- Live axe WCAG 2 A/AA and 2.1 AA checks: no violations on the completed 320px ElevenLabs report its evidence drawer and the mobile research library. Automated accessibility is not a full assistive-technology audit.
- Controlled MCP fault injection: saved-directory 503, retry/recovery and empty publication list. These were labelled controlled tests and were not substituted for successful live collection.
- A short local Vite overlay occurred while reconciling merge-conflict markers; the affected interaction was rerun after resolution. No unresolved overlay remains.
- No application animation engine changes, numeric-count animation, new runtime npm dependencies, backend edits or relaxed test assertions.
- Production build retains the existing >500 kB chunk warning (main bundle approximately 595 kB / 183 kB gzip); build succeeds. No performance threshold is claimed by this audit.

## Captures and evidence

All captures were produced through Playwright MCP and remain in ignored `tests/outputs/persona-audit/`; the JSON-RPC transcript records the actual calls and results.

- Before: `before-founder-progress.png`, `before-investor-name-search.png`, `before-vc-comparison.png`, `before-mobile-comparison.png`.
- Failure retained: `founder-live-worker-failure.png`.
- Live reports: `founder-live-report-mobile.png`, `after-name-research-desktop.png`, `angel-completed-320px-reduced-motion.png`.
- Continuing workflow: `accelerator-watchlist-mobile.png`, `saved-search-mobile.png`, `vc-mixed-comparison-desktop.png`, `vc-mixed-comparison-mobile.png`, `vc-two-fresh-reports-mobile.png`.
- Evidence: `journalist-live-provenance-desktop.png`, `accelerator-live-financial-evidence-mobile.png`.
- Fault tests: `controlled-directory-service-error.png`, `controlled-empty-directory.png`.

## Remaining blockers and explicit limits

- Growth, Survival and Overall company outcomes remain unavailable: no validated outcome models/labels are provided. A frontend-only patch cannot make the original success/failure investment decision reliable.
- Public-source collection is bounded. JavaScript-only content may be incomplete; GitHub/provider calls can fail; missing financial entity mappings prevent some financial collection. Missing evidence stays missing.
- Actual paying-customer retention, audited private financials, calibrated confidence and a validated ranking of business risks/supporting signals are not available for the researched companies.
- Watchlists, notes and history are **browser-local**. Saved searches retain browser-local text/watchlist filters. No account storage, cross-device sync, alerts or scheduled collection is implemented or implied. The existing API does not provide the account/notification/scheduler services required for a durable version of those features.
- Review dates are visible manual reminders, not a scheduled task. Reports are retained as immutable versions; automatic longitudinal change analysis is not implemented.
- Cross-report comparison is evidence comparison with dates and definitions. It does not turn unrelated records into a statistically comparable cohort.
- Existing package-traction and technical data-health tools retain their own meanings and routes; they are not relabelled as company-success models.
- All screenshots are local browser evidence, not production uptime or external-provider completeness guarantees.

## Files changed

The review diff against the integrated #90 UI base includes earlier #88 refinements as well as the audit fixes. No backend files appear in this diff.

- `docs/design/APPROACHABLE-RESEARCH-UI.md`
- `docs/design/TECHNO-CLASSICAL-THEME.md`
- `frontend/index.html`
- `frontend/public/favicon.svg`
- `frontend/src/App.tsx`
- `frontend/src/pages/companies/CompanyHomePage.tsx`
- `frontend/src/pages/companies/CompanyListPage.tsx`
- `frontend/src/pages/companies/ComparePage.tsx`
- `frontend/src/pages/research/CompanyDossier.tsx`
- `frontend/src/pages/research/ResearchComparison.tsx`
- `frontend/src/pages/research/ResearchJobPage.tsx`
- `frontend/src/pages/research/ResearchLibrary.tsx`
- `frontend/src/pages/research/ResearchTools.tsx`
- `frontend/src/pages/research/client.ts`
- `frontend/src/pages/research/library.ts`
- `frontend/src/pages/research/summary.ts`
- `frontend/src/pages/research/savedSearches.ts`
- `frontend/src/theme/theme.css`
- `frontend/src/theme/assets/rocket-line-drawing.svg`
- `frontend/tests/e2e/company-home.spec.ts`
- `frontend/tests/e2e/research-library.spec.ts`
- `frontend/tests/e2e/research.spec.ts`
- `frontend/tests/e2e/theme.spec.ts`
- `frontend/tests/unit/company-search.test.tsx`
- `frontend/tests/unit/evidence-summary.test.ts`
- `frontend/tests/unit/research-library.test.tsx`
- `frontend/tests/unit/theme.test.ts`
- `docs/qa/PERSONA-PRODUCT-AUDIT.md`

## Delivery

- PR #90 merged into the integrated UI branch.
- PR #93 contains the persona fixes and carries forward #88 refinements; review #93 as the integrated successor rather than merging the conflicting #88 independently.
- Working preview: `http://localhost:5174/`. Use **Compare & explore → Your research**, or **Decision summary & notes** on any dossier.

## Review follow-up

- Checked #93, #88, #90 and the three inline change requests on #86. #93 had no new reviewer findings; all six GitHub check groups passed on `a86c405`.
- Candidate layout, decorative overflow and unthemed fallback fixes are included in #93. Added explicit candidate geometry/accessibility/action regressions at 375, 1024 and 1440px; strengthened rollback assertions to check hidden artwork and the main region's internal width.
- Corrected a missed inherited finding: normalized the rocket SVG's CRLF/trailing whitespace. XML structure, path geometry and styles are unchanged. The complete diff from main now passes whitespace validation.
- Rechecked the inherited Python formatting finding: the integrated file is formatted and Python CI is green.
- Original #86 threads remain open until #93 is integrated into that branch; replies identify the fix and validation rather than implying that #86 alone contains every correction.
- Follow-up validation: 30 homepage/theme browser tests, production build/generated types and formatting; original full-suite results remain recorded above.
