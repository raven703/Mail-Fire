"""Explicit state-only cutover of a restored Alembic 0007 database."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = "Validate a restored legacy schema; --apply records adoption without changing legacy rows."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        problems = []
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))
            if "alembic_version" not in tables:
                raise CommandError("Expected a restored Alembic database, not a fresh Django database")
            cursor.execute("SELECT version_num FROM alembic_version")
            if cursor.fetchall() != [("0007",)]:
                raise CommandError("Only an Alembic 0007 backup may be adopted")
            for model in apps.get_app_config("records").get_models():
                table = model._meta.db_table
                if table not in tables:
                    problems.append(f"Missing table {table}")
                    continue
                description = {
                    c.name: c for c in connection.introspection.get_table_description(cursor, table)
                }
                expected = {f.column for f in model._meta.local_fields}
                if set(description) != expected:
                    problems.append(f"Column mismatch in {table}")
                    continue
                constraints = connection.introspection.get_constraints(cursor, table)
                for field in model._meta.local_fields:
                    actual = description[field.column]
                    if actual.null_ok != field.null:
                        problems.append(f"Nullability mismatch: {table}.{field.column}")
                    # Compare actual PostgreSQL type to the Django mapping; varchar
                    # without a limit and text are intentionally different types.
                    cursor.execute(
                        "SELECT format_type(a.atttypid,a.atttypmod) FROM pg_attribute a "
                        "WHERE a.attrelid=%s::regclass AND a.attname=%s",
                        [connection.ops.quote_name(table), field.column],
                    )
                    actual_type = cursor.fetchone()[0]
                    expected_type = field.db_type(connection).replace("varchar", "character varying")
                    if field.get_internal_type() == "DateTimeField":
                        expected_type = "timestamp without time zone"
                    if actual_type != expected_type:
                        problems.append(
                            f"Type mismatch: {table}.{field.column}: {actual_type} != {expected_type}"
                        )
                    if field.unique and not any(
                        (c["unique"] or c["primary_key"]) and c["columns"] == [field.column]
                        for c in constraints.values()
                    ):
                        problems.append(f"Missing uniqueness: {table}.{field.column}")
                    if field.is_relation:
                        target = (field.related_model._meta.db_table, field.target_field.column)
                        if not any(
                            c["foreign_key"] == target and c["columns"] == [field.column]
                            for c in constraints.values()
                        ):
                            problems.append(f"Missing foreign key: {table}.{field.column}")
            for index in [
                "contents_fts",
                "semantic_chunks_vector",
                "semantic_chunks_source",
                "ix_messages_subject_trgm",
                "ix_messages_sender_trgm",
                "ix_contents_text_trgm",
                "ix_attachments_name_trgm",
                "ix_messages_recipients_trgm",
                "ix_incidents_event_risk",
                "ix_incidents_status_created",
                "ix_mail_events_message_source",
            ]:
                cursor.execute("SELECT to_regclass(%s)", [index])
                if cursor.fetchone()[0] is None:
                    problems.append(f"Missing index {index}")
        if problems:
            raise CommandError("Schema adoption refused:\n" + "\n".join(problems))
        if options["apply"]:
            recorder = MigrationRecorder(connection)
            recorder.ensure_schema()
            recorder.record_applied("records", "0001_initial")
            self.stdout.write(
                self.style.SUCCESS("Adopted records schema; now run migrate and import_legacy_accounts")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Schema validated; no changes made (use --apply to adopt)"))
