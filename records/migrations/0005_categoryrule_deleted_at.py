from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("records", "0004_seed_system_categories")]
    operations = [
        migrations.AddField(
            model_name="categoryrule", name="deleted_at",
            field=models.DateTimeField(blank=True, db_index=True, editable=False, null=True),
        ),
    ]