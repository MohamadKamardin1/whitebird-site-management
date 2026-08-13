"""Root and operational URL patterns served by the host-facing app."""

from django.urls import path

from . import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    path("", views.landing, name="landing"),
]
