# MICE UI component contract

## Ownership and cascade

The app uses Django partials, native controls, HTMX and the existing MICE palette.
No framework or backend changes are needed.

1. `static/mice/style.css`: palette and domain layouts (evidence, policies, charts).
2. `static/mice/ui.css`: page spacing, headers, panels, FilterBar, DataTable,
   Pagination, Badge, Tabs, EmptyState and spacing/radius tokens.
3. `static/mice/controls.css`: Button/IconButton and native Input/Select/Checkbox
   geometry, colors and hover/focus/disabled states. Links with `action-button`
   use the same contract as buttons, including `primary`.
4. `static/mice/editor-dialog.css`: the existing Modal shell and its single body
   scroll area. `dialogs.js` owns focus, closing and HTMX lifecycle behavior.
5. `static/mice/native-shell.css`: navigation, toolbar and shell breakpoints only.
6. Specialized styles own only their feature, not generic main/section/table or
   filter positioning. Weighted terms retain their existing shared editor.

Do not add global sticky filters, broad table/section selectors to feature files,
or higher-specificity overrides to compensate for another owner's definition.
Only the workspace toolbar/navigation are sticky. Page panels do not scroll;
`ui-table-scroll` is the horizontal overflow boundary for data tables. Document
and evidence viewers retain their intentional content scrolling.

## Partials (`templates/ui/`)

- `page_header.html`: `title`, optional `subtitle`, `count`, `actions_template`.
- `button.html`: `text`, optional `href`, `type` (default button), `variant`
  (`primary`), `name`, `value`, `disabled`.
- `icon_button.html`: accessible `label`, `icon_template` or `icon`, `disabled`.
- `input.html`: `label`, `name`, `value`, `type`, `placeholder`, `list`.
- `select.html`: `label`, `name`, `(value, label)` `options`, selected `value`.
- `field.html`: Django BoundField `field`, preserving server errors/help/widgets.
- `checkbox.html`: `label`, `name`, `value`, `checked`, `disabled`.
- `multiselect.html`: `label`, `name`, model `options`, selected primary keys
  `selected`; uses native checkboxes and a semantic fieldset, no second picker JS.
- `filter_bar.html`: `fields_template`, optional `action`, `layout`.
- `data_table.html`: `label`, `content_template` (thead/tbody), `table_class`.
  Tables with complex existing inline markup share `ui-data-table` and
  `ui-table-scroll` rather than duplicating their presentation.
- `pagination.html`: existing `page`, `pagination_query`; the legacy records
  include forwards here so all paginated pages share one implementation.
- `badge.html`: `text`, `variant`; existing `.badge` markup shares its styling.
- `modal.html`: `id`, `title`, `content_template`, optional `close_url`,
  `dialog_class`, `submit_label`. Uses the established `data-editor` contract.
- `tabs.html`: `label`, `tabs` with `href`, `title`, `active`. Existing JS tabs
  retain `data-tabs` / `data-tab` and share `.tabs` presentation.
- `empty_state.html`: `text`.

Use `only` when including simple value-only components to avoid context leakage.
Form/table body templates deliberately inherit permission and request context.
Never construct trusted HTML from user-provided strings.

## Incidents

Six primary filters form a responsive three-column grid. Additional filters
remain native controls within details; selected advanced filters reopen it after
GET/HTMX navigation. Names, choices, permission checks and query handling remain
unchanged. All seven privileged table columns are preserved, including sender,
recipient and timestamp; narrower windows scroll the table horizontally.

## Quick validation

## Workspace periods and section shells

`records.ui_filters.resolve_period(request)` is the session-backed contract for
overview, incidents, messages and analytics. Explicit valid URL dates win;
invalid/incomplete custom dates leave session state unchanged. Ranges are rolling
24/168/720 hours; custom bounds retain independent offsets for DST boundaries.
The shared `_global_period.html` lives in the page header, submits through HTMX,
preserves applied local parameters and omits pagination on a period change.
Overview polls neither write period session state nor replace newer UI responses.
Queue/service cards remain live measurements, independent of the period.

`ml_base.html` and `settings_base.html` own their stable section heading and tabs.
Monitoring uses the shared tabs and one navigation entry; existing tab URLs stay
valid. `check_workspace_sections.py` is a read-only browser regression, including
the four-page period journey, custom period, history, reset and CSV. It never
submits training, inference, retention or GC actions.

## Category catalog and editor

The category catalog uses shared `ui-disclosure`, `ui-data-table-compact` and
`ui-action-menu` primitives. Rule counters come from the read-only `category_ui`
template tag (one aggregate query), not from detection logic or model changes.
Descriptions remain available as title tooltips and in the read-only detail.

The category Modal uses `data-tabs` and `ui-form-grid`; both panels stay in the
same POST form, so switching tabs never serializes or discards field values.
Category panels own their scroll positions; the shell, tab strip and footer do
not scroll. The formset starts with zero extra forms. Trash actions stage DELETE
until submission, offer undo for persisted rules and hide new discarded forms.
Persisted rules use `deleted_at`, retaining IDs and audit events; the default
manager excludes tombstones from editor, counters, exports and detection inputs.
Evidence resolves original metadata from existing configuration snapshots and
AnalysisRevision records. New findings reference the snapshot hash, without
duplicating configurations. Missing legacy snapshots are explicitly indicated;
current rule parameters are never substituted for missing historical data.
Invalid native fields activate their containing tab and expand their rule.
Rule forms retain their original management fields, DELETE flags and ordering.
An accordion presents summaries and opens the existing structured editor inline.
`check_category_ui.py` performs a read-only browser regression in both themes
at 1024/1280/1920 px, including unsaved values, weighted terms and system rows.

`python scripts/check_ui_system.py` uses the already available Playwright and
requires `ADMIN_PASSWORD`. Optional environment: `MICE_UI_URL`,
`MICE_CHROMIUM_PATH`, `MICE_UI_SCREENSHOTS`. It does not submit data-changing
forms. It checks 1024/1280/1920 pixels in both themes, filter/reset behavior and
HTMX navigation. Existing Django tests cover server permissions and forms.