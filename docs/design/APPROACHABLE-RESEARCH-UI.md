# Approachable research UI

- Audience: someone investigating one company, moving from identity to outlook,
  business dimensions and supporting evidence.
- Direction: a warm editorial research desk. Ivory canvas, paper surfaces, dark
  ink, restrained terracotta actions and the existing engraved illustration.
- Hierarchy: make the search action unmistakable, distinguish saved dossiers
  from new research, and use quieter styling for supporting explanations.
- Typography: retain locally bundled Barlow Condensed for editorial headings,
  Plus Jakarta Sans for controls and reading, and JetBrains Mono for metadata.
  Supporting text must remain legible on phones; do not shrink a page to fit it.
- Layout: shared spacing and radius tokens; aligned cards; readable paragraph
  widths; the homepage scrolls rather than shrinking its text. The dossier keeps
  its existing compact overview and internal measurement scrolling. Tables keep
  their own scroll containers and preserve source ordering.
- Motion: retain the existing Material 3 Expressive library without changes.
  No additional animation engine, entrance effects or animated evidence.
- Behaviour: preserve every handler, API call, confirmation, route, disclosure
  and native dialog. Colours cannot imply an invented score or confidence level.
- Scope: frontend presentation, visual regression coverage and this document.
  No backend, schema, generated types or dependency changes.

## Design guidance

- Applied the accessibility, readable typography, semantic colours, spacing and
  responsive-layout guidance from
  [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
- Its generated portfolio/enterprise marketing patterns did not match this
  research application. They were not adopted; the product flow above determines
  the composition. Existing project motion rules take precedence over generic
  animation recommendations.
- The skill is a development aid, not a runtime dependency. No third-party
  components or artwork were copied into the application.

## Shared tokens

| Role                         | Value                             |
| ---------------------------- | --------------------------------- |
| Canvas / surface / raised    | `#f5f3ed` / `#fffdf8` / `#eae8df` |
| Text / secondary text        | `#252923` / `#62665c`             |
| Rules / control boundaries   | `#d8d8cc` / `#7b7e70`             |
| Link and focus accent        | `#943c24`                         |
| Action / hover / action text | `#a94125` / `#89321c` / `#ffffff` |
| Selected surface             | `#f5e4d9`                         |
| Control / panel radius       | `8px` / `16px`                    |
| Spacing                      | `8px` / `16px` / `24px` / `32px`  |

- Use `--theme-on-action` for text on filled primary actions; `--theme-text`
  belongs on paper/neutral surfaces. Contrast tests cover the actual pairs.
- Retain labelled warning, error and positive-source colours. Terracotta does
  not indicate company quality or a model prediction.
- Main search controls and saved-dossier links have at least 44px target heights.
- On narrow screens the decorative hero illustration is omitted, the form
  becomes one column, and company actions follow their identity and metadata.

## Verification

- Capture the integrated baseline and refined home/report at desktop and mobile.
- Run the full unit suite, generated-type check, TypeScript and production build.
- Run the full browser suite, including axe audits, drawers, disclosures,
  keyboard navigation, live reduced-motion preferences, zoom and overflow.
- Keep test reports and screenshots under ignored `tests/outputs/`.

## Integration

- Build on PR #86 (`codex/home-ui-motion-polish`), retaining its `MotionSurface`
  and `MotionAmbient` components, artwork, event handling and reduced-motion
  behaviour. Only their surrounding layout and surface styling are refined.
- Keep the moving artwork in its own non-interactive region beside the hero.
  Evidence, table values and source ordering remain immediate and unchanged.
- The existing working checkout and its untracked `Design.md` are not modified.
