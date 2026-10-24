# Techno-Classical Retrofuturist theme

## Intent and boundaries

SignalShift is a research instrument: editorial hierarchy and etched geometry
frame dated evidence, rather than suggesting certainty or futuristic prediction
capabilities. The theme changes presentation only. Routes, data semantics,
backend/API contracts, generated types, functional components and test assertions
remain intact. Existing stylesheets stay in place beneath an additive theme.

The root `theme-techno-classical` class enables `src/theme/theme.css`. Removing
that class restores the preceding presentation. Keep layout, responsive rules and
Material 3 Expressive motion in their existing modules; no new animation engine,
page timing, animated data or extra JavaScript dependency is introduced.

## Palette and hierarchy

| Role                   | Token                  | Colour    |
| ---------------------- | ---------------------- | --------- |
| Canvas                 | `--theme-canvas`       | `#090f1b` |
| Surface                | `--theme-surface`      | `#101a2a` |
| Raised surface         | `--theme-raised`       | `#172438` |
| Primary text           | `--theme-text`         | `#f1ecdf` |
| Secondary text         | `--theme-muted`        | `#acb9cb` |
| Technical rule         | `--theme-line`         | `#34445b` |
| Input/control boundary | `--theme-control-line` | `#7185a2` |
| Electric blue          | `--theme-accent`       | `#8bb5ff` |
| Selected surface       | `--theme-selected`     | `#203655` |
| Warning/evidence gap   | `--theme-warning`      | `#e8c58b` |
| Error                  | `--theme-danger`       | `#ffb0a7` |
| Confirmed source state | `--theme-positive`     | `#a7d1bf` |

Warm ivory is reserved for readable primary content; muted text remains readable
at small sizes. Blue denotes navigation, focus and selection, not model quality.
Amber and red support existing explicit status labels. Thin rules separate
measurement groups and distinguish controls from passive surfaces. Avoid glows,
bright gradients, large shadows and decorative hover movement.

## Type and ornament

- Keep bundled Plus Jakarta Sans for body text and controls, and JetBrains Mono
  for timestamps, provenance, metadata and forecast-window tags.
- Use a single locally served Latin Barlow Condensed semibold face for editorial
  headings. Its small WOFF2 asset is licensed under SIL OFL 1.1; retain the licence
  and source record beside it. Other scripts fall back to the existing body font.
- Preserve responsive font sizes in dense dossier controls; do not turn table
  cells, values or long evidence excerpts into condensed display text.
- Add one original SVG of architectural arches and orbital construction lines.
  It is a decorative CSS background on broad research headings, has no semantic
  content, never sits beneath evidence text and is omitted on narrow screens.
  No Hermes artwork, branding or third-party engraving is used.
- A low-contrast static grid belongs on the canvas only. Evidence, tables and
  forms use opaque surfaces so texture does not reduce reading contrast.

## Components and chronology

Domain entry, identity confirmation, real job progress and evidence drawers keep
their exact controls and content. Forecast windows use outlined monospace tags;
measurement dates and provenance use tabular numerals. Existing event sections and disclosures gain
a fine vertical rule and small static markers. This does not reorder events or
infer missing dates. Unknown, partial and failed states retain their existing
words and source limitations.

Directory, comparison, report and legacy views adopt the same surface and status
tokens after the main research flow is verified. The legacy SVG chart reads theme
colours for axes, line, points and tooltip only; its values, ordering, gaps,
accessible description and disabled animation remain unchanged.

## Accessibility and rollback

- Keep native semantics, visible focus, skip navigation, focus traps, restoration,
  inert disclosures and keyboard tab selection. Native form controls opt into a
  dark colour scheme; control boundaries and focus rings need at least 3:1.
- Target WCAG AA text contrast (4.5:1 normal, 3:1 large). Test actual computed
  surfaces, including notices, selected tabs, links and drawer text with axe.
- Respect reduced-motion through the existing root provider and browser tests.
  No theme animation or per-frame state updates are needed.
- Preserve internal scrolling on tables and evidence panels; check narrow
  screens, text zoom and absence of viewport overflow.
- Retain the old stylesheet declarations. Revert the root class/import to roll
  back the theme, and the chart falls back to the prior light palette.

## Staged validation

1. Start from integrated main `8cbac0f`; retain desktop/mobile screenshots and
   baseline browser results under `tests/outputs/theme-baseline`.
2. Add shared tokens/type, then the domain-research flow and drawer surfaces.
3. Run research and accessibility regressions and inspect comparison captures.
4. Extend the verified palette to directory, comparison, reports and legacy views.
5. Run the complete frontend unit and browser suites, generated-type check,
   formatting and production build. Retain all captures, including failures,
   under unique `tests/outputs/theme-*` directories.
6. Open a PR only after the full suite and build pass. Record final evidence,
   asset sizes, modified files and remaining visual limits below.

### Baseline findings

- Existing 36 browser cases pass on integrated main.
- The additional seven-screen, two-viewport audit found pre-existing keyboard
  access gaps in three scrollable dossier measurement panels and the legacy
  history table. Added labelled, keyboard-focusable scroll regions without
  changing measurements, ordering or interaction handlers.
- The unchanged light presentation now passes that complete surface audit.
  Before captures are retained in `tests/outputs/theme-baseline-accessible`;
  the original findings remain in `tests/outputs/theme-baseline-surfaces`.

## Implementation and validation report

### Modified files

| File                                                         | Purpose                                                                                                                                       |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/design/TECHNO-CLASSICAL-THEME.md`                      | Theme specification, staged audit, rollback and this delivery report.                                                                         |
| `frontend/index.html`                                        | Opt into the root theme class before React mounts.                                                                                            |
| `frontend/src/main.tsx`                                      | Import the additive theme after existing layout/motion styles.                                                                                |
| `frontend/src/theme/theme.css`                               | Palette/type tokens, shared surfaces, controls, evidence chronology, original ornament, forced-colour treatment and short-viewport scrolling. |
| `frontend/src/theme/assets/barlow-condensed-latin-600.woff2` | Local 22,308-byte heading face; body/metadata fonts are reused.                                                                               |
| `frontend/src/theme/assets/OFL.txt`                          | Font licence retained with the asset.                                                                                                         |
| `frontend/src/theme/assets/NOTICE.md`                        | Asset provenance and attribution.                                                                                                             |
| `frontend/src/theme/assets/observatory.svg`                  | Original 755-byte decorative line engraving.                                                                                                  |
| `frontend/src/components/HistoryChart.tsx`                   | Read shared colour tokens for chart presentation; preserve the light fallback, values, gaps and disabled animation.                           |
| `frontend/src/pages/research/CompanyDossier.tsx`             | Label/focus scrollable measurements; attach styling classes to existing events/timestamps.                                                    |
| `frontend/src/pages/tool-detail/ToolDetail.tsx`              | Label/focus the existing scrollable history table.                                                                                            |
| `frontend/tests/e2e/theme.spec.ts`                           | Seven-screen desktop/mobile screenshots, axe audits, keyboard scroll/focus, short viewport, forced colours and rollback coverage.             |
| `frontend/tests/unit/theme.test.ts`                          | Sixteen actual-token contrast checks for text and control boundaries.                                                                         |
| `frontend/tests/real-company/research.spec.ts`               | Assert Escape finishes closing the drawer before the settled-state accessibility audit; retain all original assertions.                       |

The existing `styles.css`, `workspace.css`, motion library, routes, dependency
manifests, backend, API contracts and generated types are unchanged.

### Validation evidence

- Baseline: 36 existing browser cases pass. The additional surface audit passes
  after the two keyboard-accessibility fixes described above.
- Research stage: eight focused domain/report, drawer, reduced-motion and real
  state-transition cases pass; 43 existing frontend units and build pass.
- Complete surface migration: 14 screenshot/axe cases pass across 1440×900 and
  375×812. The 16 new token checks meet 4.5:1 text and 3:1 control boundaries.
- Short-viewport inspection exposed the pre-existing fixed-height workspace
  clipping at 720×450 (the CSS reflow area of a 1440×900 window at 200% zoom).
  The theme now permits main-region scrolling at heights up to 600px; the test
  verifies the evidence ledger is reachable and fully inside that region.
- Existing tests also exercise 200% root text size, mobile selection, Escape,
  focus restoration, live reduced-motion changes and steady polling responses.
- The optional real replay initially audited during an outgoing drawer fade.
  Adding an explicit closed-dialog assertion fixes the race without disabling
  axe rules or changing the animation. All three real publication/dimension/
  immutable-report cases pass with collection disabled.
- Production preview of real Qdrant navigation, desktop/mobile dossier and source
  drawer is checked separately from fixtures. No vendor collection is triggered.

Final commands: `npm run format:check`, `npm run build` (canonical generated-type
check plus TypeScript and Vite), `npm test`, and `npm run test:e2e -- --workers=1`.
The optional real replay uses `playwright.company.config.ts` with the restored
publication and collection disabled.

### Captures and size

Local artifacts remain under ignored `tests/outputs/` and are not application
assets. No test outputs, including initial failures, were deleted.

| Evidence                                         | Directory                   |
| ------------------------------------------------ | --------------------------- |
| Before: all existing browser workflows           | `theme-baseline`            |
| Before: seven surfaces at both viewports         | `theme-baseline-accessible` |
| Research stage comparison                        | `theme-research-stage`      |
| Full themed surfaces and final regression run    | `theme-final`               |
| Keyboard/short-height and forced-colour captures | `theme-short-viewport`      |
| Real publication, dimensions and legacy report   | `theme-real-final`          |
| Local production Qdrant/home/source views        | `theme/live-preview`        |
| Legacy chart at both viewports                   | `theme/chart`               |
| Command logs                                     | `theme`                     |

Compared with integrated main, CSS gzip increases from 13.21 KB to 16.02 KB;
entry JS from 170.74 KB to 170.80 KB; lazy chart JS from 171.91 KB to 172.07 KB.
The one new font is 22.31 KB and the SVG is 755 bytes. No package dependency,
remote font request, image library, video or animation asset is added. The
existing Vite warning about chunks above 500 KB remains; this work does not
change application chunking.

### Remaining visual limits

No known contrast, viewport-overflow or clipped-control regressions remain in
the audited Chromium flows. Wide data tables retain their deliberate internal
horizontal scrolling. The existing compact mobile layout still truncates long
company names visually while retaining their full DOM/accessibility text.

Non-Latin headings use the existing body-font fallback because the extra display
face is Latin-only. Native select/checkbox appearance varies by platform and is
intentionally retained. Safari/Firefox and actual operating-system zoom UI were
not exercised; the checks cover Chromium, 200% text-size and zoom-equivalent CSS
viewport reflow. These are verification limits, not claims of cross-browser
pixel identity.

### Final result

- 59 frontend unit tests pass, including all 16 token contrast checks.
- All 52 default browser tests pass on the final implementation.
- Three optional real-company publication/dimension/immutable-report browser
  tests pass, and the local production-preview smoke check passes.
- Formatting, canonical generated types, TypeScript and Vite production build
  pass. Existing CSS/layout/motion and all protected backend/API paths are intact.
- The side-by-side desktop comparison is retained at
  `tests/outputs/theme/comparison-desktop.png`.
