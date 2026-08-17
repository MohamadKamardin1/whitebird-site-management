from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("site_management", "0021_seed_pdf_cleanliness_checklists"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailysitereport",
            name="challenges",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
