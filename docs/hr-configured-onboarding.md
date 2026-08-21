# Configured HR Cleaner Onboarding

## Individual registration

HR now selects both the **onboarding status** and the **assigned site** before registering one cleaner. The registration form records identity, contact, emergency-contact, status, and destination-site information in one audited action.

| HR selection | Result |
|---|---|
| **Trainee** | Creates a draft site assignment and starts a 90-day trainee programme at the selected site. |
| **Active** | Creates an active site assignment at the selected site for an existing worker who is already ready for operational deployment. |

Only HR and System Administrators can register cleaners. The selected site must be active.

## Bulk workbook onboarding

Before downloading a workbook, HR chooses one onboarding status and one destination site in the onboarding workspace. The generated workbook includes an **Onboarding configuration** sheet displaying these choices and a Cleaners sheet containing only cleaner identity and contact columns.

The workbook deliberately has no editable status or site columns. Preview and import use the status and site selected in the HR interface, not spreadsheet-supplied values. This keeps one upload cohort consistent and prevents a modified workbook from assigning cleaners to an unintended site or lifecycle status.

Each upload remains preview-first. Rows with invalid identity data, invalid dates, invalid dropdown values, or duplicate identities are rejected before any cleaner, assignment, or trainee-programme record is created.

## HR People Registry and protected data

The HR People Registry is the HR management workspace for cleaner records. HR can update permitted cleaner profile fields, deactivate a cleaner without deleting operational history, and transfer a cleaner by ending the current assignment and creating an audited assignment at the selected site.

Cleaner ID numbers and phone numbers remain masked in the ordinary registry list. HR can use the explicit **Reveal details** control for a specific cleaner when the information is required for an HR review. Each reveal is authorized by the backend and recorded in the audit trail. Customized template downloads also use the authenticated application request path, so downloading no longer bypasses the HR session token.
