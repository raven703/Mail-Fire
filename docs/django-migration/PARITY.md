# Functional parity matrix

## Current interpretation — 2026-11-24

Parity means capabilities, algorithms, scenarios and UI, not old schema/internal
React JSON routes/service topology. Prefer native Django domain services/forms/
templates. Preserve external integration APIs. Historical data import is separate,
not a fresh-schema development gate. ML/LLM remain inactive while being ported.
PLAN.md's current contract supersedes historical conflicting instructions below.
Full integration/visual/regression/load acceptance follows implementation.

| Current increment | Implementation | Remaining acceptance |
|---|---|---|
| Native single EML/MSG upload | pipeline/forms.py, pipeline/uploads.py, templates/pipeline/upload.html; bounded input, investigator capability, CSRF, stable delivery token, shared transactional accept + audit | ZIP/SMTP/directory, database acceptance and visual parity pending |
| Schema independence | Existing ORM retained, native redesign allowed | Historical importer separate if needed |
| Web contract | Native HTML workflows preferred | React-only JSON routes not mandatory |

Target features remain **NOT PORTED** until implemented and verified. Existing
baseline tests do not prove Django parity. Add test paths, reports and commit IDs
per row as stages land; never replace NOT PORTED with an unsupported percentage.

| Capability | Existing source / contract | Required acceptance | Target status |
|---|---|---|---|
| Login/logout, sessions, disabled accounts | api.py, accounts_api.py | Legacy hash login, CSRF, expiry, revoke, secure cookies | Auth endpoints + import implemented; 2 focused tests pass; UI/account CRUD cutover pending |
| Roles and originals access | user/analyst/admin dependencies, preview/admin APIs | Role × action × originals permission matrix; no content leakage | Django capability backend implemented and tested; remaining API enforcement pending |
| EML/MSG, ZIP and directory import | uploads.py, mail.py, importer.py, smtp.py | Source events, duplicate handling, retries, malformed uploads | NOT PORTED |
| SMTP reception | smtp.py | Allowlist, source identity, durable acceptance, failure paths | NOT PORTED |
| Parser/Converter isolation | parser_service.py, sandbox.py, converter/, check_isolation.py | No credentials/DB access, timeout, malformed document tests | NOT PORTED |
| Extraction and nested archives | extraction.py, processing.py | Exact texts/statuses/attachments, archive limits | NOT PORTED |
| OCR backends and normalization | ocr.py, text_normalizer.py | Unchanged algorithms/settings/output; engine failures visible | NOT PORTED |
| PII, passport, SNILS, advanced engines | detectors.py, advanced_detectors.py, passport.py, snils.py | Existing regression fixtures and 350-case evidence comparison | NOT PORTED |
| Antivirus/secrets | antivirus.py, secret_scan.py | Enabled/disabled/unavailable distinction, no false clean status | NOT PORTED |
| Categories, ANY/ALL rules | categories.py, categories_api.py | CRUD, validation, active references, rule precedence | NOT PORTED |
| Document templates, fingerprints | document_templates.py, fingerprints.py, reference_api.py | Native/OCR anchors, thresholds, samples, no synthetic evidence | NOT PORTED |
| Semantic search, pgvector | semantic.py, semantic_api.py | Indexes, background reindex/progress, query parity | NOT PORTED |
| ML inference and optional disable | ml.py, ml_runtime.py, ml_engines.py | Predictions unchanged, lazy bounded loading, failures visible | NOT PORTED |
| Datasets, train, publish/rollback | datasets.py, ml_datasets_api.py, ml_api.py, background.py | Snapshot hashes, eligibility gates, holdout isolation, progress | NOT PORTED |
| LLM settings and optional disable | llm_analyzer.py, llm_api.py | API timeouts, redaction/payload behavior, outputs unchanged | NOT PORTED |
| Policy lifecycle and versions | workspace_api.py, catalog_api.py, processing.evaluate | CRUD, archive/delete/restore, shadow, history, reeval saved evidence | Policy-only worker, snapshot revisions and permission-checked request endpoint implemented; lifecycle CRUD/UI and message-based acceptance pending |
| Rulepack import/export | rulepacks.py, rulepacks_api.py, rulepacks_cli.py | Versioning, validation, inactive policies, atomic import | NOT PORTED |
| Unified incidents and investigations | workspace_api.py, processing.py, Incident*.tsx | One incident/message, assignments/comments/status/history preserved | NOT PORTED |
| Message detail/attachment viewer | api.py, preview_api.py, document_preview.py, MessageAttachments.tsx | Safe preview, originals permission, all tabs, viewer isolation | NOT PORTED |
| Search/filters/ranges/preferences | workspace_api.py, admin_api.py, main.tsx | URL state, pagination, sorting, rolling range, theme, saved settings | NOT PORTED |
| Security overview/analytics | SecurityOverview.tsx, workspace_api.py | Existing semantics, live refresh, charts, counts, empty/error states | NOT PORTED |
| Accounts/addresses/employees | accounts_api.py, catalog_api.py, Accounts.tsx | CRUD, last-admin protection, disable, identity mapping | Account CRUD, historical ID sync and session revocation ported; first templates added; modal/visual parity and addresses/employees pending |
| Reliable queues and controls | worker.py, jobs APIs, Queues.tsx, monitoring.py | 10 queues, ID-only tasks, outbox, retry/cancel, fencing/DLQ/recovery | Delivery/state/outbox implemented; real maintenance job smoke passes; analysis producer/handler and UI cutover pending |
| Notifications/SIEM | integrations.py, admin_api.py, models.Outbox | Preserve delivery contract, backoff, dedup semantics | Dedicated notification handler + atomic intents implemented; old outbox UI/config CRUD and E2E pending |
| Retention/legal hold | retention.py, retention_api.py | Dry-run, hold protection, references/blob safety, Beat scheduling | NOT PORTED |
| Monitoring/audit/resources | monitoring.py, maintenance.py, SystemStatus.tsx, Operations.tsx | Broker/workers/queues/age/duration/errors, CPU/RAM/GPU, degraded states | Django operations page/API, DB metrics, Rabbit management and Celery ping implemented; per-container/GPU telemetry, full UI/refresh parity pending |
| Airgap/update/release | update/, Dockerfile, docs | Offline assets/models, compatible backup/upgrade/rollback | NOT PORTED |
| UI visual parity | All TSX/CSS in inventory.json | Same DOM/CSS/layout, themes, responsive views, dialogs, screenshots | NOT PORTED |
| Data preservation | models.py, migrations/versions/, raw semantic DDL | Backup restore, table/hash/FK/index comparison, rollback rehearsal | 26 ORM models, frozen DDL, migration/adoption commands implemented; fresh DB verified; real backup validation pending |
| Performance and fault recovery | benchmark-350-v1, evaluation scripts | Independent realistic load, scale matrix, kill/restart checks | NOT PORTED |

## Evidence ledger

- Continuation after 7a9e88a: ZIP/SMTP/directory adapters, deterministic engine
  orchestration, native investigations/categories/dataset review/config/audit
  delivered. 33 focused no-DB checks pass (0.199s), 11 source checks pass / 2
  skipped; Ruff/Compose config pass. DB suite blocked by absent dedicated
  credentials. Persistence mocked; no live full-cycle, visual or capacity claim.
  Detailed scope and remaining work: CHECKPOINT.md.

- Native architecture/upload checkpoint, 2026-11-24: nine isolated upload checks
  pass (0.033s), no database setup; system checks, focused Ruff and whitespace
  checks pass. Acceptance service/audit mocked in view tests; real DB/broker and
  visual acceptance not claimed. See CHECKPOINT.md for continuation.

- Detection wiring checkpoint: unchanged deterministic detect/pii algorithms
  invoked through sandbox, OCR completion dispatches detection, fenced detection
  saves PARTIAL evidence and requests existing policy/incident evaluation atomically.
  Unported engines explicitly listed, ML/LLM skipped. Twelve pipeline/policy checks
  pass (2.433 s); NOT a real EML acceptance. Independent Parser Dockerfile removes
  local backend image dependency; clean build still pending model/tool downloads.
- Real isolated Parser/OCR deployment: distinct experiment image and internal
  networks, no DB/broker secrets or host mounts supplied. Sandbox probe returned
  network_denied=true, uid=10001, database_secret=null, all sensitive paths false.
  Real generated PNG OCR returned ANALYZED, RapidOCR blocks CONFIDENTIAL and
  1234567890 with confidences 0.99881/0.99915. This is NOT a full EML/Celery cycle.
  Converter image build/health remains unverified (registry build pending).
  Transitional parser dependency image still references legacy backend base;
  standalone dependency build remains required. Detection remains unconnected.
- OCR separation checkpoint: new extract_native operation suppresses OCR through
  recursive extraction; OCR coordinator uses a distinct required remote endpoint
  and queue, commits results with fencing, preserves attachment order and partial
  states. Eight existing pipeline checks pass; no live OCR execution yet. Parser
  endpoints/images/networks and detection handoff still unconnected. Full-cycle
  acceptance NOT achieved. TODO.md records remaining autonomous work.
- Extraction hand-off checkpoint: ingestion completion and extraction dispatch
  commit atomically; extraction consumes persisted parse output, calls only the
  remote isolated Parser, validates result shape and commits attachment evidence
  with fenced completion. No existing attachment evidence is overwritten. Eight
  pipeline checks pass (0.527 s), including mocked extraction contract and stale
  redelivery refusal; no email parsing/OCR regression was run. Detection remains
  unconnected, message remains PENDING with explicit error. IMPORTANT: existing
  Parser extract contract performs inline OCR (also recursively in archives);
  independent OCR queue requires splitting that contract before scale/parity
  acceptance. No live Parser/Converter deployment or full cycle verified.
- Ingestion foundation: transactional ORM acceptance with source/blob advisory
  locks, distinct delivery events, dispatch outbox and registered ingestion.parse
  handler. Remote-only bounded parser client refuses local fallback. Parse output
  persists in job output; extraction/OCR/detection hand-off NOT CONNECTED and
  message remains PENDING with an explicit error. No upload/SMTP endpoint or
  experiment Parser/Converter deployment added in this checkpoint. This is NOT
  a working end-to-end pipeline. Seven pipeline/boundary tests pass (0.505 s),
  without processing emails. Runtime dependencies on legacy analysis remain
  unported; no full-cycle or isolation deployment acceptance claimed.
- Policy HTML catalog: list, modal editor, history, archive visibility, restore
  and deletion connected to one catalog_service shared with JSON API. Twelve
  focused auth/pipeline/policy checks pass (2.226 s). No message processing.
  Remaining UI gaps: nested category picker/create, dynamic condition summary,
  shared navigation/theme, HTMX enhancement and screenshot-based acceptance.
- Account editor inline simplification removed: native modal with original
  editor-dialog CSS, pinned footer, Escape/Cancel/X, first-input focus, scroll
  locking and revoke confirmation. Four identity tests pass (2.536 s), including
  modal rendering/error preservation/password non-disclosure. Browser screenshot
  and interaction parity remain unverified; this is not full visual acceptance.
- Policy catalog CRUD/version/archive/restore/delete APIs ported, 3 focused
  policy checks pass; policy UI still pending. WEB.md records live isolated
  nginx/ASGI health/login/static smoke (200); no mail processing.
- Operations checkpoint: four pipeline checks pass (1.075 s), template rendering,
  observer denial and no payload disclosure checked. Web Compose config and
  Django checks pass; Docker build validation tracked in WEB.md/MONITORING.md.
- Accounts checkpoint: 3 Auth/account tests pass (1.342 s), templates compile,
  migration applied/no drift, Ruff passes. No message tests; see ACCOUNTS.md.
- Policy checkpoint: isolated schema migration + no drift, 2 pure rule/source-AST
  checks and 3 delivery tests pass (5 total, 0.206 s). No message tests; see POLICY.md.
- Queue checkpoint: 3 focused PostgreSQL tests pass; real RabbitMQ topology and
  Celery prefork resource-sampling job verified. See QUEUES.md for scope/limits.
- Data/Auth checkpoint: fresh isolated PostgreSQL migration successful; 2 Auth
  tests pass (0.659 s); migration drift check, Ruff and diff whitespace checks
  pass. Schema-adoption validator passes against the fresh schema with a temporary
  Alembic 0007 marker inside a rolled-back transaction (not a real backup test).
- User revised scope: no message tests and minimal checks for subsequent stages;
  no benchmark, OCR/ML/LLM, load or full regression run in Data/Auth checkpoint.
- Source baseline: 142 passed / 22 skipped / 1 warning (64.77 s), 2026-11-24.
- Audit checkpoint including two new inventory tests: 144 passed / 22 skipped /
  1 warning (48.03 s). Ruff and `git diff --check` passed. Inventory identifies
  92 decorated local endpoints, 25 ORM tables, 23 TSX files and 8 stylesheets.
- Existing holdout report: `test-data/results-benchmark350-20261123/REPORT.md`.
  This is historical source evidence, **not** a Django run or new comparison.
- New broker/database, visual, load and chaos validation: **NOT RUN**.
- Architecture comparison: source FastAPI/SQLAlchemy/React/custom PG leases versus
  proposed Django ORM/templates/Celery/RabbitMQ. Performance, resource consumption,
  build time and image size differences are **NOT MEASURED**.

## Continuation after 91c3b44

Implemented: fixed configured Converter health alongside Parser/OCR; persisted
job-stage counts, attempts, wall-time average/p95, oldest pending age and expired
leases; corrected Celery concurrency key. Added message attachment/incident/MIME
filters, date/sender sort and delivery source/direction/time columns. Incident
list adds source/direction, permission-gated sender/recipient, sorting and default
open statuses. Global search and topbar diagnostic/investigation links restored
from master main.tsx. Master Queues/SystemStatus/main read directly.

Implementation still missing: full per-service resource collection/history and
original resource graphs; original component DOM/visual parity throughout;
evidence highlights/viewer details; remaining picker/catalog/training interaction
comparison and analytics panels/service summaries. These are code gaps, not merely
browser acceptance. Existing historical NOT PORTED rows are not proof of current
absence and have not been bulk-closed without inspection.

Implemented but awaiting verification: PostgreSQL percentile query and list
filter execution, browser layout/interactions, runtime service health and delivery
metadata rendering. No DB/container changes, builds, migration application,
comprehensive testing or ML/LLM activation performed.

Audit remediation remains deferred; no audit items were claimed fixed here.


## Continuation after 4e3b2e3

4e3b2e3 published. Direct master comparisons: Evidence.tsx, MessageAttachments.tsx,
SystemStatus.tsx and analytics branch of main.tsx. Shared escaped evidence cards
now include reason/excerpt/rule/version/risk/confidence on message, incident and
attachment pages. Viewer adds original/text/DLP tabs, passive text fallback,
async page loading, page count/previous/next, scale/highlight and error status.
Existing rasterization/authorization contracts are unchanged. Browser acceptance
and safe original mail metadata/modal parity remain outstanding.

Resource history now separates persisted service series, bounds last 20 samples
and renders original SystemStatus CPU/RAM/disk/swap KPI and history-table structure.
Master SystemStatus has a history table, not per-container graphs. Complete
service collectors remain unimplemented; no local metric is called global.
Analytics adds original KPI links, severity/category panels, processing-health
links and CSV timeline export. Runtime SQL/probe acceptance remains deferred.

Remaining implementation: complete service collectors, remaining viewer original
metadata/modal behavior, picker/catalog/training comparison and scenarios, exact
component/style parity. No claim that all functional parity work is finished.
Focused checks: 15 no-DB tests, Ruff, JavaScript syntax, whitespace. No builds,
migrations, container/source DB edits, comprehensive tests or ML/LLM activation.
Audit remediation remains deferred.
