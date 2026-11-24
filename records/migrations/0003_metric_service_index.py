from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("records", "0002_inferenceartifact")]

    operations = [
        migrations.AddIndex(
            model_name="metric",
            index=models.Index(fields=["service", "-created_at"], name="metrics_service_created_idx"),
        ),
    ]
