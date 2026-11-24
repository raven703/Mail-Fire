# MICE: native Django/HTMX — execution ledger

## Current architecture contract — 2026-11-24

This section supersedes conflicting historical requirements below. Master is
the functional/algorithmic/visual reference, NOT the architecture template.
Build a standalone Django LTS + ORM + Migrations + Templates/HTMX/Vanilla JS
application with PostgreSQL/pgvector, Celery/RabbitMQ/Beat and Docker Compose.
No React, FastAPI, SQLAlchemy, Alembic, Node/npm/Vite, Redis or Supervisor in
the target build/runtime. Do not reproduce React-only internal JSON endpoints;
preserve necessary external integration APIs and share domain services.

Retain useful identity/ORM, Outbox, retries/fencing/recovery, isolated Parser/OCR,
stage workers and policy snapshots. Native schema redesign is allowed; legacy
schema adoption is NOT a gate. Historical import is a separate optional tool.
Avoid compatibility layers and duplicate business logic. Policy is a domain
module with dedicated workers and saved-evidence reevaluation, not a microservice.
Keep ten independently scalable queues: ingestion, extraction, ocr, detection,
ml, llm, policy, notifications, training, maintenance. Preserve transactional
dispatch, durable delivery and incident uniqueness. ML/LLM must be ported but
remain inactive. 20,000 messages/day plus bursts is a target, not a measured claim.

Priority: simplicity, security/reliability, functional parity, performance,
visual parity, operational simplicity. Preserve CSS/navigation/dialogs/scenarios,
proven detectors, EML/MSG/documents/OCR, policy semantics, datasets/training,
investigations/audit/integrations, ground truth and attachment isolation.

Audit: current worktree is clean at entry; ingestion→extraction→OCR→detection→policy
is wired but detection explicitly remains PARTIAL. Keep this foundation, complete
missing engines and native user workflows rather than starting again.
Next: native upload/SMTP/import; full deterministic engines; incidents and UI;
datasets/training and inactive ML/LLM; retention/integrations; standalone builds.
Run intermediate isolated checks now. Comprehensive integration, visual,
regression and load acceptance follows implementation. Never modify master,
existing containers or source DB. Publish/checkpoint experimental branch only.

## Historical ledger (not current architectural constraints)

## Status, 2026-11-24

**Data/Auth checkpoint implemented; full migration and functional parity are
not complete.** See DATA_AUTH.md for commands, checks and cutover limitations.

Source: `origin/master` = `0e303b13c2b4e026a15828d73a3d754faea202d4`, verified
with `git fetch origin master`. Dedicated branch: `experiment/django-htmx`.
Worktree: `/home/user/Mail-Fire-django-htmx`. Original worktree and running
`mailfire` containers must remain unchanged. Original untracked OCR reports
are not migration inputs and must not be removed or committed.

## Audit findings

- Backend: FastAPI, SQLAlchemy, Alembic; 7 migration files. `0001` depends on
  application metadata: freeze historical DDL before replaying into Django.
- UI: React/TypeScript/Vite; 23 TSX files, shared CSS and browser smoke scripts.
  Preserve CSS, DOM structure, dialogs, navigation parameters and interactions;
  transpiling TSX or embedding the old SPA is not a completed template migration.
- `app.processing.analyze` combines parsing, attachment scanning/extraction/OCR,
  deterministic detectors, fingerprints/templates, ML, LLM and semantic work.
  It invokes evaluation more than once as evidence is enriched. Split at durable
  evidence boundaries; do not put this entire function in a single Celery task.
- `app.worker` polls PostgreSQL jobs with leases/heartbeat and fenced writes.
  Training and semantic reindex also depend on those leases. Port all producers
  and handlers together before enabling the new pipeline; no dual dispatcher.
- `Outbox` currently means incident notification delivery, not broker publication.
  Introduce a separate job-dispatch outbox with atomic job/evidence writes.
- Policy versions and historical hits already exist. `evaluate` locks the message
  and upserts one incident per message; preserves assignee/comments/workflow.
  Preserve these invariants with database constraints, not Celery task IDs alone.
- Auth uses Argon2, custom session tokens, admin/analyst/observer roles and a
  separate `originals` capability. Map all four dimensions into Django permissions.
  Existing sessions should be revoked at cutover; retain account IDs/passwords
  with a verified legacy Argon2 adapter and explicit password-upgrade tests.
- Parser and Converter have separate internal networks, no DB credentials, read-only
  filesystems and resource constraints. Keep their boundaries and payload protocols.
- Maintenance currently loops over retention, resources and notification delivery;
  importer/SMTP are separate processes. Beat replaces periodic scheduling, not SMTP.
- Existing limitations document contains chronological, sometimes contradictory
  statements. Code and executable acceptance tests take precedence.

Machine-readable baseline: `inventory.json`, generated using
`scripts/migration_inventory.py` (AST, no application imports, local route paths).
This is an inventory, not an assertion that every business path has been audited.

## Baseline validation

Read-only local suite executed from the experimental worktree using the existing
Python 3.12.14 environment (no production DB URL supplied):

```
/home/user/Mail-Fire/.venv/bin/python -m pytest -q --disable-warnings
142 passed, 22 skipped, 1 warning in 64.77s
```

Skipped tests are **not validated**, especially database/integration paths.
Django and Celery are absent from that environment. Original containers were
listed only; no exec, writes, restarts, imports or benchmark calls against them.

## Commit-sized implementation stages and mandatory gates

Each stage gets its own commit only after tests, with failures/skips recorded.
Update PARITY.md with evidence and the resulting commit. Do not call a stage
complete because files or services merely exist.

1. **Audit checkpoint (committed):** inventory, baseline, parity matrix, risks.
2. **Data/auth migration:** select supported Django LTS from official release
   docs; confirm Celery/Kombu/RabbitMQ compatibility; lock dependencies. Freeze
   existing DDL, map every table/index/constraint including pgvector/trgm, create
   Django migrations and Auth/session/permissions mapping. Restore a sanitized
   backup into an isolated DB; compare counts, hashes, FKs, blobs and sequences;
   exercise forward migration and restore rollback. Never fake-initial blindly.
3. **Reliable execution cutover:** Django stage state, evidence revisions,
   dispatch outbox, RabbitMQ/Celery/Beat, all job producers and handlers. Atomic
   stage transitions and outbox inserts; publisher confirms before marking sent;
   duplicate publication explicitly expected. No old polling scheduler in the
   new runtime. Real broker+DB tests, including kill-after-publish/before-confirm.
4. **Analysis/policy parity:** move unchanged algorithms behind durable per-stage
   adapters; preserve extraction status and mandatory-stage failure semantics.
   Version evidence, settings and policy snapshots. Policy-only reevaluation uses
   sufficient saved evidence, without invoking OCR/detection. Test incomplete or
   stale evidence, concurrent reevaluation and incident uniqueness/workflow.
5. **Web parity:** port every inventoried endpoint, permission boundary and UI
   scenario into Django Templates+HTMX/vanilla JS; reuse exact styles. Self-host
   browser assets. Screenshot comparisons for both themes and supported viewport
   sizes plus real CRUD/validation/error/empty/loading/modal tests. Remove React,
   TS, Node/npm/Vite from the final runtime/build only after equivalent coverage.
6. **Operations parity:** monitoring in the existing UI, queue controls, broker
   health, workers, oldest pending age, DB-derived throughput/durations/errors,
   per-container CPU/RAM and available GPU telemetry. Never show synthetic healthy
   states. Mark unavailable measurements explicitly. Test broker/worker outages.
7. **Acceptance:** repeat full tests; run identical 350-message holdout against
   isolated old/new deployments; real attachment load at 20k/day and bursts to
   25k/hour with queue-drain latency, p95/p99, RSS/CPU/GPU measured. Vary replicas
   and concurrency; train concurrently. Kill workers/broker/DB containers and
   verify no lost jobs, duplicate incidents or false successful analyses.
8. **Publication:** compare measured build time, image sizes, resource use,
   throughput and maintenance complexity. Document remaining gaps, commit all
   evidence and push experimental branch only. No merge into master.

## Execution design requirements (not yet implemented)

Ten independently scalable queues: ingestion, extraction, ocr, detection, ml,
llm, policy, notifications, training, maintenance. Broker payloads contain job IDs
only. PostgreSQL owns job state, dependencies, attempt/fencing tokens, evidence
and policy revisions; RabbitMQ provides delivery, not authoritative completion.
Use durable task queues and DLQs, persistent messages, confirms, late acknowledgments,
bounded retries/backoff/jitter, per-stage soft/hard timeouts and stale-run recovery.
Validate behavior on the selected RabbitMQ queue type rather than assuming defaults.
Outbox scanner publishes only delivery intents, never executes domain work or
reintroduces PostgreSQL work scheduling. Retain failed mandatory stages visibly.

Every worker group needs separate concurrency/prefetch/CPU/RAM/timeouts and replicas.
Training has dedicated resources, minimal prefetch and no inference worker sharing.
Heavy models load lazily within explicitly bounded process counts. Benchmark
numbers cannot be inferred from worker counts: burst target is ~6.94 messages/s,
but attachment distribution and OCR duration determine capacity.

## Isolation contract for future Compose deployment

Use a separate `compose.django.yaml`, explicit project `mice-django-htmx`, unique
image tags and project-scoped named volumes/networks (no external volumes, fixed
container names or original bind-mounted data). Proposed loopback ports: web
18080, SMTP 12525, RabbitMQ management 15673; check availability before launch.
Database `mice_django_experiment`, dedicated role/password, not the live DB.
Keep DB/AMQP unexposed. Parser/Converter retain isolated internal networks;
no broker, DB credentials, Docker socket or original filesystem mounts.
Do not run the inherited `compose.yaml`: it names the live project `mailfire`.