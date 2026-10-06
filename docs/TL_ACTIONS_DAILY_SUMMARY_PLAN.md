# Plan: TL Actions Summary Cards

## Problem

The TL Actions page lists mismatches but does not summarize the selected date range. Owners and admins need a quick count of logged, verbal, and waived actions, plus a clear comparison of HR submissions expected versus found.

## Chosen approach

Add four compact summary cards above the reconciliation results. The existing Actions sheet and waiver sheet determine action categories. Only non-verbal, non-waived actions count as expected HR submissions. The current exact-detail Payroll matching determines how many expected submissions were found.

## Files

- `backend/services/tl_actions_reconciliation.py`: classify all dated sheet actions and return summary counts while preserving existing missing-action behavior.
- `webapp/src/api/tlActions.ts`: add summary fields to the response type.
- `webapp/src/pages/TlActionsPage.tsx`: render the four cards for the selected date range.

## Success

After reconciliation, the cards show total logged actions, verbal actions, waived actions, and `found / expected` HR actions with a match or missing status. The existing missing-action list and submission flow continue to use only actions required in Payroll.
