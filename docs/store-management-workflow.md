# Company Store and Stock Workflow

## Store hierarchy

White Bird inventory is organized as a controlled distribution network. A **Super Store** can distribute to Power Stores or Site Stores. A **Power Store** can distribute to Site Stores. A **Site Store** belongs to one operational site and can optionally receive stock from a Super Store or a Power Store. All store links are validated when they are created or changed, so the hierarchy cannot contain circular or incompatible distribution relationships.

Every store can hold company products. A company product is defined once with its product code, measurement unit, category, and current unit cost. A store item records the local quantity and a unit-cost snapshot, preserving the value of movements over time.

## Inventory evidence

The system records these evidence sources as separate, auditable records:

| Record | Purpose | Inventory effect |
|---|---|---|
| Monthly opening | Captures the opening quantity and value for one store item and calendar month. | Adds the declared opening quantity. |
| Transfer out | Records stock leaving a Super, Power, or Site Store. | Decreases the source-store balance. |
| Transfer in | Records the matching receipt in the destination store. | Increases the destination-store balance. |
| Issued stock | Records consumption or controlled issue at a store. | Decreases the issuing-store balance. |

One inter-store transfer creates both the transfer-out and transfer-in movements under one audited transfer record. Weekly usage analysis aggregates issued quantities and their unit-cost value by store, site, and product.

## Monthly request approval

Site Supervisors prepare item-by-item stock requests for their assigned Site Store. A Site Supervisor can create, edit, or submit a monthly request only through the **17th day** of the month. The backend enforces this deadline; the interface also shows a clear locked-state notice once the window has closed.

| Stage | Responsible role | Required action |
|---|---|---|
| Draft and submitted | Site Supervisor | Records each configured item, quantity remaining, quantity required, and explanatory notes. |
| Zone verified | Zone Supervisor | Physically checks the Site Store and records the verified quantity for each requested item. |
| Assistant approved | Assistant General Supervisor | Reviews verified quantities and approves the final quantity for the request. |
| HR packing | Human Resources | Moves the approved request into the packing queue. |
| Assembled | Human Resources | Records the quantity assembled for each approved line. |
| Completed | System Administrator or Store Manager | Closes the assembled request after the separately audited inventory transfer or handover. |

Closing a request does not silently decrease Site Store inventory. Physical distribution must be recorded through a costed store-to-store transfer so the company can trace item quantity, current value, source, destination, date, and responsible actor.

## Manual quality checks

Administrators should periodically confirm that all Site Stores have a site assignment, every transferable item is connected to the same company product at both endpoints, opening balances are recorded once per month, and completed requests have matching dispatch or transfer evidence. Zone Supervisors should verify only their assigned sites, and Assistant General Supervisors should approve only requests within their assigned zone scope.
