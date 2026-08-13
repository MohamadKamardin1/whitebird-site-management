from django.apps import AppConfig


class SiteManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.site_management"
    verbose_name = "Site Management"
    label = "site_management"

    def ready(self) -> None:
        from . import signals  # noqa: PLC0415,F401 - registers post_migrate receiver
