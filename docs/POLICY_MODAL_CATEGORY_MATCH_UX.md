# Policy modal and category matching UX (draft PR)

## Purpose

Match the compact, white, grouped category picker reference from the user screenshots.
Policy editing uses a native modal dialog rendered via a React portal. The
dialog stays open on outside clicks; Escape, X, and Cancel close it without
saving. Focus is moved into the dialog and the browser provides native modal
focus containment. All validation errors remain in the dialog.

## Actual policy semantics

- Policy detection does **not** train or run a separate detector. Existing
  detector findings are filtered by selected categories and per-finding risk.
- `min_risk = 40` means each qualifying finding must have risk **at least 40**.
- `min_count = 1` means **one qualifying finding total**, not one category.
- `category_match = any` (default for existing records): with A,B,C selected,
  **a single qualifying finding in A OR B OR C** suffices, subject to min_count.
  Two findings from one category can meet min_count=2.
- `category_match = all`: the findings must cover **A AND B AND C**, each with
  a qualifying per-finding risk; `min_count` additionally applies to the
  total number of findings. A min_count of 1 with 3 categories still needs at
  least 3 findings, one in each category.
- With **no selected categories** and mode `any`, all active categories
  are eligible. Mode `all` with an empty list is rejected by the API.
- Multiple findings can come from the same match via different detectors;
  this work does not deduplicate them. A future independent-findings mode
  may be added after detector consolidation.
- Sender/direction filters are applied separately to each delivery event.
- Priority orders evaluation; it is **not** a stop-processing or best-match
  switch. Multiple policies may create incidents for one event.
- Shadow mode does not create an incident. Mail-Fire is passive and does not
  block delivery.

## UI details

- `frontend/src/PolicyEditor.tsx`: compact header, name/risk/min-count/
  priority row, grouped category picker, explicit OR/AND radio selection,
  live human-readable trigger preview, collapsible advanced direction/sender
  filters and shadow/enable toggles, fixed footer actions.
- `frontend/src/CategoryPicker.tsx`: category search, grouped scrolling
  checklist, selected-count badge, selected name chips, reset, admin inline
  category creation. IDs are displayed subtly, not required to be entered.
- `frontend/src/Management.tsx`: opens the editor as a modal and shows
  human-friendly category names and matching mode in the policy list.
- `frontend/src/style.css`: responsive modal and category selector for light
  and dark color themes; background scroll locked during edit.
- `app/processing.py`: pure `policy_matches` helper ensures backend
  has the same semantics explained by the UI.
- `app/workspace_api.py`: validation and persistence of `category_match`.
  The mode is an optional JSON condition: **no SQL migration is needed**.
- `tests/test_policy_matches.py` and `tests/test_workspace.py` cover
  OR/AND, thresholds, existing-policy fallback and invalid empty ALL.

## Agent acceptance criteria

1. Check out the branch; do not merge without approval. User screenshots
   are the visual reference, but adjust CSS to the application's palette.
2. Run `cd frontend && npm ci && npm run build`; run Ruff and Python tests
   on a disposable PostgreSQL DB with existing schema.
3. Open existing and new policies; check Escape/X/Cancel, focus, keyboard
   operation, no outside-click dismissal, no implicit save.
4. Confirm backend + UI agree for 3 categories, risk 40, min count 1:
   default ANY accepts one finding in any chosen category; ALL needs a
   matching finding in all three.
5. Verify count=2 from the SAME category (ANY) and count=2 with 3 distinct
   categories (ALL). Risk 39 does not count.
6. Verify all delivery directions, shadow mode, saved old policies without
   `category_match`, new version changes, list rendering, category creation,
   and multiple separate incidents across policies.
7. Check desktop, mobile, dark/light theme, browser E2E, screen-reader
   labels, focus restoration, and report any failures.
8. Do not touch production data or push/merge automatically.
