# White Bird Cleaners — Remuneration Form Source Extraction

**Source:** `WBC_FOMUYAMISHAHARA.docx.pdf`, page 1. Page 2 is blank.

## Exact Form Heading

`FOMU. TAARIFA ZA WAFANYAKAZI KWA AJILI YA MALIPO(MWEZI)`

The document includes fields for `JINA LA KITUO` and `MWEZI`.

## Exact Table Columns

| Source order | Exact source label | Platform source / workflow rule |
|---:|---|---|
| 1 | `No` | Generated sequential row number. |
| 2 | `JINA(MAJINA MATATU)` | Cleaner full name from the authorized assigned-cleaner record. |
| 3 | `SIKU ALIYOKOSE KANA KAZINI` | Pre-filled monthly absence-day count from attendance records. |
| 4 | `TAREHE ALIYOANZA KAZI(MFANYAKAZI MPYA TU)` | Pre-filled only if the cleaner began work during the selected remuneration month. |
| 5 | `NAMBA YA SIMU YAS/ZANTEL TU` | The Site Supervisor confirms the last approved number by leaving the override blank; a changed number requires a recorded replacement and audit event. |
| 6 | `TAARIFA ZA BANK: PBZ TU / ACCO NO` | The Site Supervisor confirms the last approved PBZ account by leaving the override blank; a changed account requires a recorded replacement and audit event. |
| 7 | `SAHIHI` | Submission attestation captured as authenticated actor, role, timestamp, and immutable monthly snapshot rather than a copied signature image. |

## Monthly Rules from the Business Brief

1. The Site Supervisor may prepare this form only from the **15th through the 25th** of each month in Tanzania local time.
2. The Site Supervisor sees only cleaners actively assigned to the supervisor’s authorized site.
3. Present and absent days are pre-filled from the attendance engine for the selected month. The source form carries the absence column; present days are retained in the platform view for clarity and auditability.
4. A start-work date appears only for a cleaner whose start date falls inside the selected month.
5. A blank phone or PBZ-account override means use the last approved payment contact. A non-blank override creates a proposed update with prior and new masked values, actor, timestamp, month, site, and approval history.
6. The submitted form must preserve a complete immutable monthly snapshot of the pre-filled attendance, payment-contact decision, changes, and authenticated attestation.

## Platform Extension: Verified Payment-Account Holder Name

The platform records the **name registered to the active Yas/Zantel number or PBZ account** when it differs from the cleaner name. The Site Supervisor can leave this field blank when the prior approved payment-holder name remains correct; otherwise, the proposed name is retained with the payment decision, reviewed by HR or a System Administrator, and written to the approved payment profile only after review.
