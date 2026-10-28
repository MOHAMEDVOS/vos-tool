# Plan: Confirm TL Actions in Podio

## Goal

Show a green confirmation only after the matching action is found in the Podio TL Actions app. Google Form submission remains manual and is outside this confirmation.

## Chosen approach

Use Podio's server-side OAuth flow with read-only access to the TL Actions app. Store OAuth state and encrypted refresh/access tokens in the existing `app_settings` table. After VOS prepares the forms, poll Podio for a matching action by team leader, agent, and generated action details. A Podio match changes the card to confirmed; without a match it remains pending and can be reopened.

## Files

- `backend/services/podio_integration.py`: OAuth, encrypted token handling, and matching-item lookup.
- `backend/api/tl_actions.py`: owner-only Podio connect/status endpoints and action confirmation endpoint.
- `webapp/src/api/tlActions.ts`: API calls and status types.
- `webapp/src/pages/TlActionsPage.tsx`: connect UI, Podio polling, and pending/confirmed card states.
- `docs/TL_ACTIONS_SUBMISSION_SETUP.md`: required Railway variables and setup steps.

## Verification

Build the frontend, compile changed Python modules, and run `git diff --check`. Live confirmation requires the Podio API key, an owner authorization grant, and a real submitted item; do not submit a fake production action to test it.
