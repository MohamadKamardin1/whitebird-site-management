"""Tests demonstrating the factory-boy data factories."""

import pytest

from apps.accounts.factories import ApiTokenFactory, UserFactory
from apps.accounts.models import ApiToken, Role, User
from apps.site_management.factories import SiteFactory, SiteStatusFactory, SiteTypeFactory


@pytest.mark.django_db
def test_user_factory_builds_unique_users_with_role() -> None:
    user = UserFactory(role=Role.MANAGER, password="S3cure-pass")
    assert user.check_password("S3cure-pass")
    other = UserFactory()
    assert user.pk != other.pk
    assert User.objects.count() == 2


@pytest.mark.django_db
def test_api_token_factory_issues_real_tokens() -> None:
    token = ApiTokenFactory()
    assert token.key
    assert ApiToken.objects.filter(key=token.key).count() == 1


@pytest.mark.django_db
def test_site_factory_wires_catalog_references() -> None:
    site = SiteFactory()
    assert site.status is not None
    assert site.site_type is not None
    assert site.code.startswith("SITE")
    assert SiteStatusFactory(slug=site.status.slug).pk == site.status.pk
    assert SiteTypeFactory(slug=site.site_type.slug).pk == site.site_type.pk
