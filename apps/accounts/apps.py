from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"
    label = "accounts"

    def ready(self) -> None:
        from . import signals  # noqa: F401,PLC0415 - registers role-group sync
