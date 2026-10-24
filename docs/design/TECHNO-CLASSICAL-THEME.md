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

| Role | Token | Colour |
| --- | --- | --- |
| Canvas | `--theme-canvas` | `#090f1b` |
| Surface | `--theme-surface` | `#101a2a` |
| Raised surface | `--theme-raised` | `#172438` |
| Primary text | `--theme-text` | `#f1ecdf` |
| Secondary text | `--theme-muted` | `#acb9cb` |
| Technical rule | `--theme-line` | `#34445b` |
| Input/control boundary | `--theme-control-line` | `#7185a2` |
| Electric blue | `--theme-accent` | `#8bb5ff` |
| Selected surface | `--theme-selected` | `#203655` |
| Warning/evidence gap | `--theme-warning` | `#e8c58b` |
| Error | `--theme-danger` | `#ffb0a7` |
| Confirmed source state | `--theme-positive` | `#a7d1bf` |

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
measurement dates and provenance use tabular numerals. Existing event lists gain
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
