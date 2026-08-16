from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("site_management", "0018_seed_default_cleanliness_templates")]
    operations = [
        migrations.AddField(
            model_name="zone",
            name="boundary",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
