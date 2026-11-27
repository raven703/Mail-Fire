from django.db import migrations

OLD_NAME = "Коммерческая тайна"
NEW_NAME = "Грифы конфиденциальности"
FALLBACK_NAME = f"{NEW_NAME} (CONFIDENTIAL)"


def rename_category(apps, schema_editor):
    rows = apps.get_model("records", "Category").objects.using(schema_editor.connection.alias)
    target = rows.filter(pk="CONFIDENTIAL", name=OLD_NAME)
    if not target.exists():
        return
    name = NEW_NAME
    if rows.exclude(pk="CONFIDENTIAL").filter(name=name).exists():
        name = FALLBACK_NAME
    if rows.exclude(pk="CONFIDENTIAL").filter(name=name).exists():
        raise ValueError("Confidentiality label category name is already in use")
    target.update(name=name)


def restore_category(apps, schema_editor):
    rows = apps.get_model("records", "Category").objects.using(schema_editor.connection.alias)
    target = rows.filter(pk="CONFIDENTIAL", name__in=[NEW_NAME, FALLBACK_NAME])
    if not target.exists():
        return
    if rows.exclude(pk="CONFIDENTIAL").filter(name=OLD_NAME).exists():
        raise ValueError("Previous confidentiality category name is already in use")
    target.update(name=OLD_NAME)


class Migration(migrations.Migration):
    dependencies = [("records", "0007_incident_number")]

    operations = [migrations.RunPython(rename_category, restore_category)]
