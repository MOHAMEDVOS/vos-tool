# Plan: TL Actions submission tracking

## Goal

Show each team leader's count of Actions-sheet records missing from Payroll for the exact Start date and End date selected on the page.

## Approach

Use the existing date range and reconciliation results. Include the parsed team-leader name on each missing action and show a ranked horizontal bar chart for the whole selected date range. Do not introduce automatic week or month buckets. Keep the existing last-7-days default so the user can set any custom range.

Use one date-range control styled after the supplied reference: quick presets, a two-month calendar, and two-click custom range selection. The selected dates remain the sole filter range.

## Files

- `backend/services/tl_actions_reconciliation.py`: include the team leader with each missing row.
- `webapp/src/api/tlActions.ts`: type the returned team-leader field.
- `webapp/src/pages/TlActionsPage.tsx`: add a date-range leaderboard with per-leader counts.
- `docs/TL_ACTIONS_RECONCILIATION.md`: explain that the selected date range controls the complete aggregation window.

## Verification

Check Python syntax and diff whitespace. Do not submit forms or change Payroll/Podio data.

## Counting rule

Count only actions that appear in the Actions sheet but have no exact matching Payroll action in the selected date range. Excluded verbal-only actions remain excluded.
