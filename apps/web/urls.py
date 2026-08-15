"""Root and operational URL patterns served by the host-facing app."""

from django.urls import path, re_path

from . import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    re_path(r"^app(?:/.*)?$", views.react_app, name="react_app"),
    path("marketing/", views.react_app, name="marketing"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.landing, name="landing"),
]
