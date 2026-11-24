# Native Django checkpoint — 2026-11-24

Post-8ae82ae continuation adds saved-incident timeline grouped by day and risk
bands with original Timeline chart/bar structure. DB execution is deferred.

## Continuation from 6342275

Replaced manual rule JSON with shared structured keyword/word/morphology/flexible
term, Regex, reference and ML controls in standalone and nested editors. Weighted
terms have bounded add/remove, weight/required controls; exclusions and thresholds
preserve original validator contract. Master CategoryPicker and DateTimeRangeFilter
read directly; added 24h/7d/30d/custom date controls and timezone display. Eight
focused tests pass including all engine configs and unsafe Regex rejection.
No migration, image build, browser/comprehensive tests or inference activation.
Remaining UI/telemetry entries are not closed by this increment.


## Continuation from e572a2f

Direct master CategoryPicker/PolicyEditor/IncidentTraining comparison used.
Existing categories and rules now editable inside policy form, preserving policy
draft; save/cancel and rule deletion/addition supported with original validators.
Incident training opt-in modal persists extracted text, labels, approval and audit,
refuses duplicates and respects originals permission; no training/inference
activation. Added grouped navigation and collapse. Fourteen focused no-DB tests,
Ruff and JS syntax checks pass. No migration/build/live-container/DB operations.
Structured rule widgets, exact visual parity and full service telemetry remain
open; no blanket completion claim.


## Continuation from f97ca7a

Added bounded, idempotent analyst bulk full reanalysis, page selection/reset,
per-item enqueue errors/retry and monitoring handoff. Active message jobs block
reanalysis; attachment replacement is fenced with parse completion. Added inline
category creation inside policy editor preserving unsaved policy fields, dynamic
condition summary and removed duplicate policy navigation shell. Added overview
risk distribution/priority incidents and filtered Celery worker stats (uptime,
processes/concurrency/rusage). Eleven focused no-DB checks pass; Ruff passes.
No migration/application/build/live DB or container operations. Outstanding UI
and service telemetry scenarios remain in UI-PARITY; not full parity acceptance.


## UI-first continuation from cc190a8

Continued after c80faac: category multi-select and all severity bands now filter
incident lists; message source/direction filters and page-batched attachment and
incident counts added. Recipient display remains originals-capability gated.
Twelve focused checks rerun successfully. Full UI parity remains open.

See UI-PARITY.md for explicit master-component mapping and remaining scenarios.
Added original five missing CSS assets, overview KPI/trend/policy panels,
progressive accessible message content/evidence/attachment/header tabs, shared
date filters and query-preserving pagination. Added bounded GPU/cgroup probes
and web resource display; maintenance samples also record these probes.
Independent content-addressed inference artifact copies and migration added;
model-row deletion no longer breaks newly dispatched snapshots. Migration NOT
applied to any DB. Twelve focused UI/workspace/resource/inference tests pass;
Ruff passes. No live containers, master or source DB changed. No full visual or
functional completion claim; outstanding scenarios remain in UI-PARITY.md.

## Continuation beyond cf4bbcb

Post-64ccee6 continuation adds the original seven-day delivery-flow aggregation
(hour/source/direction, events, distinct messages, mean/median/p95 bytes) and its
native monitoring table. Two provider-free LLM checks verify selected-category
filtering/confidence and explicit transfer authorization; nine focused inference,
offline and LLM checks pass. PostgreSQL aggregation execution remains unverified.

Inference now captures category names/modes, active model metadata and artifact
hashes, LLM/normalizer settings at dispatch; detection retains full deterministic
configuration. Workers use pinned model IDs/metadata and refuse missing/changed
artifacts. Artifact bytes remain in model rows, not copied: deleting a queued
model yields an explicit snapshot_artifact_unavailable result (not silent fallback).
Custom ANY/ALL is reevaluated using the original evaluate_groups via Parser with
saved config and ML scores; previous custom findings are replaced, not appended.
TF-IDF routes to ml/training image; neural snapshots route to neural/neural image.
Compose profiles and gates added; all deployment gates default false.
LLM UI supports explicit opt-in, still independently blocked by deployment gate;
provider algorithm unchanged. Offline restore checks hashes and safely stages
regular local-model files to a new directory without starting containers.
Monitoring adds Parser/OCR health, unique message status totals and admin-only
read-only PostgreSQL size/table/index/vacuum/lock/connection statistics.

17 focused no-DB tests passed; Ruff and template compilation passed. Compose
profile validation emitted no error after fixing training build-context profile.
No image builds, provider calls, source DB changes or live container changes.

Still NOT full completion: visual/interactive parity, full resource/GPU telemetry,
flow/p95 monitoring, live PostgreSQL inference/fencing acceptance, neural image
builds and offline image installation acceptance remain open. Model artifact
copies and retention during queued jobs need acceptance/design completion.
Historical TODO/PARITY entries must not be treated as checked by this increment.

## Inference continuation after b4a7393

Added deployment-gated optional detection→ML→LLM→Policy routing (both gates default
false), ID-only durable inputs, immutable inference content revisions, stale-content
refusal, fenced result/next-dispatch commit. Reused original ML prediction and LLM
request/response algorithms through persistence-free adapter entry points; legacy
adapters preserved. Built-in ML findings retain original probabilistic provenance.
Four focused routing/detection checks pass; Ruff/system/whitespace checks pass.

NOT complete inference acceptance: custom category ML ANY/ALL reevaluation still
needs original group evaluator integration; runtime Compose ML image/gate wiring
and captured config/model snapshots remain open. No inference activated. Current
Compose ML worker is still light and unsuitable for enabled inference. Do not set
gates before finishing runtime integration. Full UI/monitoring/offline remaining
work is unchanged. This checkpoint does not close TODO or parity matrix.

## Training-routing continuation after d51477c

TF-IDF jobs remain training.model/training; neural jobs now use
training.neural/neural_training and separate worker group/time limits. Handler
rejects incompatible engine/kind before DB/heavy imports. Models page lists both.
Optional offline export --neural-models includes neural image and local snapshot
archive with checksums; requires materialized non-symlink rubert/setfit directories.
Import tool verifies archive but does not extract models automatically.
Four focused routing/offline tests pass; Ruff/Compose config/whitespace pass.
No images built, inference enabled, source algorithm changed or services touched.
Remaining full inference/UI/monitoring/offline acceptance is still OPEN.

## Monitoring/offline continuation after 8dc7640

Read master SystemStatus/Operations sources without modifications. Added 30-second
HTMX refresh for broker/queue/worker panel, expired lease/delayed retry counters,
per-queue failed-attempt counts in snapshot and metadata-only diagnostic listing.
Added offline image export/checksum verification/load tool (never starts services).
Added optional neural Dockerfile/profile and exact neural dependency closure from
existing uv.lock. Local read-only model directories and offline environment flags.
Neural image is not built/validated and shares training queue with TF-IDF worker;
use only compatible neural worker for neural jobs. Offline bundle does not yet
include neural image/models. See BUILD-NATIVE.md for honest scope and limitations.

Full UI/visual parity, complete service/resource monitoring, ML/LLM inference
orchestration and final standalone/offline acceptance remain OPEN. No comprehensive
testing/audit or existing-container changes. Detection algorithms untouched.

## HTMX shell continuation after b51a2e6

Vendored HTMX 2.0.11 with license and SHA-384 integrity, no runtime CDN. Native
shell now uses existing MICE layout/sidebar/topbar classes and responsive tables.
Boosted same-origin navigation/forms target the content region; multipart encoding,
validation 400/422 rendering, CSRF header, loading/error announcements, download/
export bypass and modal reinitialization added. Sensitive DOM history caching and
script/eval execution disabled. Login redirects reload shell to discard stale nav.

This is progressive shell integration, NOT complete visual/scenario parity.
Monitoring polling, all modal/filter interactions, neural/offline delivery and
optional ML/LLM inference orchestration still remain open. No comprehensive or
browser acceptance performed. Do not mark TODO/matrix complete from this increment.

## Semantic/build/GC continuation after 3716d84

Native pgvector indexing/search added with original 180-word/40-overlap chunks,
same MiniLM model, dedicated semantic queue, per-document fenced atomic replacement,
progress and user-scoped search job results. Embeddings loaded only in optional
semantic image. Native conservative blob/content GC checks message/attachment/
reference FKs plus nested durable payload/output references, refuses competing
active jobs and locks writers during bounded collection. Preview and explicit
confirmed GC actions added to retention UI. Legal-held FK references preserved.

Standalone Parser exact dependency closure replaces full legacy lock. OCR and
training/semantic use separate Dockerfiles and explicit Compose build contexts;
training profile no longer enabled by pipeline. TF-IDF dependencies isolated from
main runtime. Neural training image/weights still open. Added rolling-range daily
message counts, risk summary and policy/analyst breakdown to overview.

23 focused no-DB tests pass; Ruff/system checks pass. Compose configuration with
training/semantic profiles validates. No images built or containers changed; lock
installation compatibility, PostgreSQL GC/index persistence and concurrency not
verified. Full HTMX/visual parity, complete analytics/monitoring, neural/offline
build support and remaining TODO are NOT complete. See BUILD-NATIVE.md.

## Model-management continuation after 29ff4d2

Added native /models/ training requests and dedicated fenced training.model worker
handler, reusing unchanged app.ml/train_binary algorithms. Reviewed corpus hash is
checked before training; model artifact digest, dataset snapshot, job provenance,
quality eligibility and inactive version are stored atomically. Publication/rollback
serialize via PostgreSQL advisory lock; inactive deletion and deactivation audited.
Added admin /llm/ configuration with HTTPS validation, environment-only API key and
forced enabled=False. No provider calls or detection inference enabled.

IMPORTANT: dedicated heavy training dependency image is not implemented yet;
current minimal runtime lacks sklearn/transformer libraries. Training UI/handler
is implemented but must not be advertised as deployment-ready. Semantic indexing,
GC, comprehensive analytics/HTMX/visual parity and dependency/build split remain
open. This checkpoint is not full TODO/parity completion. No containers or source
database touched. Focused Django checks and no-DB tests only.

## Rulepack continuation after e2bc395

e2bc395 committed and pushed to origin/experiment/django-htmx. Native rulepack
JSON import/export and audit history added at /rulepacks/: bounded 1 MiB schema,
original flattened rule contract, shared native rule validators, built-in category
protection, pack ownership checks, signed user-bound 15-minute preview and explicit
atomic apply. Imported policies remain disabled. Policy revisions preserved.
Four focused no-DB rulepack tests pass; Ruff passes. Live PostgreSQL locking,
roundtrip/persistence acceptance and browser workflows not yet verified.
Semantic pgvector, safe GC, complete analytics/UI and dependency split remain open.

## Continuation after 4ec39fa

Implemented native passive attachment pages/downloads, sandbox PNG rasterization,
bounded Office conversion, linked findings, and originals-gated message attachments.
Added reference upload/catalog with original fingerprints and document-type sample
validation; type templates retain only built-in anchors, not sample personal fields.
Added admin employee/address catalogs, messages/import history and aggregate overview.
Authenticated responses now carry private/no-store headers; local theme preference
stores no message content. Compose web can reach isolated parsing/conversion services.

Retention: admin configuration, explicit DELETE_EXPIRED confirmation, legal-hold
reason/audit and fenced maintenance jobs, per-incident retention, active-job/outbox
guards, per-message transactions and deletion checkpoints. Defaults paused. Daily
schedule performs **dry-run only**; destructive runs require explicit UI confirmation.
Blob/content GC, audit/log/metric expiry, durable intake identity tombstones and
full concurrency validation remain open. Do not enable destructive cleanup in a
real deployment before isolated PostgreSQL integration review. Existing source
directories are never modified. Retained content means this is NOT secure erasure.

Verification: 45 focused no-DB tests pass; Ruff and 21-template compilation pass.
PostgreSQL/RabbitMQ persistence, converter/Parser live requests and visual acceptance
remain unverified. No services started. ML/LLM inference remains inactive. Rulepacks,
training/model lifecycle, semantic indexing and standalone Parser lock split remain
open. Reference parsing is bounded but synchronous, like current dataset import.

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
