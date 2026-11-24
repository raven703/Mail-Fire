from django.db import migrations


def seed(apps, schema_editor):
    # Scheduler registration is safe: retention itself defaults to paused.
    schedule = apps.get_model("pipeline", "PeriodicSchedule")
    schedule.objects.using(schema_editor.connection.alias).get_or_create(
        pk="9f644100-0000-4000-8000-000000000003",
        defaults={"kind": "maintenance.retention", "interval_seconds": 86400},
    )


class Migration(migrations.Migration):
    dependencies = [("pipeline", "0002_periodic_schedules")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]