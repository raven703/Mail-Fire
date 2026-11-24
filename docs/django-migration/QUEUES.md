# Reliable delivery checkpoint

Implemented in `pipeline/`: PostgreSQL WorkItem/Attempt state with unique
deduplication keys, fenced ownership tokens/deadlines, atomic handler completion,
transactional dispatch outbox, publisher confirms, retry backoff/jitter, bounded
attempts, explicit cancellation/retry and recovery of expired/lost deliveries.
Broker payloads carry IDs only; job payloads and outputs remain in PostgreSQL.
Publication errors retain outbox records and backoff. Duplicate publications
are expected; claiming and completion are idempotent. No result backend/Redis.

RabbitMQ 4.2 quorum queues and their dead-letter queues are explicitly declared
for all ten requested groups. Persistent messages, late ACK, reject-on-worker-loss,
delivery limit and at-least-once dead-letter routing are configured. This is a
single broker, NOT a high-availability RabbitMQ cluster. Durable volumes survive
container replacement but do not replace backups or replicated storage.

Celery Beat publishes schedule IDs. Schedule rows prevent duplicate periodic
creation. Initial real handlers sample worker-visible CPU/RAM/disk and recover
delivery. GPU is explicitly unavailable rather than fabricated. Publisher can
recover delivery independently of Beat during broker trouble; it never executes
domain analysis. No ETA/countdown tasks are used: retry availability is durable
in the outbox. Celery's direct-exchange delayed-delivery startup warning therefore
does not affect this design.

Compose has separate worker groups with independent concurrency/prefetch/timeout,
CPU/RAM and independently scalable replicas. Non-maintenance groups are in the
`pipeline` profile: queues exist, but unported analysis handlers are NOT registered
or treated as successful. Heavy model libraries are absent from this runtime
image. Parser/Converter and the legacy pipeline have NOT been switched over.
Do not enable both old and new consumers for the same migrated domain jobs.

## Minimal validation (no message tests)

- Three PostgreSQL-backed tests: enqueue rollback/dedup/completion, expired worker
  fencing/dead-letter intent, failed publish retention/backoff.
- Pipeline migrations applied to isolated DB; migration drift check passes.
- Real RabbitMQ topology declared; a real prefork Celery maintenance worker
  consumed a resource-sampling job published from the outbox and completed it.
- Real resource-sampling smoke only: no message, OCR, detection, ML, LLM, benchmark
  or full failure/load campaign was run. Worker/broker/DB kill/restart acceptance
  remains outstanding. Docker runtime image was built locally; complete Compose
  application deployment and resource tuning are not yet validated.

Use a dedicated `DJANGO_SECRET_KEY`, `MICE_DB_PASSWORD`, URL-safe
`MICE_RABBIT_PASSWORD`. Runtime commands:

```
docker compose -f /home/user/Mail-Fire-django-htmx/compose.django.yaml up -d --build
```

Management uses loopback 15673, AMQP loopback 15674, experimental DB loopback
15433. These host ports are for local validation; production should not expose
DB/AMQP. No live `mailfire` volume, network, DB or image tag is reused.