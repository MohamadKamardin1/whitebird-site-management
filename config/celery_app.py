"""Celery application factory for the White Bird platform."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("whitebird")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
