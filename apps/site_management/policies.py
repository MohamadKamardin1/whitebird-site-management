"""Centralized object-level permission policies for the site domain.

Every view/read/write decision in the site module funnels through these
predicates. Routers and services call them; they never re-implement the rules.
Denial is expressed two ways:

* predicates return ``False`` (used by routers for list/visibility logic);
* :func:`ensure` raises :class:`ForbiddenActionError` (used by services before
  mutating state).
"""

from __future__ import annotations

from apps.accounts.models import RoleCode, User
from apps.accounts.permissions import management_required, user_can_manage_site
from apps.core.errors import ForbiddenActionError

from .models import (
    AssistantGeneralSummaryReport,
    Cleaner,
    CleanerSiteAssignment,
    DailySiteReport,
    GeneralManagementReport,
    Inspection,
    Issue,
    Job,
    Site,
    SiteStore,
    Zone,
    ZoneSummaryReport,
)
from .scoping import assigned_zone_ids, site_in_user_scope, visible_sites, visible_zones

REVIEWER_ROLES = {
    RoleCode.GENERAL_SUPERVISOR,
    RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
    RoleCode.ZONE_SUPERVISOR,
}
SENIOR_ROLES = {RoleCode.GENERAL_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}


def _is_reviewer(user: User) -> bool:
    return user.is_system_admin or user.role in REVIEWER_ROLES


def _is_senior(user: User) -> bool:
    return user.is_system_admin or user.role in SENIOR_ROLES


def _manage_site(user: User, site_id: int) -> bool:
    return user.is_system_admin or user_can_manage_site(user, site_id)


# --------------------------------------------------------------------------- #
# Zones & sites
# --------------------------------------------------------------------------- #


def can_view_zone(user: User, zone: Zone) -> bool:
    return visible_zones(user).filter(pk=zone.pk).exists()


def can_view_site(user: User, site: Site) -> bool:
    return site_in_user_scope(user, site.pk)


def can_edit_site(user: User, site: Site) -> bool:
    return _manage_site(user, site.pk)


# --------------------------------------------------------------------------- #
# Cleaners
# --------------------------------------------------------------------------- #


def can_view_cleaner(user: User, cleaner: Cleaner) -> bool:
    """Read access: management roles may view cleaners in their scope.

    PII masking is applied separately at serialization time.
    """
    if not (management_required(user) or user.is_management_viewer):
        return False
    if user.is_system_admin or user.role in {RoleCode.GENERAL_SUPERVISOR, RoleCode.MANAGEMENT_VIEWER}:
        return True
    return cleaner.site_assignments.filter(site__in=visible_sites(user)).exists()


def can_edit_cleaner(user: User, cleaner: Cleaner) -> bool:
    if user.is_system_admin or user.role == RoleCode.GENERAL_SUPERVISOR:
        return True
    if user.is_management_viewer:
        return False
    from .scoping import supervised_sites

    return cleaner.site_assignments.filter(site__in=supervised_sites(user)).exists()


# --------------------------------------------------------------------------- #
# Assignments
# --------------------------------------------------------------------------- #


def can_view_assignment(user: User, assignment: CleanerSiteAssignment) -> bool:
    if user.is_system_admin:
        return True
    return site_in_user_scope(user, assignment.site_id)


def can_edit_assignment(user: User, assignment: CleanerSiteAssignment) -> bool:
    return _manage_site(user, assignment.site_id)


# --------------------------------------------------------------------------- #
# Attendance
# --------------------------------------------------------------------------- #


def can_record_attendance(user: User, site: Site, date: object) -> bool:
    return _manage_site(user, site.pk)


def can_review_attendance(user: User, site: Site) -> bool:
    return _is_reviewer(user) and site_in_user_scope(user, site.pk)


# --------------------------------------------------------------------------- #
# Stores
# --------------------------------------------------------------------------- #


def can_manage_store(user: User, store: SiteStore) -> bool:
    return _manage_site(user, store.site_id)


# --------------------------------------------------------------------------- #
# Inspections
# --------------------------------------------------------------------------- #


def can_view_inspection(user: User, inspection: Inspection) -> bool:
    return site_in_user_scope(user, inspection.site_id)


def can_create_inspection(user: User, site: Site) -> bool:
    return _manage_site(user, site.pk)


def can_review_inspection(user: User, inspection: Inspection) -> bool:
    return _is_reviewer(user) and site_in_user_scope(user, inspection.site_id)


# --------------------------------------------------------------------------- #
# Issues & jobs
# --------------------------------------------------------------------------- #


def can_view_issue(user: User, issue: Issue) -> bool:
    return site_in_user_scope(user, issue.site_id)


def can_edit_issue(user: User, issue: Issue) -> bool:
    return _manage_site(user, issue.site_id)


def can_assign_job(user: User, job: Job) -> bool:
    return user.has_perm("accounts.assign_job") and _manage_site(user, job.site_id)


def can_verify_job(user: User, job: Job) -> bool:
    return user.has_perm("accounts.verify_job") and _manage_site(user, job.site_id)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #


def can_submit_site_report(user: User, report: DailySiteReport) -> bool:
    return _manage_site(user, report.site_id)


def can_review_site_report(user: User, report: DailySiteReport) -> bool:
    return _is_reviewer(user) and site_in_user_scope(user, report.site_id)


def _can_zone_review(user: User, zone_id: int) -> bool:
    if not _is_reviewer(user):
        return False
    if user.is_system_admin or user.role in {RoleCode.GENERAL_SUPERVISOR, RoleCode.MANAGEMENT_VIEWER}:
        return True
    if user.role == RoleCode.ASSISTANT_GENERAL_SUPERVISOR and not assigned_zone_ids(user):
        return True
    return zone_id in assigned_zone_ids(user)


def can_review_zone_report(user: User, report: ZoneSummaryReport) -> bool:
    return _can_zone_review(user, report.zone_id)


def can_review_assistant_report(user: User, report: AssistantGeneralSummaryReport) -> bool:
    return _is_senior(user)


def can_submit_general_report(user: User, report: GeneralManagementReport) -> bool:
    return user.is_system_admin or user.role == RoleCode.GENERAL_SUPERVISOR


def can_view_management_report(user: User, report: GeneralManagementReport) -> bool:
    return management_required(user) or user.is_management_viewer


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def can_export_data(user: User, resource: str) -> bool:
    return user.has_perm("accounts.export_site_management_data")


# --------------------------------------------------------------------------- #
# Service guard
# --------------------------------------------------------------------------- #


def ensure(user: User, predicate: bool, message: str = "You are not permitted to perform this action.") -> None:
    """Raise ``ForbiddenActionError`` unless ``predicate`` holds for ``user``."""
    if not predicate:
        raise ForbiddenActionError(message)
