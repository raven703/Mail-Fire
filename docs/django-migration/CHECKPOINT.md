# Native Django checkpoint — 2026-11-24

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