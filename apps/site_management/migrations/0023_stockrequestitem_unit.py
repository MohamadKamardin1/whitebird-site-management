from django.db import migrations, models


def copy_configured_units(apps, schema_editor):
    StockRequestItem = apps.get_model("site_management", "StockRequestItem")
    for item in StockRequestItem.objects.select_related("store_item").filter(unit="").iterator():
        item.unit = item.store_item.unit
        item.save(update_fields=["unit"])


class Migration(migrations.Migration):
    dependencies = [
        ("site_management", "0022_dailysitereport_challenges"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockrequestitem",
            name="unit",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.RunPython(copy_configured_units, migrations.RunPython.noop),
    ]
