# Accounts checkpoint

Django JSON account CRUD now preserves the existing validation, role/originals
fields, password length, duplicate-name rejection, self-revocation protection,
last-admin protection, soft deletion, audit and session invalidation semantics.
Changes serialize with the legacy accounts-admin advisory lock. The actor is
rechecked inside that lock. Responses/audit never contain password hashes.

Django users synchronize the historical accounts row under the same transaction,
including new users from create_user/create_superuser, so investigation FKs can
continue to use account IDs. Django Argon2 hashes are converted to legacy PHC
representation in that row. Legacy service account writes must still be frozen
at cutover: this is not a bidirectional identity synchronization system.

Every account edit increments access_version. Middleware rejects a session with
an older version at its next request, including role-only changes; password
changes also retain Django's native auth-hash invalidation. Existing experimental
sessions without a version are intentionally logged out. The legacy sessions
for edited accounts are deleted too. In-flight requests are not retroactively
terminated. Legacy import remains atomic and does not overwrite existing users.

First server-rendered pages: login, logout and account management. Original CSS
and logos are copied byte-for-byte into static/mice; no Node build is needed.
These pages use normal Django POST/redirect/GET and CSRF. **UI parity is NOT
complete**: account editing is presently an inline form rather than the original
modal; full navigation, themes and dialogs still need the shared template/JS
port. No screenshot/browser parity is claimed. These pages do not replace the
live React UI or expose unported features as working links.

Validation: three focused Auth/account tests passed (1.342 s); migration applied
to experimental DB; no migration drift; template compilation and Ruff passed.
No message tests, benchmark or full regression. Template pages are not yet
served by a production Compose web service; static serving/deployment will be
connected in the shared web-runtime checkpoint.