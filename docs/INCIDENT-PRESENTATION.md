# Incident numbers and grouped evidence

Presentation-only grouping keeps every finding; groups are keyed by category,
rule identity, source and saved rule/detector revision. Each occurrence retains
its excerpt, source document, risk and coordinates. Historical rule parameters
appear once per group. Current attachment names and saved attachment snapshots
are used when available; legacy unknown sources are not mislabelled as body.
No detector, matching, policy, risk calculation or inference logic is changed.

Incident.number is a database-generated unique bigint (PostgreSQL sequence).
The display format is INC-000001, with no rollover after six digits. The
existing UUID remains the primary key, including all URLs and relationships.
Numbers are stable and not reused after deletion during normal operation.
Sequence gaps are normal after rollbacks. They are not incident counts.

Migration records.0007 assigns existing rows numbers ordered by creation time
and UUID, advances the sequence and installs the database default and unique
constraint. The migration locks the incidents table; back up and apply during
a maintenance window. Rollback removes display numbers, not incidents.

Before merge: Django CI, migration-state check and migration with existing
data, verify the grouped evidence visually. No benchmark required. Do not
purge data or restart/change the analysis architecture.
