# Unified Mail-Fire UI controls — style contract

This PR is **visual only**. The user's existing Mail-Fire light and dark
palettes are intentional and must be preserved. No backend, API, migrations,
DLP logic, React component behavior, or access control changes are required.

## Current CSS audit

Prior to this change, `frontend/src/style.css` mixed several generations of
CSS: initial 7px field/button radii, later compact toolbars, per-page filters,
a separate modal design, circular custom category checkboxes, and older native
checkboxes in other sections. Some labels were `display:grid` while others
used `display:flex`; selects alternated between browser-native arrows and
custom rounded designs. The reference image also uses compact typography and
gentle borders.

## Canonical rules

`frontend/src/controls.css` is imported after `style.css` and is now the
**only intended place to modify the visual contract for common controls**.

- Colors: **inherit** `--card`, `--text`, `--muted`, `--border`,
  `--selected` and `--accent` in both themes. Keep existing purple primary
  buttons. Do **not** turn the overall product grayscale.
- Inputs: height 40px, consistent 10px corners and border, no heavy shadows.
- Selects: height 40px, pill shape, thin custom chevron on the right;
  list semantics remain native.
- Buttons: compact 38px, 10px radius, consistent font and visible focus.
  Primary buttons retain current accent and white text.
- General checkboxes: 19px square, slightly rounded corners, high contrast
  checkmark when selected, native `input[type=checkbox]`.
- Radio buttons: 19–20px round, dark (light theme) / light (dark theme)
  selected fill and small opposite-color centered dot; native semantics.
- **Category multi-select checkboxes** remain circular (as on the supplied
  category-picker screenshots) while remaining real checkboxes permitting
  multiple selection.
- Grouped category option rows remain full-width with consistent gaps.
- Dense filters: minimum 34px; no unwanted growth from generic controls.
- Do not alter navigation buttons, tabs, switches, chips or toolbar icon
  geometry. Focus-visible rings and disabled states apply throughout.
- Reduced motion is respected.

`main.tsx` imports `controls.css` *after* legacy styles so that the
shared contract is reliably applied on ALL pages. Avoid adding new ad hoc
button/checkbox/select declarations to `style.css`. Prefer adding a new
semantic modifier to `controls.css` when a real different control role is
needed.

## Manual and browser regression checklist

Visual acceptance is based on the **user's screenshots**, not just successful
TypeScript compilation. The source screenshots should be attached to the
agent's visual review; do not approximate from this document alone.

1. Run `npm ci && npm run build` in `frontend/`, inspect DOM and CSS.
2. Compare screenshots at the *same browser viewport and zoom* before/after.
   Check typography, 40px pill selects, circular radio checks, 19px square
   checkboxes, spacing, button radii and colors.
3. Check **light and dark** themes; accent palette, side navigation, risk
   badges, cards and charts should remain unchanged.
4. In the policy modal: category choice controls, ANY/ALL radio, buttons,
   selects and fields. Escape, close X and Cancel must work; clicking outside
   must not close; no form data is lost unexpectedly on interaction.
5. In Categories: creation and editing, rules enabling/disabling, multiple
   reference checkboxes, category selector multi-choice, search, creation
   modal. Selection circles are expected in category-picker *only*.
6. In ML: dataset import/upload, training options, checkboxes, example
   review, category selection. Test file inputs (not custom-styled).
7. In Accounts: role select, enabled/originals checkboxes and submit/cancel.
8. In Operations: retention setting checkbox, SIEM forms, queue tabs.
9. In Messages/Incidents: filter selects, search, pagination, controls,
   theme switch, global search and icon buttons.
10. Verify hover, focus-visible, keyboard Space/Arrow/Tab, native label click,
    disabled, invalid required inputs, keyboard accessibility and
    `prefers-reduced-motion` at 320, 375, 768, 1280 and 1920 px.
11. Check CSS override specificity. Legacy selectors should not take
    precedence over the shared controls accidentally. If they do, correct
    the legacy conflict rather than piling on `!important`.
12. Do NOT alter production data or merge automatically before reviewed
    screenshots and green build.

## Future maintenance

Prefer shared native controls with `className="primary"` for a primary
action. There is deliberately no new React UI library, dependency or
JavaScript state management layer. Avoid component wrappers which strip
native label/input semantics. Future UI design changes should extend
`controls.css` instead of introducing independent page-local styles.
