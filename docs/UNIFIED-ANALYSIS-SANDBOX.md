# Unified analysis sandbox (opt-in rollout)

## Architecture
Durable acceptance (SMTP, upload, directory import) retains the original blob, message, event and import record in the existing transaction. New work is routed to analysis.analyze when MICE_UNIFIED_ANALYSIS_ENABLED=true. The ingestion worker remains for bundle intake and legacy jobs. The analysis worker sends one request to the parser; the dedicated single-threaded launcher preloads pymorphy3/Razdel and forks a fresh child per mail. The child parses EML/MSG, extracts attachments, delegates OCR when needed, prepares separate MIME document evidence, evaluates DLP and static/secrets checks, returns results and exits. ClamAV stays external in the trusted coordinator. Optional inference and policy/notifications are unchanged. Regex timeout isolation, Gitleaks and OCR may still start their own auxiliary processes; one main sandbox does not mean one OS process total.

PreparedDocument caches token streams and first-word indexes per document. CompiledRuleSet caches keyword phrases and weighted terms within a configuration snapshot for the mail; no mail-derived state is written back into the launcher. Custom regex remains separately bounded; no unsafe in-process regex replacement.

## Isolation
The child has a private directory, resource limits, seccomp, Landlock ABI >=3, parent-death signal and its own process group. Landlock is required, not a silent fallback. The child inherits a connected Unix socket, not an unrestricted network client. The trusted parser broker proxies only fixed POST http://ocr-parser:8090/parse with operation extract, limits request size/count and response size, forbids redirects and does not log content. The parser is on two internal Docker networks; no DB/broker/default network membership is added. Verify the deployment kernel and Docker seccomp policy support Landlock before enabling. Same-UID signal interference, /proc restrictions, malicious descendant cleanup, and memory peaks under parallel large attachments require explicit adversarial testing; do not represent process isolation as equivalent to separate VMs.

## Deployment and migration
The branch is based on df9f582 (published main). Reconcile the agent's newer RU3 and parser backpressure/deferral changes first, especially parser_service, parser_client, services/tasks and migration graph. Preserve temporary HTTP errors, Retry-After, finite deferral budget and diagnostics; the published base does not contain the local changes. The new queue migration changes model choices only. If the local branch already has a 0005 migration, generate a merge migration or rebase the new choice migration; never reset data.
Default MICE_UNIFIED_ANALYSIS_ENABLED=false; do not enable before tests pass. Keep legacy ingestion.parse, extraction.extract, ocr.complete and detection.detect consumers until all old work, delayed retries and recoverable jobs are drained or explicitly migrated. Then stop those legacy extraction/ocr/detection Celery consumers (not the OCR parser service). Do not purge existing queues or DB blindly. Rollback: disable new admissions, finish existing analysis jobs with the new worker/parser enabled or explicitly recover them, then return to legacy admissions. Never disable the parser endpoint while its jobs remain active.

Suggested settings after validation:
- MICE_UNIFIED_ANALYSIS_ENABLED=true
- MICE_ANALYSIS_CONCURRENCY=2
- MICE_PARSER_CONCURRENCY=2
- MICE_PARSER_QUEUE_SIZE=3
- MICE_PARSER_SLOT_WAIT_SECONDS=5
- MICE_ANALYSIS_WALL_TIMEOUT=600
- MICE_ANALYSIS_TIMEOUT=720

Keep worker deadlines larger than parser wall timeout plus AV/DB/policy overhead. Monitor parser CPU/RSS, tmpfs, cgroup OOM/throttling, active/queued slots, stage timings and OCR saturation. An OCR-waiting child occupies a slot. Do not tune concurrency by guesswork.

## Acceptance gates (not run by this PR author)
1. Resolve local changes and migration graph; run python manage.py check, makemigrations --check --dry-run and Django test identity records pipeline policy_engine --noinput.
2. On the parser image with real Linux Landlock/seccomp, run tests/test_unified_analysis.py and tests/test_text_match.py using pytest in a suitable test environment. Test native attachments, real OCR service with valid images/PDF, archives, Gitleaks, custom regex, antivirus, oversized and malformed mail, cancellation and launcher crash/timeout. Verify a sandbox cannot open network sockets, read sibling workspaces, access DB/broker secrets, escape its process group or signal another request. Verify process and temporary-directory cleanup. Fail closed if isolation unavailable; do not weaken it to make tests pass.
3. Test old and new queues concurrently during cutover; inspect deduplication, stale fencing, deferrals, partial errors, reanalysis and one policy evaluation per successful job.
4. On a clean test database with unchanged RU3 configuration, process all 350 original EML files via normal intake using legacy and unified routes. Compare findings (category, rule ID, risk, confidence, offsets, document association normalized by attachment identity), statuses and incidents. Attachment IDs can differ; don't compare them literally. The shared aggregate extraction budget intentionally bounds expansion across attachments; limit-triggering inputs may differ from the old per-attachment budget. Investigate any other semantic differences before enabling.
5. Record launches, stage times, wall throughput, p95, deferrals, DEAD/CANCELLED, CPU, RSS and swap for concurrency 1 and 2. No measured speedup is claimed.

Legacy extraction/OCR/detection handlers remain available for transition. Removing compatibility handlers, changing OCR models, modifying RU3 and adding persistent cross-mail rule caches are out of scope for this PR.
