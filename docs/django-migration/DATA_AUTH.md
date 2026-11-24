# Data/Auth checkpoint

Implemented: Django 5.2.19 LTS project, explicit ORM mappings for all 25 legacy
tables plus semantic_chunks, vector(384), frozen PostgreSQL DDL and Django
migration state. Existing IDs, blobs, foreign keys, uniqueness, FTS/trigram/HNSW
indexes remain in the schema. Initial schema creation is irreversible on purpose:
rollback is restoration of a backup, not destructive reverse migrations.

Auth uses Django sessions, CSRF, Argon2 and permission checks. A separate
`mice_users` table preserves legacy account IDs without rewriting historical
references. The four capabilities preserve role + independent originals access,
including for superusers. Legacy PHC hashes are upgraded on successful login.
Disabled accounts cannot authenticate. Old cookies are not accepted or imported.
Current legacy services still own `accounts`; account writes must be frozen at
cutover. Subsequent Django account-management port must synchronize historical
account references before allowing new users to author investigation records.

## Local isolated environment

Install `requirements.django.lock` in the experimental worktree's own venv.
Set a dedicated `DJANGO_SECRET_KEY` and `MICE_DB_PASSWORD`. Do not copy the live
`.env`. `compose.django.yaml` currently provides only the isolated PostgreSQL
service, published on loopback 15433; it is not the finished application stack.
The experimental database uses the project-scoped `django-postgres` volume.

Fresh database: `manage.py migrate`, then provision users explicitly.
Restored legacy backup: restore only into `mice_django_experiment`, run
`manage.py adopt_legacy_schema` (read-only validation), then repeat with `--apply`.
Only Alembic revision 0007 is accepted. Columns, nullability, types, uniqueness,
FKs and important search indexes are checked before recording migration state.
Then run `manage.py migrate` and `manage.py import_legacy_accounts`.
The import is atomic, does not overwrite existing users and rejects collisions,
unknown roles and unsupported hashes. Back up before applying. Do not point any
of these commands at the live database. A restored production backup and its
row/blob hash comparison have NOT been exercised in this checkpoint.

The Django auth JSON endpoints require the standard `X-CSRFToken` header,
including login. Fetch `/api/csrf` first and refresh the token after login.
The existing React client has NOT been switched to these endpoints yet.

## Minimal validation only

Per the user's revised instruction: no message tests, holdout, OCR/ML/LLM,
benchmark, full regression or load suite was run during this checkpoint.
Fresh real PostgreSQL migration succeeded. Two focused Auth tests cover legacy
import, password upgrade, role/originals separation, disabled access, session
login/logout and CSRF. Migration drift check and Ruff are also required.

The legacy runtime remains unchanged. Pipeline, Celery/RabbitMQ, templates and
full account-management parity are future checkpoints, not implemented features.