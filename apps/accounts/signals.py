"""Account signals — keep a user's role group in sync with their role."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import RoleCode, User
from .rbac import ROLE_GROUP_NAMES


@receiver(post_save, sender=User)
def sync_user_role_group(sender: Any, instance: User, **kwargs: Any) -> None:
    """Ensure the user belongs to the group matching their role.

    Membership in *other* role groups is removed so a user only ever carries
    one role's permissions; any manually-assigned non-role groups are kept.
    Groups are created on demand so the platform works before ``seed_rbac``
    has run.
    """
    group_name = ROLE_GROUP_NAMES.get(RoleCode(instance.role))
    if group_name is None:
        return
    group, _ = Group.objects.get_or_create(name=group_name)

    role_group_names = set(ROLE_GROUP_NAMES.values())
    role_groups = Group.objects.filter(name__in=role_group_names)
    instance.groups.remove(*role_groups.exclude(name=group_name))
    if not instance.groups.filter(pk=group.pk).exists():
        instance.groups.add(group)
