# Parser load incident and recovery

## Verified evidence

The initial database snapshot contained 306 DEAD jobs: ingestion.parse 101,
extraction.extract 124, detection.detect 81. Every error was HTTPStatusError.
The available worker HTTP logs contained 896/703/509 HTTP 503 responses,
respectively, and no other error status. These counts include retries and are
not counts of failed messages. Old errors did not retain HTTP status or reason,
so attributing every historical attempt individually is impossible.

The parser shared by three queues used BoundedSemaphore(1) with nonblocking
acquisition and immediate 503. Workers treated that as a processing failure,
exhausting the five-attempt budget. OCR uses another service; policy does not
call the parser. Their lack of this error is consistent with this mechanism.

## Implemented

- Keep one sandbox process, admit at most four executing/waiting requests,
  wait at most five seconds for the slot, and return fixed queue_full/busy
  tokens with Retry-After. Request bodies are not allocated before admission.
- Transport/timeouts and HTTP 408/425/429/500/502/503/504 are dependency
  unavailability: durable delayed dispatch, bounded exponential jitter,
  Retry-After capped at 300 seconds, no worker sleep/retry loop.
- Deferral refunds the claim's processing attempt, increments deferrals and
  preserves a distinct immutable Attempt row with monotonic audit numbering.
  Ownership tokens fence old attempts; deferrals never exhaust max_attempts.
- Other non-success HTTP statuses are permanent rejections and terminate
  immediately. Unknown handler errors retain the existing bounded retry policy.
- Diagnostics include fixed service alias, allowlisted operation, status and
  fixed reason. No URL, credentials, filename, mail text or HTTP body is logged.
- Pipeline migration 0005 adds the deferrals counter.

## Capacity decision

## Prolonged outage monitoring

The operations queue panel and monitoring JSON expose parser degradation,
job age in seconds, deferrals and next retry. Age >= 3600 seconds is critical.
After 86400 seconds of job age (override via Django setting
MICE_PARSER_MAX_WAIT_SECONDS), the next dependency failure stops automatic
retries as CANCELLED with wait_budget_exceeded, not DEAD or malformed mail.
These jobs remain visible in the degradation panel and can be manually retried.
The budget is based on total job age, including queue residence, not measured
continuous outage duration. Raising the budget may be necessary before manually
retrying an old job during an ongoing outage.

Observed host: 4 CPUs, 9.7 GiB RAM, 5.7 GiB available, 1.1 GiB swap used.
Parser container limit is 3 GiB; sandbox can use four BLAS/OpenMP threads.
Three simultaneous full parser services could approach 9 GiB plus DB, broker,
OCR and workers and oversubscribe CPU. Therefore do not enable three copies by
default. First use bounded admission and durable backpressure. If measured
latency requires separation, isolate detection from mail/extraction with explicit
CPU/RAM budgets and lower per-process thread counts; benchmark peak RSS and CPU
before enabling. This is a capacity assessment, not a measured speedup claim.

## Recovery

`recover_parser_dead --plan /absolute/path/plan.json` previews eligibility.
`recover_parser_dead --plan /absolute/path/plan.json --apply` rechecks under row
locks, creates an audit entry and reuses the original WorkItem/deduplication key.
It never reimports mail or directly creates attachments/incidents.

Initial plan: 226 eligible, 80 superseded by newer stage jobs. The 226 were
submitted for recovery after deployment. Superseded jobs deliberately retain
history and must not be replayed over newer attachment/content evidence.
Recovery is asynchronous; submission is not proof of completed processing.
Permanent errors and invalid parent chains require manual review.

Existing handlers fence and commit stage effects plus completion atomically;
extraction refuses existing attachment evidence, and policy locks the message
and updates its incident. These safeguards prevent ordinary redelivery from
appending duplicates. They do not justify blind replay of stale analysis chains.

Evidence and plans: /home/user/mice-archives/parser-backpressure/.
153 Django tests passed after the change; migration-state check and diff check
passed. OCR configuration was not changed. Benchmark recovery scripts were
paused to avoid concurrent reanalysis during job recovery. The original frozen
benchmark observations are not rewritten by this recovery command.