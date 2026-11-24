# Autonomous migration backlog

## Superseding native Django backlog — 2026-11-24

The historical backlog below is evidence only when it conflicts with this section.
Master is a behavior/design/algorithm reference; old architecture/schema/API parity
is not required. Comprehensive acceptance is deferred until implementation completes.

- [x] Review existing experimental worktree; retain ORM/auth/Celery/Outbox/fencing,
  Parser/OCR/detection and standalone policy domain.
- [x] Update architectural contract and parity interpretation.
- [x] Native single EML/MSG HTML upload using shared durable acceptance, capability
  check, CSRF, bounded read, delivery token and transactional audit (intermediate).
- [ ] ZIP/directory import and SMTP durable acceptance.
- [ ] Finish normalization, AV/secrets, categories, references/templates, OCR/archive contracts.
- [ ] Native incidents/investigations/audit, safe previews/originals, analytics.
- [ ] Policies/categories/rulepacks, saved-evidence sufficiency and reevaluation.
- [ ] Datasets/training/publish/rollback, semantic pgvector; port ML/LLM but keep inactive.
- [ ] Integrations/notifications, retention/legal hold and maintenance.
- [ ] Templates/HTMX visual and workflow parity, original CSS/themes/dialogs.
- [ ] Remove forbidden target runtime/build dependencies; standalone sandbox builds.
- [ ] Simplify compatibility-driven schema/code where useful; separate historical importer.
- [ ] Intermediate isolated unit/security checks; then complete acceptance matrix,
  integration/visual/regression/load/chaos and ground truth after implementation.
- [ ] Checkpoint and publish experimental branch only, never merge master.

## Historical backlog

Continuation after 7a9e88a adds all intake adapters (ZIP sandbox jobs, SMTP,
read-only stable directory watcher), deterministic evidence orchestration,
native analyst/category/dataset/config/audit pages. See CHECKPOINT.md: these are
implemented increments with focused checks, not full parity acceptance. ML/LLM
remain inactive; training/publish/rollback, viewer, rulepacks, retention, semantic
indexing, full HTMX/visual parity and standalone dependency split remain open.

Work only in experiment/django-htmx. Master/live containers/data are forbidden.
Newest user instruction permits isolated email integration/regression/load tests.

- [ ] Split native extraction and OCR contracts, including nested archives.
  Native extraction now propagates use_ocr=False recursively; OCR coordinator
  registered on its own queue. Isolated OCR service deployment and real PDF/image/
  archive verification remain required. OCR currently re-extracts the original
  attachment in the OCR service, preserving the original combined algorithm.
- [ ] Deploy dedicated secret-free Parser/OCR/Converter in internal networks.
  Parser and OCR now running on distinct internal networks. Real sandbox probe
  confirmed network_denied=true, uid=10001, no DB secret/sensitive mounts. Real
  generated PNG recognized by RapidOCR. Converter build/start was attempted;
  registry metadata retrieval delayed it; inspect build/container before retrying.
  Dockerfile.django-parser currently uses mailfire-backend:local dependency base;
  replace with standalone pinned dependencies before final independence acceptance.
- [ ] Connect detection, normalization, AV/secrets, category/reference/template rules.
- [ ] Connect optional ML/LLM workers with explicit unavailable/disabled states.
- [ ] Persist final analysis and enqueue policy/incident evaluation atomically.
  Deterministic detection adapter now wired OCR→detection→policy using unchanged
  detect()/pii() through sandbox. Missing AV/secrets/normalization/custom/reference/
  template checks are explicit engine_errors and force PARTIAL. ML/LLM skipped.
  Real full-cycle acceptance still pending updated Parser image build.
- [ ] Add upload/SMTP/import adapters and delivery-context deduplication tests.
- [ ] Exercise real RabbitMQ/Celery full cycle; crash recovery/idempotency tests.
- [ ] Port remaining APIs/services enumerated in PARITY.md and inventory.json.
- [ ] Finish HTMX pages, nested dialogs, theme/navigation and screenshot parity.
- [ ] Adopt real backup in isolated DB and compare data; no production cutover.
- [ ] Run isolated regression/integration/load acceptance and record evidence.
- [ ] Remove legacy runtime/ORM/API/frontend dependencies only after parity.

Checkpoints are not completion. Never infer full-cycle success from unit tests.

## Current build continuation

Independent Dockerfile.django-parser now starts from the public uv Python base,
installs frozen dependencies/models/tools and copies source; no local legacy image
reference. Build log `/tmp/mice-parser-no-ml-build.log` (no embeddings preparation).
Earlier `/tmp/mice-standalone-parser-build.log` may still have an older build
downloading embeddings; do not mistake its output for current build acceptance.
Converter build `/tmp/mice-converter-build.log` is downloading LibreOffice packages.
Runtime rebuilt successfully, 12 pipeline/policy checks passed (2.433 s).
Neither new detection sandbox operation nor full Celery chain is live verified yet.

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
