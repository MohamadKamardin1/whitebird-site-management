from typing import Any

from django.db import migrations


def seed_site_stores(apps: Any, schema_editor: Any) -> None:
    Site = apps.get_model("site_management", "Site")
    SiteStore = apps.get_model("site_management", "SiteStore")
    for site in Site.objects.all():
        if not SiteStore.objects.filter(site=site, is_active=True).exists():
            SiteStore.objects.create(site=site, store_name=f"{site.name} Store", location="")


def noop(apps: Any, schema_editor: Any) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [("site_management", "0019_zone_boundary")]
    operations = [migrations.RunPython(seed_site_stores, noop)]
