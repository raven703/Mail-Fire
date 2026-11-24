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
policy editor/list/history is now available at `/policies/`; no full visual parity claimed.

HTML and JSON adapters use `policy_engine/catalog_service.py` as the single
transactional domain implementation. HTML includes modal conditions editor,
history, archive filtering, restore/delete and read-only observer access. A
focused page lifecycle test verifies database writes and role enforcement.
Nested category selection/creation and live summary remain pending, along with
browser visual comparison. Existing detector catalog remains in catalog.py.