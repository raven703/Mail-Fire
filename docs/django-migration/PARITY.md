# Functional parity matrix

Current status after the continuation from `841be5c`. “Implemented” records
available code paths. Integration, browser, holdout and load acceptance are
separate. The architecture contract is in [PLAN.md](PLAN.md).

| Capability | Current implementation | Remaining work or verification |
|---|---|---|
| Authentication and access | Django sessions, legacy password adapter, account CRUD/revocation, independent originals capability and saved theme | Verify live account/role × action matrix and legacy adoption |
| Upload, ZIP, directory, SMTP | Shared durable acceptance, stable delivery keys, per-file browser results, isolated ZIP expansion, SMTP receipt handling, read-only directory watcher with durable failures | Verify duplicate, partial and delivery failure cases |
| Parser/OCR/Converter | Isolated services, bounded calls, extraction and OCR jobs, passive rasterization | Verify rebuilt images and nested/Office/scan fixtures |
| Deterministic detectors | Reused original PII/static/secrets/normalizer, category rules, fingerprint and document-type algorithms; AV and detector configuration | Run original holdout and disabled/unavailable-state acceptance |
| Reference library and pgvector | Upload, original matches, settings, delete, manual/optional automatic reindex, async semantic search | Verify indexed counts, PostgreSQL locks and embedding snapshot/runtime |
| Policies and rulepacks | Versioned CRUD, history, toggles, rules, shadow mode, rulepack preview/apply, saved-evidence single/batch reevaluation | Verify ordering, deduplication, version preservation and transactional error cases |
| Incidents and message detail | Unified incident, action dialogs, assignment/comment/history, filters/search, bulk full reanalysis, six message tabs and gated attachment modal with nested EML/MSG metadata | Browser interactions and live persistence/concurrency |
| Overview and analytics | Separate views, rolling/custom ranges, risk bands, grouped timeline, policy snapshot counts, priority list, processing links and CSV | Verify PostgreSQL aggregation and browser refresh/drill-down |
| Datasets and training | Source/mapping import, duplicate detection and versioning, review and approval, example/dataset deletion, manual/incident labeling, engine-specific training jobs and quality views | Verify nested creation and draft preservation, model lifecycle and corpus provenance |
| Optional ML/LLM | Provider/model adapters and native settings behind deployment gates; disabled | Builds and disabled-path acceptance; no provider tests in this stage |
| Employee/address catalogs | Native list/search and create/update with contact mapping | Browser layout and original interaction parity |
| Queues, resources and audit | Celery lease/job controls, RabbitMQ stats, queue/flow/PostgreSQL panels, health and per-service cgroup sampling, metric history, diagnostic and audit views | Verify all profiles, cgroup/permissions, clock and PostgreSQL statistics in deployment |
| Notifications and retention | Durable SIEM attempts, legal hold, previews, confirmed cleanup, bounded log TTL and reference-aware GC | Scheduled destructive cleanup remains open; verify concurrency and storage integrity |
| Build and offline | Standalone image definitions and dependency locks, offline compose/probe, images and optional neural snapshots with checksums | Build all images, run clean-host restore; automated signed updater absent |
| UI | Server templates, HTMX interactions, original static styles and icons, grouped shell and shared dialogs | Component and screenshot parity unconfirmed. See [UI-PARITY.md](UI-PARITY.md). |
| Historical data | Django ORM schema and separate adoption command | Real backup comparison, isolated rehearsal and rollback |
| Performance and fault recovery | Durable jobs and observability implemented | Benchmark, load/capacity and crash acceptance deferred |

Historical checkpoints report earlier isolated results. They are not acceptance
evidence for this revision or a production cutover.
