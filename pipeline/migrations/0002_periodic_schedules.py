from django.db import migrations


def seed(apps, schema_editor):
    schedule = apps.get_model("pipeline", "PeriodicSchedule")
    for identifier, kind in [
        ("9f644100-0000-4000-8000-000000000001", "maintenance.resources"),
        ("9f644100-0000-4000-8000-000000000002", "maintenance.recover"),
    ]:
        schedule.objects.using(schema_editor.connection.alias).get_or_create(
            pk=identifier, defaults={"kind": kind, "interval_seconds": 30}
        )


class Migration(migrations.Migration):
    dependencies = [("pipeline", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
