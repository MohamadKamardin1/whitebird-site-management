# Timetable Core Flow

The platform already had the audited `SupervisorTimetableEntry` model introduced by migration `0024`. It represents one **supervisor**, one **zone**, one **site**, and one recurring weekly shift. The timetable wizard deliberately reuses this record rather than adding a second M2M timetable model.

The administrator chooses a scope role, the specific active supervisor account(s), selected zones, selected sites, a title, effective date range, weekly work/off days, shift, and notes. The wizard supports `zone_supervisor` and `assistant_general_supervisor` scopes. It no longer auto-resolves every supervisor in a zone: each selected supervisor is explicitly recorded in the batch payload.

For Zone Supervisors, at least one selected site is required and an entry is created only where that direct supervisor has a current active assignment to the site’s zone. This allows different Zone Supervisors to have distinct timetables for the same site. For Assistant General Supervisors, the selected zones may span multiple current Assistant General Supervisor assignments. Site selection is optional: when no sites are selected, every active site in the selected zones is included; otherwise only the selected sites are included. An `all_zones` Assistant General Supervisor assignment covers all selected zones.

The backend rejects every site that is not in a submitted zone, selected users whose role does not match the chosen scope, unavailable users, and supervisors without current coverage of any selected zone. It still applies the existing `site_in_user_scope` validation for every retained entry. Batch creation is atomic: no partial timetable is kept if any entry is invalid.

`SupervisorShiftSlot` now supports `asubuhi`, `mchana`, and `full_day`. Existing checklist submissions retain the recorded shift value. Assistant General Supervisor assignments support multiple active individual zones, with database and model safeguards that prevent duplicate zone assignments or mixing an all-zones assignment with individual zones.

The administrator list exposes all timetable records, including inactive entries. System administrators can activate, deactivate, and safely delete an entry. When checklist submissions depend on a timetable, deletion is converted into an audited deactivation so historical evidence remains intact. Entries with no dependent checklist submission are hard-deleted with an audit record.

Personal schedulers use `GET /timetables?scope_role=zone_supervisor` or `GET /timetables?scope_role=assistant_general_supervisor`. Each route is server-scoped to the authenticated user, their current visible zones, and their current visible sites. The UI is read-only; the existing `/supervision/roster` page remains the operational checklist workspace. The scheduler and administrator interface render labels, roles, shifts, statuses, empty states, lifecycle actions, and event details through the Kiswahili/English language switch.

## Manual UI QA

Before release, verify the following in the administrator wizard:

1. Select one Zone Supervisor directly, then confirm that another active Zone Supervisor assigned to the same zone is not added to the review or batch result unless selected.
2. Select two zones, choose sites from both, then remove one zone. Its previously selected sites must be removed automatically and must not appear in the review step.
3. Select the Assistant General Supervisor scope, assign one user with two active zone assignments, leave sites unselected, and confirm that all active sites in the selected zones appear in the retained entry result.
4. Select the Full day shift, save the batch, and confirm that its scheduler card is blue and says **Siku nzima** in Kiswahili and **Full day** in English.
5. Attempt to continue without a supervisor, zone, required Zone Supervisor site, timetable title, or work day. The relevant step must keep the administrator on the guided form.
6. Submit a deliberately invalid site/zone pairing or unauthorised supervisor/zone pairing through the API or a stale browser state. The page must show the server validation message inline and must not claim that a timetable was saved.
7. Create a checklist submission for an entry, use the administrator delete control, and confirm that the entry stays visible as inactive. Delete an unused entry and confirm that it disappears.
8. Sign in as both a Zone Supervisor and an Assistant General Supervisor and use Day, Week, and Month views. Confirm that only the signed-in supervisor’s active entries and assigned sites appear, and that the page has no create, edit, or delete controls.
