import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("records", "0001_initial")]

    operations = [migrations.CreateModel(
        name="InferenceArtifact",
        fields=[("sha256", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.BinaryField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now))],
        options={"db_table": "inference_artifacts"},
    )]