# Site Supervisor Cleanliness Report PDF Findings

Source: `WBCSITESUPERVISORRIPOTIYAUSAFI22.pdf`

## Page 1: Daily/weekly report header and shift declaration

The report is titled **REPOTI YA USAFI SIKU & WIKI** (daily and weekly cleanliness report) and begins with a **Taarifa za Jumla** general-information section. It captures the date, shift selection, site name, and supervisor name. The shift options are **Asubuhi** (morning), **Mchana** (afternoon), and **Usiku** (night).

The report includes a notice that the report is completed for the selected shift or night shift and submitted to the office every morning. It then asks the supervisor to identify the main areas being cleaned. The visible area choices are **Vyooni** (toilets), **Ofisini** (offices), **Eneo la ndani** (indoor area), **Eneo la nje** (outdoor area), and **Bustani** (garden).

## Page 2: Weekly cleanliness matrix

The page presents a weekly matrix titled **UHAKIKI WA USAFI** (cleanliness verification). Each area has a row group with weekday columns labeled **M, T, W, T, F, S, S**. The UI should preserve this spreadsheet-like orientation but for the site-supervisor daily workflow should focus the active date while showing the weekly context where useful.

### Area group: Toilets (`Vyooni`)

The visible questions are:

1. Floor and wall surfaces have been washed and cleaned.
2. The mirrors have been cleaned.
3. The rubbish bin has been cleaned.
4. The toilet has been washed and cleaned.
5. Soap, brushes, and cleaning tools have been washed and stored properly.
6. Water has been put into the tank for cleaning.
7. Water has been put into the hand-washing container.
8. Towels have been placed.
9. Toilet paper has been placed.

### Area group: Offices (`Ofisini`)

The visible questions are:

1. Floor and wall surfaces have been cleaned.
2. Chairs, tables, and office equipment have been dusted before the office is opened.
3. The rubbish bin has been washed and cleaned.
4. The desk has been arranged and cleaned.
5. Floors, doors, and windows have been cleaned.
6. Tables have been arranged and curtains have been straightened.
7. The ceiling has been wiped and cobwebs removed.
8. Furniture has been arranged.
9. The rubbish bin has been placed.

### Area group: Indoor area (`Eneo la ndani`)

The visible questions are:

1. Floor and wall surfaces have been cleaned.
2. Stairs have been cleaned before opening.
3. The rubbish bin has been cleaned.
4. The entrance has been wiped and cleaned.
5. Floors and doors have been cleaned.
6. Furniture has been arranged and curtains straightened.
7. The ceiling has been wiped and cobwebs removed.
8. The furniture has been arranged.
9. The bin has been placed.
10. Water has been put in the water container and it has been covered.

The PDF uses simple cell-based verification rather than free-form narrative as the primary daily record. The product should therefore support a quick status per question, with exception details available only when a check is not complete.

## Page 3: Outdoor, garden, and store checks

### Area group: Outdoor area (`Eneo la nje`)

The visible questions are:

1. Grass has been cut.
2. Parking/parking area has been cleaned.
3. The fence has been cleaned.
4. The passage/path has been cleaned.
5. All surrounding areas have been cleaned.
6. The area has been watered.
7. The rubbish bin has been wiped and cleaned.

### Area group: Garden (`Bustani`)

The visible questions are:

1. The grass has been cut.
2. The flower beds have been watered.
3. Flowers have been pruned.
4. The area has been collected/cleared.
5. The area has been watered.
6. Safe paths have been created.
7. The garden has been maintained with care.
8. Branches have been cut.
9. Damaged plants have been removed/replaced.

### Store readiness section

The report includes **Usimamizi wa Store na Vitendea Kazi** (store and equipment management). Its visible checks are:

1. The store door is locked and the key has been handed over.
2. The store door is locked and the key has been returned to the store.
3. All equipment is returned to its place and organized.
4. Equipment that has been used is washed and returned to the store.
5. Equipment that has been used is returned to its proper location.
6. Equipment that needs repair has been separated and reported.

## Page 4: Staff performance, comments, and handover

### Staff-performance section

The final matrix is **Maendeleo ya wafanyakazi** (staff performance/progress). Its visible checks are:

1. The worker can perform within the required time.
2. The worker is honest and hardworking.
3. The worker completes tasks before time.
4. The worker is present in all work areas.
5. The worker does not leave the work area without informing the supervisor.
6. The worker follows instructions and performs assigned work.

### Exceptions and comments

The report provides a **Mengineyo / Changamoto zilizojitokeza** section for seven numbered challenges or other observations. The digital workflow should expose this as an optional general comment plus a structured exception row attached to the affected area/question, rather than requiring the supervisor to write everything in one unstructured block.

### Handover

The report ends with **Uthibitisho wa makabidhiano ya shift (handover)** and two supervisor sign-off blocks: Supervisor wa zamu (I) and Supervisor wa zamu (II), each with name, signature, and date. The digital equivalent should capture handover recipient, handover notes, and a timestamped acknowledgement while preserving the audit actor and submission time.

## Product interpretation

The PDF is a weekly paper matrix, but the requested product behavior is a daily site-supervisor workflow. The recommended UI is a spreadsheet-like grid with one row per question, a fixed question column, a status cell for the selected date, and expandable exception fields. The supervisor should not re-enter site, supervisor, or date identity when those values are available from the authenticated session and current assignment.
