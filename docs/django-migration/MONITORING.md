# Operations checkpoint

Server-rendered `/operations/` and authenticated `/api/monitor/queues` report
PostgreSQL pending/running/dead counts, oldest pending age, completions in the
last hour, mean successful attempt duration, unpublished/error dispatch counts.
RabbitMQ Management supplies ready/unacknowledged counts and consumers; Celery
inspect ping supplies responding workers. Calls are bounded and degraded states
are explicit. No Docker socket or privileged host telemetry is mounted.

The HTML page shows the latest 100 jobs (queue/status filters) without payloads,
and recent worker-visible CPU/RAM/process RSS samples. Admin-only cancel/retry
POSTs use Django CSRF and record audit events. Observers can inspect but cannot
control work. GPU and full per-container health/resource metrics remain unavailable;
worker-visible psutil values are labeled, not presented as container limits.
UI is functional but does not yet reproduce the legacy SystemStatus/Queues layout
or auto-refresh behavior; visual parity remains pending.

Minimal checks: four pipeline tests passed (1.075 s), including actual template
rendering, payload non-disclosure and observer control denial. Django check,
template compilation and Ruff passed. No mail fixtures/processing/benchmark.
Docker web/frontend build was started separately; completion must be checked
before claiming deployed runtime validation.