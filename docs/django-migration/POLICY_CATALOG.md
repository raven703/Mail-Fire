# Policy catalog API checkpoint

Ported policy list, create/update, enabled toggle, history, archive/restore and
delete at existing catalog/workspace paths using ORM and Django session/CSRF.
Validation mirrors legacy bounds, category availability/mode, category-match,
direction checks. Edits lock policy rows; save increments version and records
before/after audit. Immutable PolicyRevision evidence is retained across deletion.
Deleting clears representative Incident.policy FK without changing policy_hits.
Archive and restore both disable execution, matching the legacy behavior.

Three focused tests pass in 0.256 s: AST parity of pure policy rules plus one
database CRUD lifecycle/category validation/snapshot-retention case. No message
processing or email fixtures were executed. No schema drift detected. Server UI
policy editor/list/history remains to be ported; no full visual parity claimed.