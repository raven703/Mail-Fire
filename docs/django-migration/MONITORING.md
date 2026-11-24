# Native monitoring

`/operations/` includes mail and technical queues, hourly delivery statistics,
per-service resource history, PostgreSQL health and job controls. The queue
panel refreshes periodically. `/api/monitor/queues` remains available to
authenticated users with workspace access. RabbitMQ and Celery management
provide queue and worker statistics alongside persisted status and attempt timing.

Each Compose service has a scoped probe. The maintenance worker stores samples
and expires new resource series after seven days. The display shows the last 20
points per service, including stale/missing states and GPU data when exposed.
See [BUILD-NATIVE.md](BUILD-NATIVE.md) for deployment wiring.

Queue controls and PostgreSQL details are administrator-only. Job payloads are
excluded from list pages. Diagnostic and audit details are originals-gated.
Live resource and PostgreSQL verification are deferred.
