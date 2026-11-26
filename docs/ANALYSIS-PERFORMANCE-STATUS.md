# Performance configuration and failed mail

Follow-up to unified analysis PR #17. The load baseline was 350/350 in 17m08.49s,
2/2 concurrency, 1,225 mail/hour and F1 96.91% on the RU3 benchmark.
This is not a new benchmark or a sustained 24-hour result.

## Deployment

The new Settings → Performance page is admin-only. It validates and stores a
desired deployment profile in PostgreSQL and exports an allowlisted .env
fragment. It does not write host files, restart Docker, or change runtime
settings secretly. The displayed environment reflects the web process's
declared configuration, not independently measured remote service settings.

Recommended benchmark settings:
```env
MICE_UNIFIED_ANALYSIS_ENABLED=true
MICE_ANALYSIS_CONCURRENCY=2
MICE_PARSER_CONCURRENCY=2
MICE_SANDBOX_ADDRESS_LIMIT_MIB=1024
```
The fourth setting is new and not part of the original benchmark. Validate it
on the target system. Drain existing jobs, back up the database, merge these
keys into the existing .env without replacing secrets, and recreate services
using the normal Compose procedure. Do not remove volumes. Existing installs
retain their explicit flag; legacy Compose fallback stays off to avoid a
silent routing change during upgrade.

RLIMIT_AS bounds virtual address space for each primary forked child; it is
not a private cgroup/RSS limit. Existing CPU/file/FD limits and parser cgroup
remain. Helper and OCR limits remain separate. The UI checks conservative
headroom for the shipped 3 GiB parser; it cannot guarantee zero OOM.

## Failure semantics

Transient transport and OCR dependency failures defer with the existing
finite waiting budget. Known sandbox deadline/errors consume bounded attempts;
an explicitly reported MemoryError is rejected for manual retry. A closed
connection alone cannot prove an OOM or a per-message fault. Unknown closures
remain temporary until the existing waiting budget is exhausted.

Latest unified DEAD/CANCELLED transitions mark a PENDING message FAILED,
without deleting original mail or previous evidence. Stale attempts cannot
overwrite a later run. PARTIAL results retain their existing findings.
The 0007 migration reconciles historical unified terminal jobs and indexes
the latest-root-job lookup. Legacy pipeline terminal semantics are not
redesigned in this PR.

Messages show the derived current processing/retry state, sanitized reason,
and full reanalysis action. Overview exposes a period-aware incomplete-mail
counter; its risk links use native navigation to avoid inheriting the live
poll's HTMX fragment selector.

## Before merge

Run Django CI including migration checks, restricted-container tests including
the new per-message address-limit probe, verify risk drill-down in the browser
manually, and verify the deployment configuration and failure/retry paths.
Confirm the new limit does not regress normal processing with real documents.
No rule, model, or OCR provider changes are intended.
