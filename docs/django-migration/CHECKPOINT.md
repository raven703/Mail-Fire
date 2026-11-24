# Native Django checkpoint — 2026-11-24

## Continuation after 7a9e88a

Implemented in this continuation (not full product acceptance):
- ZIP durable blob/job acceptance, isolated sandbox expansion using original
  app.uploads limits, fenced atomic member acceptance, stable delivery identities.
- SMTP collector management command: explicit CIDR allowlist, bounded DATA,
  storage commit before 250, 451 on storage error, independent receipt events.
- Read-only directory management command: stable files, no-follow descriptor
  traversal, regular-file/size/change checks, stable namespace/path/content keys,
  one-shot/watch modes, no source move/delete. Destructive source policies omitted.
- Native detection configuration snapshot; original detect/pii, normalization
  diagnostics, fingerprints/templates and category ANY/ALL algorithms in sandbox.
  Shared rule evaluator no longer imports SQLAlchemy except in legacy ORM helpers.
  Static YARA/oletools/gitleaks and configurable AV connected, errors yield PARTIAL.
  ML/LLM always skipped; ML-dependent rules explicitly report disabled engine.
- Native analyst list/detail/message/original download, investigation status,
  assignment/comments/audit; independent originals permission; escaped evidence.
- Category/rule native forms, source-equivalent bounded config validation.
- Dataset CSV/JSONL sandbox parsing with original algorithm, atomic import,
  unapproved external labels and manual review; admin + originals required.
- Native normalizer/AV/SIEM settings and audit/outbox pages, shared navigation.
- Policy worker ignores older queued snapshots when a newer evaluation completed.
- Compose profiles smtp and directory-import, pinned SMTP dependencies; runtime
  copies reusable app algorithms. Parser build still uses legacy full dependency
  lock and MUST be slimmed before claiming forbidden-dependency removal.

Verification: 33 focused SimpleTestCase checks pass (0.199s); focused Ruff passes;
11 source pytest checks pass / 2 skipped (1.29s); Compose config exits 0.
DB-backed suite was attempted without experimental DB credentials and failed
authentication before setup. No DB acceptance claimed; do not reuse production
credentials or existing containers. View/worker persistence checks use mocks.
No containers were started/restarted/exec'd; comprehensive acceptance deferred.

Next: actual isolated PostgreSQL intermediate checks for new ORM actions;
finish evidence sufficiency/staleness and concurrent policy tests; attachment
viewer, imports progress/retry UI, references/templates administration, rulepacks,
ML training/publish/rollback and LLM management (inference inactive), semantic
indexing, retention/legal hold, employee/address catalogs, analytics. Replace
intermediate form/table layouts with full original DOM/CSS/HTMX scenario parity.
Standalone dependency/build split, airgap and upgrade remain open.
Directory watcher reports failures but has no durable failed-file ledger yet.
Dataset parsing currently waits for the bounded isolated Parser request in HTML
view; move long imports to durable jobs if required. No inference is enabled.

## Previous checkpoint

Branch: experiment/django-htmx. Worktree: /home/user/Mail-Fire-django-htmx.
Entry commit: 4995900. Master worktree and existing containers/source DB untouched.

## Delivered

- Revised PLAN/TODO/PARITY: native Django architecture, optional historical import,
  no mandatory React-only APIs, retain useful foundation, ML/LLM inactive.
- Native /messages/upload/ for single EML/MSG; analyst/admin capability, CSRF,
  bounded read, UUID delivery identity, transactional shared accept + audit.
- Operations navigation entry; no parser invocation in web process.

## Verified

- Nine pipeline.test_uploads tests pass, 0.033s, database setup skipped.
- Django system checks pass; Ruff focused checks pass; git diff --check passes.
- Tests cover validation, stable user-scoped identity, anonymous/observer denial,
  native rendering, shared accept/audit invocation, conflict response and CSRF.
- Success/conflict acceptance calls are mocked: real PostgreSQL delivery dedup,
  broker dispatch and analysis are NOT newly verified by this increment.

## Continue here

Complete ZIP/directory/SMTP acceptance using shared ingestion; do not extract
archives in the web process without the existing untrusted-input isolation review.
Then complete missing detection engines (currently PARTIAL), native incident and
investigation workflows, templates/HTMX parity, datasets/training and inactive
ML/LLM, integrations/retention. Remove forbidden runtime/build dependencies after
separating reusable algorithms from legacy infrastructure. Existing legacy SQL
adoption is not a requirement for new schema design.

Full product is NOT completed. Historical evidence in PARITY is not current
acceptance. Comprehensive integration/visual/regression/load checks remain deferred
per user request. No existing container was exec'd, restarted or modified.