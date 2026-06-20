# resv5 "Voicemail" disposition bug — Live Diagnosis

**Date:** 2026-06-19
**Symptom:** Running automation on **resva5** with the 8 wanted dispositions
(Spanish Speaker, DNC-Unknown, Unknown, DNC-Decision Maker, Wrong Number,
Decision Maker-NYI, Dead Call, Not logged) returns **Voicemail** calls. Reported
as "only happens with resva5".

**Verdict:** The disposition *filter itself is correct* on resva5. Voicemail only
appears when the **Call Dispositions box is left empty** (no selection), because an
empty box means "download every disposition", and resva5's full set includes
Voicemail (id 63). Proven live below.

---

## How it was tested (live, read-only — downloaded nothing)

Login `UserCreation` on `https://resva5.readymode.com/`, fetch the call-log report
and tally each row's actual `Type` (the disposition that ends up in the filename).

Probes added: `scripts/probe_disposition_map.py`, `scripts/probe_disposition_fetch.py`.

### 1. resva5's IDs are a completely different set from resva2

| label | resva2 id | resva5 id |
|-------|-----------|-----------|
| spanish speaker | 96 | **42** |
| voicemail | 139 | **63** |
| dead call | 140 | **85** |
| decision maker - nyi | 2 | **84** |
| unknown | 147 | **89** |
| dnc - unknown | 145 | **90** |
| dnc - decision maker | 146 | **86** |
| wrong number | 5 | 5 |
| not logged | -1 | -1 |

The static `DISPOSITION_TYPE_IDS` fallback in `readymode_http.py` was captured on
resva2 and is **wrong on resva5** — but the live per-dialer map
(`init_call_log()`) loads fine on resva5 (17 entries), so the app resolves the
right ids.

### 2. The 8 picks, resolved as the app actually sends them → CORRECT

```
types sent: [6, 42, 90, 89, 86, 5, 84, 85, -1]
rows sampled: 100
   42  Decision Maker - NYI
   26  Unknown
   12  Wrong Number
    9  DNC - Decision Maker
    7  Dead Call
    2  DNC - Unknown
    2  Spanish Speaker
```
→ **No voicemail.** The filter works on resva5 when the 8 are selected.

### 3. Empty selection (no dispositions chosen) → VOICEMAIL leaks

An empty box ⇒ backend sends `dispositions = None` ⇒
`_collect_tasks_for_dialer` uses `all_type_ids(dialer_map)` = **every** id
including voicemail (63):

```
types: [6, 1, 5, 7, 42, 63, 84, 85, 86, 87, 88, 89, 90, 91, 92, 94, -1]
rows sampled: 150
   49  Decision Maker - NYI
   31  Unknown
   26  Voicemail   <<< downloaded
   14  Wrong Number
   ...
```
→ **This is the only path that produces Voicemail.**

---

## Root cause

`webapp/src/pages/AuditPage.tsx` initialises `dispositions = []`. Backend
`backend/api/readymode.py` turns an empty list into `None`
(`request.dispositions or None`), and `download_readymode_calls._collect_tasks_for_dialer`
treats "no disposition" as "select all dispositions" — which on resva5 includes
Voicemail.

So: **the 8 dispositions weren't actually sent for that resva5 run** (box left
empty / selection didn't register), so it fell back to "download everything".

### Why it *looked* resva5-specific
- "Voicemail" is **not** in the UI dropdown, so it can't be chosen on purpose —
  it can only arrive via the download-everything fallback.
- resva5's id set is unlike resva2/resva3 (which share many ids), so resva5 is the
  dialer where per-dialer mistakes surface most visibly.

---

## Fix options (not yet implemented — need approval)

1. **UI**: default the disposition box to the 8 standard dispositions instead of
   empty, so a blank run never silently means "everything". (Low)
2. **Backend/automation**: when no disposition is selected, exclude Voicemail /
   Prank Voicemail from the default-all set. (Low)
3. **No code change**: ensure the 8 are actually selected before running — the
   filter itself is correct. (Zero)

> If the 8 *were* selected and Voicemail still appears, the deployed Railway build
> predates commit `1218f4c` (2026-06-16, per-dialer live map). Redeploy the current
> branch — that commit is already in `fix/railway-session-auth`.
