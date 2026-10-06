# Plan: TL Actions Summary Cards

## Problem

The TL Actions page lists mismatches but does not summarize the selected date range. Owners and admins need a quick count of logged, verbal, and waived actions, plus a clear comparison of HR submissions expected versus found.

## Chosen approach

Add four compact summary cards above the reconciliation results. The selected date range filters Actions sheet rows only. The Payroll lookup independently checks the last 14 calendar days, including today, so a recent late submission can still match. The existing Actions sheet and waiver sheet determine action categories. Only non-verbal, non-waived actions count as expected HR submissions. Exact-detail Payroll matching determines how many expected submissions were found.

## Files

- `backend/services/tl_actions_reconciliation.py`: classify all dated sheet actions, fetch Payroll for the independent two-week window, and return summary counts and both date ranges.
- `webapp/src/api/tlActions.ts`: include Payroll lookup dates in the response type.
- `webapp/src/pages/TlActionsPage.tsx`: render the four cards and show which Payroll date range was checked.

## Success

After reconciliation, the cards show total logged actions, verbal actions, waived actions, and `found / expected` HR actions with a match or missing status. The page states the Payroll lookup dates. The existing missing-action list and submission flow continue to use only actions required in Payroll, with the sheet range unchanged.
