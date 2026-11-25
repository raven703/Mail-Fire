from django.db import migrations, models
import records.models


class Migration(migrations.Migration):
    dependencies = [("records", "0005_categoryrule_deleted_at")]
    operations = [migrations.CreateModel(name="OCRTestDocument", fields=[
        ("id", models.CharField(default=records.models.record_id, max_length=36, primary_key=True, serialize=False)),
        ("owner", models.CharField(max_length=36, db_index=True)),
        ("data", models.BinaryField()), ("name", models.CharField(max_length=40)),
        ("expires_at", models.DateTimeField(db_index=True)),
    ])]