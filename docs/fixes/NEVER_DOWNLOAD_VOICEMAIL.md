# Plan: Voicemail is NEVER downloaded

**Date:** 2026-08-07 · **Requested by:** Mohamed
**Rule:** *Under no condition may a Voicemail call be selected/downloaded by the automation.*

---

## Problem

Voicemail calls can reach the download queue through **three** doors today
(see [DISPOSITION_FILTER_FLOW.md](../investigations/DISPOSITION_FILTER_FLOW.md)):

1. **Empty disposition selection** → `all_type_ids(dialer_map)` = every id on the dialer,
   Voicemail included. This is the confirmed resva5 leak.
2. **Wrong ids** → when `init_call_log()` fails, the static resva2-captured map is used;
   an id we believe is "Wrong Number" may be "Voicemail" on that dialer.
3. **Loose substring match** in `disposition_type_ids()` resolving a requested label onto a
   voicemail id.

A whitelist filter alone can never close door 2 — if the ids are wrong, no id-level filter helps.

## Options considered

| # | Approach | Effort | Guarantee | Verdict |
|---|---|---|---|---|
| A | Drop "Voicemail" from the frontend list | L | none (it's already absent; leak is server-side) | ✗ |
| B | Strip voicemail ids in `all_type_ids` / `disposition_type_ids` | L | closes doors 1 & 3 only | partial |
| C | Skip rows whose actual `Type` is voicemail, before queuing the mp3 | L | closes **all** doors — uses the row's own label, not an id | ✓ |
| D | Hard-fail the run when the live map can't load | M | closes doors, but breaks audits on a transient scrape failure | ✗ |

**Chosen: B + C.** B keeps the wire request honest (never *asks* for voicemail); C is the
belt-and-braces net that holds even when id resolution is wrong, because it reads each row's
own `Type` string returned by ReadyMode.

## Scope decisions

- **"Voicemail" = any label containing `voicemail`, or with `vm` as a standalone word** —
  covers `Voicemail`, `Prank Voicemail`, and tenant renames like `VM - No Answer`, without
  false-matching a label that merely contains those two letters.
- **Download path only.** The analytics CSV paths (`_run_campaign_disposition_scan`
  reachability, `_run_agent_call_length_scan` long-VM detector) *must* keep counting voicemail
  or their stats break. They export CSV, never audio — so `export_call_log_csv` opts out of the
  block explicitly.

## Files changed

| File | Change |
|---|---|
| `automation/readymode_http.py` | `BLOCKED_DISPOSITION_SUBSTRINGS` / `_TOKENS` + `is_blocked_disposition()` + `blocked_type_ids()`; `disposition_type_ids()` and `all_type_ids()` gain `block_voicemail=True` (the substring fallback also refuses to land on a blocked id) |
| `automation/readymode_http.py` | `export_call_log_csv()` takes `block_voicemail=False` (analytics needs VM rows) |
| `automation/download_readymode_calls.py` | types resolved **before** the probe call and passed to it, so no request from this path ever asks for voicemail; falls back to `all_type_ids(DISPOSITION_TYPE_IDS)` instead of `None` when the live map is missing; row-level guard skips + counts any row whose `Type` is voicemail |
| `webapp/src/api/readymode.ts` | comment: Voicemail is intentionally absent and server-blocked |

## Verified (2026-08-07, against resva5's real id map)

| Case | Result |
|---|---|
| `["Voicemail"]` requested | `[6]` — id 63 never sent |
| `["Unknown","Voicemail","Wrong Number"]` | `[6, 89, 5]` |
| `["Prank Voicemail"]` | `[6]` |
| empty box → `all_type_ids` | `[6, 42, 85, 84, 89, 90, 86, 5, -1]` — no 63 |
| the 8 UI picks | `[6, 42, 90, 89, 86, 5, 84, 85, -1]` — matches the known-good live run |
| no live map → static set | 139 / 148 (voicemail, prank voicemail) both absent |
| `block_voicemail=False` (analytics) | 63 still present ✅ |
| simulated report returning VM rows anyway | rows skipped, `INFO … skipped N voicemail row(s)` printed |

Still to confirm live: run a lite audit on resva5 with an **empty** disposition box → expect
0 files named `… _ Voicemail.mp3`, and the reachability scan still reporting voicemail counts.

## Risks & rollback

Low. Only narrows what gets downloaded. If a dialer legitimately labels a wanted disposition
with the word "voicemail" it would be skipped — acceptable, that is the rule.
Rollback: revert the two `automation/` files.
