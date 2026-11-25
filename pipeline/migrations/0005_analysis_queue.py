"""Register unified analysis queue without modifying existing work items."""
from django.db import migrations, models

GROUPS = ("neural", "neural_training", "semantic", "ingestion", "analysis",
          "extraction", "ocr", "detection", "ml", "llm", "policy",
          "notifications", "training", "maintenance")


class Migration(migrations.Migration):
    dependencies = [("pipeline", "0004_queue_choices")]
    operations = [
        migrations.AlterField(model_name="workitem", name="queue",
                              field=models.CharField(choices=[(g, g) for g in GROUPS], max_length=24)),
    ]
