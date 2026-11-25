from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pipeline", "0004_queue_choices")]
    operations = [migrations.AddField(model_name="workitem", name="deferrals",
                                     field=models.PositiveIntegerField(default=0))]