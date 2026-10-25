# Approachable research UI

- Audience: someone investigating one company, moving from identity to outlook,
  business dimensions and supporting evidence.
- Direction: a warm editorial research desk. Peach surfaces, an orange-gradient home canvas, dark
  ink, bright orange actions and the existing engraved illustration.
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
| Canvas / surface / raised    | `#ffe2c7` / `#fffaf5` / `#f2f2f7` |
| Text / secondary text        | `#14141a` / `#6c5141`             |
| Rules / control boundaries   | `#d6a67c` / `#8a5a35`             |
| Link and focus accent        | `#7a3600`                         |
| Action / hover / action text | `#ff8200` / `#e87200` / `#14141a` |
| Selected surface             | `#ffd1a6`                         |
| Control / panel radius       | `8px` / `16px`                    |
| Spacing                      | `8px` / `16px` / `24px` / `32px`  |

- Use `--theme-on-action` for text on filled primary actions; `--theme-text`
  belongs on paper/neutral surfaces. Contrast tests cover the actual pairs.
- Retain labelled warning, error and positive-source colours. Orange does
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

## Changed files

- `frontend/src/theme/theme.css`: shared palette, typography, panel geometry,
  search/result layout, touch targets and responsive presentation.
- `frontend/src/pages/companies/CompanyHomePage.tsx`: form styling hook,
  confirmation help text and the saved-research heading; handlers unchanged.
- `frontend/tests/unit/theme.test.ts`: check the new explicit action-text token
  against both primary action backgrounds using the existing AA threshold.
- `frontend/tests/e2e/theme.spec.ts`: updated canvas expectation and additional
  320px, 768px and 1024px target-size, keyboard, overflow and accessibility checks.
- `docs/design/TECHNO-CLASSICAL-THEME.md`: link the historical foundation to the
  current presentation guide.
- `docs/design/APPROACHABLE-RESEARCH-UI.md`: design decisions and delivery record.

## Remaining constraints

- Evidence panels retain their existing compact metadata and internal scrolling;
  the page-fit regression still covers laptops and phones down to 375 × 667.
- The narrow-screen footer keeps its existing truncated qualification; complete
  explanations remain on the report and methodology pages.
- The production build still reports the existing large JavaScript chunk warning.
  This refinement adds no package, chart animation or new animation engine.

## Delivery validation

- Base: PR #86 at `cdabe8037ce050c8ed55986b78ee3b8efbe57f55`.
- Unit suite: 71 passed, including spring physics, reduced motion, ambient motion,
  disclosure lifecycle, engine boundaries and token contrast.
- Browser suite: 55 passed, including axe audits, five dossier viewport sizes,
  keyboard/Escape/focus restoration, responsive tables, route motion and polling.
- Generated API types, TypeScript, production build and frontend formatting pass.
- Real local-backend smoke: Qdrant opens, Adoption & Retention opens and closes
  with Escape, no page errors and no horizontal document overflow on mobile.
- No changes to backend, contracts, API client, dependencies or motion code
  relative to PR #86. No live research/collection job was started for visual QA.
- Baseline captures: `tests/outputs/ui-polish-before/` (integrated main at
  `64fa8d6`, before applying the refinement).
- Final screenshots and traces: `tests/outputs/ui-polish-integrated/`.
- Local-backend captures: `tests/outputs/ui-polish/live/`.
- Logs: `tests/outputs/ui-polish/integrated-{unit,browser,build,format}.log`.

## Screenshot palette refinement

- Match the supplied peach/orange reference on port 5174 using the original PR #86 colour tokens.
- Add shared fine horizontal/vertical grid backgrounds to the three homepage panels.
- Keep the current hierarchy, handlers, motion library and backend unchanged.
- Primary orange buttons use dark text to preserve contrast. Grid textures are removed in forced-colour mode.
- Revalidated the screenshot palette: 71 unit tests, 55 browser tests, generated types,
  TypeScript, production build and formatting pass. Logs: `tests/outputs/ui-orange/`;
  desktop/mobile captures: `tests/outputs/ui-orange-browser/`.
