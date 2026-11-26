"""Stable display numbers, independent of UUID and incident status."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("records", "0006_ocrtestdocument")]
    operations = [
        migrations.RunSQL(
            "CREATE SEQUENCE mice_incident_number_seq AS bigint START WITH 1",
            "DROP SEQUENCE mice_incident_number_seq",
        ),
        migrations.AddField(
            model_name="incident", name="number",
            field=models.BigIntegerField(null=True, editable=False),
        ),
        migrations.RunSQL(
            """WITH ranked AS (
                SELECT id, row_number() OVER (ORDER BY created_at, id) AS n FROM incidents
            )
            UPDATE incidents SET number = ranked.n FROM ranked WHERE incidents.id = ranked.id;
            SELECT setval('mice_incident_number_seq',
                          COALESCE((SELECT max(number) FROM incidents), 1),
                          EXISTS (SELECT 1 FROM incidents));""",
            migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="incident", name="number",
            field=models.BigIntegerField(unique=True, editable=False, db_default=models.Func(
                template="nextval('mice_incident_number_seq'::regclass)", output_field=models.BigIntegerField(),
            )),
        ),
    ]
