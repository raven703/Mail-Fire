# Native UI scenario inventory

Reference components are in `master:frontend/src`. Native templates use the
original theme assets, icons and CSS where applicable and HTMX for server-rendered
updates. No browser acceptance was performed in this continuation.

| Reference | Implemented | Known outstanding implementation or comparison |
|---|---|---|
| main, NavIcon, components | Grouped sidebar with collapse and original icons/logos, topbar health, notification drill-down, global search, per-account theme and menu | Compare active states, mobile/sidebar layout and routing behavior |
| SecurityOverview and analytics | Separate overview and reports, period-aware KPIs, severity segmentation, priority list, policy bars, health links and CSV | Verify units, zero/missing states, live refresh and screenshots |
| IncidentTable / IncidentCategoryFilter | Compact sender layout, policy autocomplete, category/severity/status/source/direction/assignment filters and date/sort | Original keyboard combobox behavior is approximated by native datalist |
| IncidentActions / IncidentTraining | Assignment and decision dialogs, history/comments, incident labels and approval, nested category creation | Verify modal focus, validation and draft preservation |
| MessageSelection / MessageAttachments / Evidence | Page selection and bulk full reanalysis, six detail tabs, searchable recipients, attachment rows and modal, PNG/Office preview, nested mail metadata and DLP cards | Compare keyboard, focus restoration, preview fallback and presentation |
| CategoryPicker / PolicyEditor / CategoryManagement | Grouped search/chips/reset, category rules and nested creation/editing, policy draft preservation, catalog history and archive | Compare editor spacing, ordering and interactions |
| Management / RulepackTransfer | Policy statistics, switch and reevaluation, detector options, reference catalog with matches and indexing, rulepack preview/apply/export | Finish visual comparison for reference/detector/rulepack/settings flows |
| MLDatasets / MLTrainingOptions | Import dialog with source/mapping, review and deletion, manual-label picker, engine-specific options, jobs and model metrics/actions | Compare tabs, nested category creation and draft preservation. |
| Accounts / employee and address catalogs | Account dialogs and permission checks, linked employee/address pages and shared create/edit dialogs | Compare catalog navigation and modal presentation |
| Operations / Queues / SystemStatus | Queue, flow, resource, PostgreSQL and job views, worker and service health, history, refresh and filters | Verify all statuses and browser presentation with actual data |

Visual fidelity in light/dark modes, responsive widths and browser interactions
must be checked on the experimental stack. Code presence and runtime
verification are tracked independently.
