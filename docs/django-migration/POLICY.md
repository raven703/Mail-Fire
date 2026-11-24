# Policy Engine checkpoint

`policy_engine` is a logical Django module, not an HTTP microservice. Its jobs
execute on the dedicated `policy` Celery queue. Policy requests snapshot persisted
findings, detector version, message completeness, sender/recipients, delivery IDs,
active categories, detector switches and the entire ordered policy set.
AnalysisRevision/PolicyRevision/Evaluation preserve historical inputs and outputs.
Snapshots are append-only through the service API; administrative SQL access is
not prevented from modifying them.

`POST /api/messages/<id>/reevaluate` uses Django sessions/CSRF and requires the
investigate permission. Optional `request_id` is a UUID for client deduplication;
reusing it with different snapshots is rejected, not silently reinterpreted.
No saved findings or no delivery context yields 409/requires_analysis. Existing
PARTIAL evidence may still produce incident evidence, but never becomes ANALYZED.
This endpoint does not invoke parsing, extraction, OCR, detection, ML or LLM.
It cannot reconstruct evidence absent from the stored analysis and does not
automatically rerun missing stages. The old reanalyze endpoint is not replaced.

The unchanged pure policy_matches and classify_direction functions were extracted
from master without importing the old SQLAlchemy/FastAPI/inference runtime.
ANY/ALL, thresholds, shadow policies, disabled categories, ML switches and
historical inactive hits retain their source semantics. Evaluation locks message
and job rows, preserves incident workflow/comments/assignee and keeps the unique
incident/message constraint. Evaluation + incident + notification intents + job
completion commit together under the current attempt token.

New incident notification intents use the dedicated notifications queue. HTTP
preserves the incident Idempotency-Key; syslog/CEF preserve existing UDP behavior.
External UDP receivers inherently cannot guarantee deduplication. HTTP receiver
cooperation is required after a crash between delivery and database commit.
Delivery I/O runs outside DB transactions; completion is fenced. WorkItem/Attempt
is authoritative for retry/dead status; legacy outbox UI has not yet been adapted.

Validation: migrations applied on isolated PostgreSQL, migration drift check;
two tiny pure-rule tests, including AST equivalence to source functions, plus
the three existing delivery tests. **No messages were imported, created as test
fixtures, processed or benchmarked.** Incident behavior, full policy CRUD/history,
notification end-to-end and browser UI parity are not acceptance-tested here.

Remaining: connect new staged analysis producers, finish policy CRUD and UI,
bulk reevaluation orchestration, operational history/metrics screens and retention
rules for new immutable history tables. Live legacy deployment is unchanged.