# Timetable Core Flow

The platform already had the audited `SupervisorTimetableEntry` model introduced by migration `0024`. It represents one **supervisor**, one **zone**, one **site**, and one recurring weekly shift. The timetable wizard deliberately reuses this record rather than adding a second M2M timetable model.

The administrator chooses the extensible `scope_role` field, selected zones, selected sites, a title, effective date range, weekly work/off days, shift, and notes. For the currently supported `zone_supervisor` scope, the batch API resolves the active Zone Supervisor assignment for each selected site’s zone and creates one audited `SupervisorTimetableEntry` for each supervisor-site pairing.

The backend rejects every site that is not in a submitted zone before creating any entries. It also rejects a selected zone without an active Zone Supervisor and still applies the existing `site_in_user_scope` validation for every retained entry. Batch creation is atomic: no partial timetable is kept if any entry is invalid.

The Zone Supervisor scheduler uses `GET /timetables?scope_role=zone_supervisor`, which is server-scoped to the authenticated user, their currently visible zones, and their currently visible sites. The user interface is read-only; the existing `/supervision/roster` page remains the separate operational checklist workspace.

## Manual UI QA

Before release, verify the following in the administrator wizard:

1. Select two zones, choose sites from both, then remove one zone. Its previously selected sites must be removed automatically and must not appear in the review step.
2. Attempt to continue without a zone, site, timetable title, or work day. The relevant step must keep the administrator on the guided form.
3. Submit a deliberately invalid site/zone pairing through the API or a stale browser state. The page must show the server validation message inline and must not claim that a timetable was saved.
4. Sign in as a Zone Supervisor and use Day, Week, and Month views. Confirm that only that supervisor’s active entries and assigned sites appear, and that the page has no create, edit, or delete controls.
