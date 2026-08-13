"""Idempotently seed the RBAC groups and their permission sets.

Run via ``python manage.py seed_rbac``. Safe to run repeatedly — existing
groups are updated in place.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import RoleCode
from apps.accounts.rbac import ROLE_GROUP_NAMES, group_permission_codenames


class Command(BaseCommand):
    help = "Create RBAC groups for every role and assign their permissions."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        permissions_by_key: dict[tuple[str, str], Permission] = {}
        for permission in Permission.objects.all():
            permissions_by_key[(permission.content_type.app_label, permission.codename)] = permission

        for role, group_name in ROLE_GROUP_NAMES.items():
            group, created = Group.objects.get_or_create(name=group_name)
            desired = group_permission_codenames(role)
            group.permissions.set([permissions_by_key[key] for key in desired if key in permissions_by_key])
            self.stdout.write(
                f"  {'created' if created else 'updated'} group: {group_name} ({group.permissions.count()} permissions)"
            )

        self.stdout.write(self.style.SUCCESS(f"RBAC seeded for {len(ROLE_GROUP_NAMES)} roles."))
        self.stdout.write(f"  roles: {', '.join(r.value for r in RoleCode)}")
