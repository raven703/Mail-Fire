# Native UI scenario inventory (continuation from cc190a8)

Reference is read-only `master:frontend/src`; no React runtime is introduced.
Implemented does not mean browser/screenshot acceptance. Full testing is deferred.

| Original components | Native counterpart | Remaining functional/visual work |
|---|---|---|
| main, NavIcon, components | identity/base, native shell, local HTMX | icons and global search (grouped navigation/collapse and original 24h/7d/30d/custom date controls implemented) |
| SecurityOverview | records/overview, _overview_panels, original CSS | original trend segmentation and service summaries (risk distribution and priority list implemented) |
| IncidentTable, IncidentCategoryFilter | records/incidents, workspace; multi-category/severity/date/assignee filters | compact sender layout, remaining original filters and picker styling |
| IncidentActions, IncidentTraining | records/incident, datasets | original action layout (explicit incident-training modal implemented) |
| MessageSelection | records/messages; source/direction/date filters, attachment/incident counts | delivery metadata columns (page selection, bounded bulk full reanalysis, per-item results and retry implemented) |
| Evidence, MessageAttachments | records/message, _message_tabs, attachment | full evidence summaries/highlights, matching original viewer layout |
| PolicyEditor, CategoryPicker | policy_engine/catalog, categories | picker styling (structured keyword/flexible-term/regex/reference/ML fields now shared by standalone and nested editors; nested edit/create and summaries implemented) |
| CategoryManagement | policy_engine/categories | editor visual parity and all original inline interactions |
| Accounts, EditorDialog | identity/users, dialogs.js | browser acceptance |
| Management, RulepackTransfer | records/catalog/references/imports, rulepacks | per-catalog comparison and dialogs |
| MLDatasets, LLMSettings | records/datasets/models/llm | training panel/workflow comparison |
| Operations, Queues, SystemStatus | pipeline/operations | queue p95/graphs, complete service telemetry and original multi-panel layout |

Original security-overview, message-detail, message-selection,
incident-category-filter and system-status styles copied verbatim and loaded.
Date filters/pagination preserve query parameters. Message tabs progressively
enhance visible server sections and support keyboard navigation. Resource probes
report unavailable GPU honestly; nvidia-smi must be exposed by the deployment.
No Docker socket, host mounts or live container changes added.

Inference artifacts are now independent content-addressed binary copies in
`inference_artifacts`, created in the caller's dispatch transaction. A migration
is supplied but NOT applied. Retention deliberately keeps these copies; no new
artifact GC policy is introduced. Existing queued pre-migration snapshots need
re-dispatch to populate copies; no unsafe model-row fallback is used.