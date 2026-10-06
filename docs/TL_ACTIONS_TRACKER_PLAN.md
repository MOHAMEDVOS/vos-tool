# Plan: Save Missing TL Actions to the Tracker Sheet

## Goal

Give Owners a button in TL Actions to append currently missing actions to the provided Google Sheet with the action date, team leader, and original action details.

## Approach

Use an authenticated Owner-only backend endpoint and the existing Google service-account Sheets client. Validate the tracker headers, compare the three values to existing rows to avoid duplicates, and append only new rows. Keep existing rows untouched. The page reports the number added and any configuration or permission error.

## Files

- `backend/services/tl_actions_tracker.py`: read tracker rows, check headers and duplicates, append new rows.
- `backend/api/tl_actions.py`: validate the request and restrict the write endpoint to Owner/Admin.
- `webapp/src/api/tlActions.ts`: add the tracker append API call and response type.
- `webapp/src/pages/TlActionsPage.tsx`: add the append button and result feedback.

## Success

Only Owners can see or use the button. Clicking it appends the displayed reconciliation's missing actions under existing data, never overwrites old rows, and shows how many were added or already present. Live sheet writes require the backend service account to have Editor access to the tracker.
