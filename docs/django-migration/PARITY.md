# Functional parity matrix

All target features are **NOT PORTED** until implemented and verified. Existing
baseline tests do not prove Django parity. Add test paths, reports and commit IDs
per row as stages land; never replace NOT PORTED with an unsupported percentage.

| Capability | Existing source / contract | Required acceptance | Target status |
|---|---|---|---|
| Login/logout, sessions, disabled accounts | api.py, accounts_api.py | Legacy hash login, CSRF, expiry, revoke, secure cookies | NOT PORTED |
| Roles and originals access | user/analyst/admin dependencies, preview/admin APIs | Role × action × originals permission matrix; no content leakage | NOT PORTED |
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
| Policy lifecycle and versions | workspace_api.py, catalog_api.py, processing.evaluate | CRUD, archive/delete/restore, shadow, history, reeval saved evidence | NOT PORTED |
| Rulepack import/export | rulepacks.py, rulepacks_api.py, rulepacks_cli.py | Versioning, validation, inactive policies, atomic import | NOT PORTED |
| Unified incidents and investigations | workspace_api.py, processing.py, Incident*.tsx | One incident/message, assignments/comments/status/history preserved | NOT PORTED |
| Message detail/attachment viewer | api.py, preview_api.py, document_preview.py, MessageAttachments.tsx | Safe preview, originals permission, all tabs, viewer isolation | NOT PORTED |
| Search/filters/ranges/preferences | workspace_api.py, admin_api.py, main.tsx | URL state, pagination, sorting, rolling range, theme, saved settings | NOT PORTED |
| Security overview/analytics | SecurityOverview.tsx, workspace_api.py | Existing semantics, live refresh, charts, counts, empty/error states | NOT PORTED |
| Accounts/addresses/employees | accounts_api.py, catalog_api.py, Accounts.tsx | CRUD, last-admin protection, disable, identity mapping | NOT PORTED |
| Reliable queues and controls | worker.py, jobs APIs, Queues.tsx, monitoring.py | 10 queues, ID-only tasks, outbox, retry/cancel, fencing/DLQ/recovery | NOT PORTED |
| Notifications/SIEM | integrations.py, admin_api.py, models.Outbox | Preserve delivery contract, backoff, dedup semantics | NOT PORTED |
| Retention/legal hold | retention.py, retention_api.py | Dry-run, hold protection, references/blob safety, Beat scheduling | NOT PORTED |
| Monitoring/audit/resources | monitoring.py, maintenance.py, SystemStatus.tsx, Operations.tsx | Broker/workers/queues/age/duration/errors, CPU/RAM/GPU, degraded states | NOT PORTED |
| Airgap/update/release | update/, Dockerfile, docs | Offline assets/models, compatible backup/upgrade/rollback | NOT PORTED |
| UI visual parity | All TSX/CSS in inventory.json | Same DOM/CSS/layout, themes, responsive views, dialogs, screenshots | NOT PORTED |
| Data preservation | models.py, migrations/versions/, raw semantic DDL | Backup restore, table/hash/FK/index comparison, rollback rehearsal | NOT PORTED |
| Performance and fault recovery | benchmark-350-v1, evaluation scripts | Independent realistic load, scale matrix, kill/restart checks | NOT PORTED |

## Evidence ledger

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