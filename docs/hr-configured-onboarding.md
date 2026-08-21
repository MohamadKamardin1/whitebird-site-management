# Configured HR Cleaner Onboarding

## Individual registration

HR now selects both the **onboarding status** and the **assigned site** before registering one cleaner. The registration form records identity, contact, emergency-contact, status, and destination-site information in one audited action.

| HR selection | Result |
|---|---|
| **Trainee** | Creates a draft site assignment and starts a 90-day trainee programme at the selected site. The trainee appears in that site's Training Management workspace immediately. |
| **Active** | Creates an active site assignment at the selected site for an existing worker who is already ready for operational deployment. |

Only HR and System Administrators can register cleaners. The selected site must be active.

## Bulk workbook onboarding

Before downloading a workbook, HR chooses one onboarding status and one destination site in the onboarding workspace. The generated workbook includes an **Onboarding configuration** sheet displaying these choices and a Cleaners sheet containing only cleaner identity and contact columns.

The workbook deliberately has no editable status or site columns. Preview and import use the status and site selected in the HR interface, not spreadsheet-supplied values. This keeps one upload cohort consistent and prevents a modified workbook from assigning cleaners to an unintended site or lifecycle status.

Each upload remains preview-first. Rows with invalid identity data, invalid dates, invalid dropdown values, or duplicate identities are rejected before any cleaner, assignment, or trainee-programme record is created.

## HR People Registry and protected data

The HR People Registry is the HR management workspace for cleaner records. It shows each person's **current assigned site** and, for trainees, their **training site**. HR can update permitted cleaner profile fields, deactivate a cleaner without deleting operational history, and transfer a cleaner or trainee with an effective date and required reason.

Transfers retain history instead of overwriting it. The service ends the current active or draft assignment, creates the destination assignment, and—when the person is in training—moves the active trainee programme to the same site. The receiving site's Training Management workspace therefore becomes the authoritative place for that trainee's daily assessments, while earlier assignments and evaluations remain auditable.

HR can select multiple cleaners or trainees in the registry and transfer them as one atomic, audited batch. The system validates every selected person before changing any record; if any selected person cannot move, the batch is not partially applied. The batch audit records the actor, effective date, transfer reason, origin, destination, resulting assignment, and trainee-programme linkage for every person.

Cleaner ID numbers and phone numbers remain masked in the ordinary registry list. HR can use the explicit **Reveal details** control for a specific cleaner when the information is required for an HR review. Each reveal is authorized by the backend and recorded in the audit trail. Customized template downloads also use the authenticated application request path, so downloading no longer bypasses the HR session token.
