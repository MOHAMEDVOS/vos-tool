# Plan: Hide waived TL Actions

## Problem

TL Actions currently excludes verbal actions, but it does not consult the appeal response sheet for actions that were waived. Waived items should be omitted from the app and its action count so team leaders do not prepare them for Payroll submission.

## Findings

- The response workbook is `Auditing appeals to Reply`, tab `Audit Reply`.
- `Please Insert action temp from the reporting group` contains the full action template.
- `Result` contains `Waived` or `Not Waived`.
- The current Actions source stores the comparable full action text in `Details`.
- Reconciliation and submission preparation both use `_sheet_rows`, so filtering there applies to both flows.

## Options considered

1. Read the waiver sheet during `_sheet_rows` and exclude rows whose normalized `Details` match a row marked `Waived`. Low effort and follows the existing Sheets CSV / service-account fallback pattern.
2. Read the waiver sheet through Google Sheets API on every request. More authentication plumbing despite the sheet already being link-readable.
3. Keep waived templates in a backend-maintained list. This duplicates the sheet and can go stale.

## Chosen solution

Use option 1. Normalize templates with `normalize_details`, treat only a status equal to `Waived` ignoring case and surrounding whitespace as waived, and leave `Not Waived` eligible. Keep existing verbal filtering. Configure the waiver spreadsheet ID and tab with environment overrides and safe defaults.

## Files

- `backend/services/tl_actions_reconciliation.py`: load waived templates and filter matching Actions rows.
- `.env.example`: document optional waiver sheet settings.
- `docs/TL_ACTIONS_RECONCILIATION.md`: describe the new exclusion rule.

## Verification

Review the final diff and run whitespace checks. Do not change Google Sheets data or Payroll records.

## Risks

The two sheets must contain the same action template text after the existing HTML and whitespace cleanup. If Google cannot read the waiver sheet publicly, the configured service account must have viewer access.
