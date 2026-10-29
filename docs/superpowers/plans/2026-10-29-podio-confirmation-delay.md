# Plan: Delay the First Podio Confirmation Check

## Problem

VOS checks Podio immediately after the forms open, before the user has had time to submit and Podio to save the action. The card also keeps saying “Waiting for Podio” after a successful check found no match.

## Solution

Start the check clock when the forms are opened. Wait 30 seconds before the first Podio lookup, then retry every 15 seconds. Show “Not found yet” after a successful lookup misses, and keep checking until confirmed. Reopening the forms starts a fresh clock and lookup window.

## Files

- `webapp/src/pages/TlActionsPage.tsx`: delay and retry checks, persist whether a lookup has missed, and show the user the result.
- `docs/investigations/TL_ACTIONS_PODIO_CONFIRMATION.md`: update the investigation with the implemented behavior.

## Verification

Review the diff for the 30-second initial delay, 15-second retries, visible unmatched state, and fresh timestamp on reopen. No action will be submitted to production during verification.
