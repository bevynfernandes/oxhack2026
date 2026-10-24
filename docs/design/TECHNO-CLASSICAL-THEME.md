# Techno-Classical Retrofuturist theme

## Intent and boundaries

SignalShift is a research instrument: editorial hierarchy and etched geometry
frame dated evidence, rather than suggesting certainty or futuristic prediction
capabilities. The theme changes presentation only. Routes, data semantics,
backend/API contracts, generated types, functional components and test assertions
remain intact. Existing stylesheets stay in place beneath an additive theme.

The root `theme-techno-classical` class enables `src/theme/theme.css`. Removing
that class restores the preceding presentation. The theme owns its responsive presentation overrides; preserve the original
layout underneath it and keep Material 3 Expressive motion in its existing module; no new animation engine,
page timing, animated data or extra JavaScript dependency is introduced.

## Palette and hierarchy

| Role                   | Token                  | Colour    |
| ---------------------- | ---------------------- | --------- |
| Canvas                 | `--theme-canvas`       | `#0d0d24` |
| Surface                | `--theme-surface`      | `#14142b` |
| Raised surface         | `--theme-raised`       | `#202037` |
| Primary text           | `--theme-text`         | `#f2f0e9` |
| Secondary text         | `--theme-muted`        | `#b5b5c5` |
| Technical rule         | `--theme-line`         | `#414154` |
| Input/control boundary | `--theme-control-line` | `#7e7e99` |
| Electric blue          | `--theme-accent`       | `#aaaaff` |
| Cobalt action/frame    | `--theme-action`       | `#0000f2` |
| Cobalt hover           | `--theme-action-hover` | `#3030ff` |
| Selected surface       | `--theme-selected`     | `#29294c` |
| Warning/evidence gap   | `--theme-warning`      | `#e8c58b` |
| Error                  | `--theme-danger`       | `#ffb0a7` |
| Confirmed source state | `--theme-positive`     | `#a7d1bf` |

Warm ivory is reserved for readable primary content; muted text remains readable
at small sizes. Blue denotes navigation, focus and selection, not model quality.
Amber and red support existing explicit status labels. Thin rules separate
measurement groups and distinguish controls from passive surfaces. Avoid glows,
bright gradients, large shadows and decorative hover movement.

## Reference and composition

The revised theme follows the [Hermes Agent landing page](https://hermes-agent.nousresearch.com/),
inspected visually and through computed styles on 2026-10-24. The reference uses
near-black indigo (`rgb(13,13,36)`), cobalt (`rgb(0,0,242)`), a narrow perimeter
frame, very light condensed headings, uppercase navigation and monochrome etched
illustrations. The previous theme only recoloured the existing dashboard; this
revision changes hierarchy, spacing and composition as well.

- Home has a split editorial heading/illustration above a ruled company directory.
  Company actions and search retain the existing handlers, pagination and content.
- Domain research pairs its large heading with the same illustration; dossiers
  use a compact identity masthead, separated statistics and square dimension panels.
- Mobile uses smaller display sizes and a compact illustration. All main content
  can scroll vertically; the explicit `minmax(0, 1fr)` shell column prevents
  intrinsic content widths from putting controls outside the viewport.
- Cobalt is used for filled actions and the frame. Text links use a lighter blue
  to meet contrast on dark backgrounds; the exact saturated reference blue is
  unsuitable for small text on those surfaces.

## Type and ornament

- Keep bundled Plus Jakarta Sans for reading text and JetBrains Mono for timestamps,
  provenance, metadata and forecast-window tags.
- Use local Barlow Condensed 200 for large editorial headings and 600 for small
  uppercase navigation/controls. Both are SIL OFL 1.1. The reference's proprietary
  Rules fonts are not bundled; Barlow is the licensed condensed substitute.
- Keep data cells, values and long evidence excerpts in their existing readable fonts.
- `armillary.svg` is an original 6.67 KB geometric engraving with meridians, orbital
  rings and a pedestal. `grain.svg` is a 331-byte static texture tile. Both are
  decorative CSS backgrounds, excluded from forced-colour mode, with no animation.
- Keep the earlier `observatory.svg` asset for the retained first-pass design.
  No Hermes branding, artwork, font binaries or source code is copied.
- Evidence, tables and forms retain opaque surfaces for readable contrast.

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
| `frontend/src/theme/assets/barlow-condensed-latin-200.woff2` | Local 14,616-byte extra-light display face; same OFL licence.                                                                                 |
| `frontend/src/theme/assets/armillary.svg`                    | Original 6,665-byte etched orbital illustration.                                                                                              |
| `frontend/src/theme/assets/grain.svg`                        | Original 331-byte static texture tile.                                                                                                        |
| `frontend/src/theme/assets/OFL.txt`                          | Font licence retained with the asset.                                                                                                         |
| `frontend/src/theme/assets/NOTICE.md`                        | Asset provenance and attribution.                                                                                                             |
| `frontend/src/theme/assets/observatory.svg`                  | Original 755-byte decorative line engraving.                                                                                                  |
| `frontend/src/components/HistoryChart.tsx`                   | Read shared colour tokens for chart presentation; preserve the light fallback, values, gaps and disabled animation.                           |
| `frontend/src/pages/research/CompanyDossier.tsx`             | Label/focus scrollable measurements; attach styling classes to existing events/timestamps.                                                    |
| `frontend/src/pages/tool-detail/ToolDetail.tsx`              | Label/focus the existing scrollable history table.                                                                                            |
| `frontend/tests/e2e/theme.spec.ts`                           | Seven-screen desktop/mobile screenshots, axe audits, keyboard scroll/focus, short viewport, forced colours and rollback coverage.             |
| `frontend/tests/unit/theme.test.ts`                          | Eighteen actual-token contrast checks for text and control boundaries.                                                                        |
| `frontend/tests/real-company/research.spec.ts`               | Assert Escape finishes closing the drawer before the settled-state accessibility audit; retain all original assertions.                       |

The existing `styles.css`, `workspace.css`, motion library, routes, dependency
manifests, backend, API contracts and generated types are unchanged.

### Initial theme validation evidence

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

### Initial theme result

- 59 frontend unit tests pass, including all 16 token contrast checks.
- All 52 default browser tests pass on the final implementation.
- Three optional real-company publication/dimension/immutable-report browser
  tests pass, and the local production-preview smoke check passes.
- Formatting, canonical generated types, TypeScript and Vite production build
  pass. Existing CSS/layout/motion and all protected backend/API paths are intact.
- The side-by-side desktop comparison is retained at
  `tests/outputs/theme/comparison-desktop.png`.

## Reference-led revision — 2026-10-24

### Changed files in this revision

- `frontend/src/theme/theme.css`: reference-matched indigo/cobalt palette, blue
  frame, lighter editorial typography, split home/research compositions, ruled
  dossier layout, compact laptop/phone overrides and intrinsic-width safeguards.
- `frontend/src/theme/assets/barlow-condensed-latin-200.woff2`: local extra-light face.
- `frontend/src/theme/assets/armillary.svg`: original decorative engraving.
- `frontend/src/theme/assets/grain.svg`: static low-opacity texture.
- `frontend/src/theme/assets/NOTICE.md`: additional asset provenance and licence record.
- `frontend/tests/e2e/theme.spec.ts`: assert main-region horizontal overflow as
  well as document overflow; update the explicit canvas colour assertion.
- `frontend/tests/unit/theme.test.ts`: add contrast checks for white text on
  cobalt action and hover surfaces, preserving all previous contrast thresholds.
- `docs/design/TECHNO-CLASSICAL-THEME.md`: revised specification and verification record.

### Regression findings and fixes

- The perimeter frame exposed an implicit grid minimum that could push mobile
  controls outside the main region. An explicit shrinking grid column fixes it;
  the stronger main-region check now catches the problem independently of the
  document-width check. Native long-option snapshot selects can also shrink.
- Larger dossier typography initially violated the existing no-scroll overview
  contract. Compact height breakpoints restore that contract at 1440×900,
  1366×768, 1280×720, 390×844 and 375×667 without changing the original test.
- Pagination remains in view on short phones. At 720×450 zoom-equivalent reflow,
  vertical scrolling keeps the ledger reachable instead of compressing evidence.
- No existing functional assertion, axe rule, motion test or contrast threshold
  is removed or relaxed. No backend/API/generated-type/component logic changes
  are part of this revision.

### Evidence and size

- 61 unit tests pass, including 18 contrast checks.
- All 52 default browser tests pass on the final revision, including desktop/mobile
  screenshot and axe checks, one-screen dossier geometry and shared motion regressions.
- Formatting, canonical generated types, TypeScript and production build pass.
- Three real publication/dimension/immutable-report cases pass with collection
  disabled; captures and report are in `tests/outputs/hermes-real-final`.
- Live production Qdrant inspection verifies dimension expansion, tab changes,
  Escape and focus restoration. No collection jobs are submitted.
- Before captures remain in `tests/outputs/theme-final`; revised screenshots,
  axe audits and motion captures are in `tests/outputs/hermes-final`.
- Side-by-side home/domain/dossier comparison:
  `tests/outputs/theme/reference-comparison.html`.
- Earlier failed audit outputs are retained in `hermes-surfaces`,
  `hermes-surfaces-v2` and `hermes-full`; the focused dossier correction passes
  in `hermes-dossier-fit`. Command logs are in `tests/outputs/theme/hermes-*.log`.
- Compared with the previous theme, CSS gzip changes from 16.02 KB to 17.10 KB;
  entry JS stays approximately 170.80 KB and lazy chart JS stays 172.07 KB.
  Added assets: 14.62 KB local font, 6.67 KB SVG (1.65 KB gzip) and 331-byte
  grain tile. No package dependencies or remote application asset requests.
- The existing large-chunk build warning remains. The earlier Chromium-only
  verification limits and native-control/non-Latin fallback differences apply.
  This follows the reference's visual language, using an OFL font substitute and
  original artwork rather than claiming identical branded pixels.

### Integration with the new evidence-mapping UI

- Main advanced during delivery to `f1b7e65` (mapped evidence presentation and
  immutable re-mapping). Integrated that UI into the theme branch while retaining the other
  developer's work.
- The only conflict was the measurement wrapper: retain both the theme's labelled
  keyboard-scroll region and the new backend-provided coverage/claim/event counts.
  New mapping controls, attributed quotes, links, polling and explicit writes are
  unchanged from main. Backend/API/generated-type files have no PR diff.
- Integrated formatting, generated types, TypeScript, build and 63 unit tests pass.
  The two additional units are the other developer's mapping tests.
- The optional live re-mapping browser case requires a retained mapped report and
  configured mapping worker; no report ID was supplied, so it remains explicitly
  skipped. Existing publication/dimension/immutable-report replay remains enabled.
- Integrated application size is CSS 17.23 KB gzip, entry JS 172.05 KB and chart
  JS 172.07 KB. The extra JavaScript comes from the newly integrated mapping UI;
  the theme revision itself added no application JavaScript.
- A new mapping link increased the summary row height. Compact mapping-action
  typography and model-note spacing keep the original standalone report geometry
  checks passing. Inline-control hover remains transparent.
- Final integrated browser artifacts and logs use `hermes-delivery` and
  `hermes-delivery-real`. The initial integrated run and focused spacing regression
  remain in `hermes-integrated` and `hermes-mapping-fit`; earlier captures are kept.
- Final integrated result: 63 unit tests, all 52 default browser tests, three real
  replay cases, formatting, generated types, TypeScript and production build pass.
  One optional live re-mapping case is explicitly skipped for the missing report
  fixture described above. No known visual or interaction regression remains in
  the audited Chromium flows.
