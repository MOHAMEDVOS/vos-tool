# TL Actions Podio Confirmation Investigation

## Problem

A team-leader action appears in Podio after submission, but its VOS card stays at “Waiting for Podio” or “Not confirmed in Podio.” The provided example is the customized late-hours action form for Marwan Ibrahim Gomaa Mahmoud Hassan, submitted by Marwa Mohamed Kamal Abd-Elatif on October 28, 2026.

## Findings

VOS does not search for the original action form text. `find_submitted_action()` rebuilds the customized Podio report with `_full_action_text()` and compares it to the text returned for the Podio field labeled “Details about incident.” The comparison is exact after whitespace and HTML normalization. Any omitted, moved, or edited line means no match.

The form prefill puts the generated report into the “Details about incident” textarea. The generated report includes the team leader, agent, customized issue type, incident narrative, date, and, when present in the source row, `Reported by TL`. It also appends `Action Given: 2$`. The screenshot initially appeared to show the textarea ending at the date, but the user clarified that the remaining lines are below the visible portion after scrolling. Therefore, the screenshot does not establish that the submitted report is missing those lines.

There is a second failure path: Podio lookup is limited to items created from two minutes before through 30 minutes after the first time the user opened the forms. Clicking “Reopen forms” does not refresh the saved start time; `saveStartedStatus()` keeps the previous timestamp. A later resubmission can therefore be outside the lookup window forever.

## Likely cause for this example

The user confirms the full customized action text is in the Podio field, so the screenshot-based missing-lines hypothesis is withdrawn. A concrete remaining defect is the time window: opening the action form stores a local timestamp, and reopening the forms does not refresh it. Podio lookup only accepts an item created up to 30 minutes after that saved timestamp. If the user submits after that window, or retries later via “Reopen forms,” VOS will not confirm it. Exact-text mismatch or Podio field/API shape remain possible but are not confirmed without inspecting the actual item returned by Podio.

## Implemented behavior

VOS records the start time after opening the forms, waits 30 seconds before its first Podio lookup, then retries every 15 seconds. A successful lookup that finds no match is shown as “Not found in Podio yet”; retries continue until a match is found. Reopening the forms resets the lookup start time and the waiting state. The bounded created-time lookup remains in place to avoid matching an unrelated older action.

## Evidence locations

- `backend/services/podio_integration.py`: exact incident-field comparison and the `started_after` lookup window.
- `backend/services/tl_actions_submission.py`: customized report construction and Podio prefill fields.
- `webapp/src/pages/TlActionsPage.tsx`: retry timestamp storage and the “Reopen forms” flow.
- `docs/TL_ACTIONS_SUBMISSION_SETUP.md`: documented exact-text and time-window requirements.
