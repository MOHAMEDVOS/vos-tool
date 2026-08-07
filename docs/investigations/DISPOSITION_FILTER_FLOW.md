# ReadyMode Disposition Filter — How Selection Actually Works

**Date:** 2026-08-07 · **Scope:** UI checkbox → `report[types][]` on the wire
**Related:** [RESVA5_VOICEMAIL_DISPOSITION.md](RESVA5_VOICEMAIL_DISPOSITION.md) · `docs/READYMODE_HTTP_SPEC.md §2–3`

> **Update 2026-08-07 — voicemail is now hard-blocked on the download path** (both at id
> resolution and per-row). Sections 3 and 5 below describe the pre-block behaviour; see
> [NEVER_DOWNLOAD_VOICEMAIL.md](../fixes/NEVER_DOWNLOAD_VOICEMAIL.md) for the rule.

---

## 1. End-to-end path

```
AuditPage (MultiSelect, 8 hardcoded labels)
   webapp/src/api/readymode.ts:14  DISPOSITIONS[]
        │  dispositions: string[]   (labels, not ids)
        ▼
POST /api/readymode/download|stream     backend/api/readymode.py:327 / :432
        │  request.dispositions or None
        ▼
download_all_call_recordings(disposition=[...])
        │
        ▼
_collect_tasks_for_dialer()             automation/download_readymode_calls.py:206
        ├─ client.login()
        ├─ dialer_map = client.init_call_log()      ← LIVE per-dialer label→id
        ├─ types = disposition_type_ids(disposition, dialer_map)   [filter set]
        │  else  all_type_ids(dialer_map)                          [no filter]
        ▼
client.fetch_report(types=types, page=N)  → GET /CCS Reports/call_log/update
        report[types][]=6&report[types][]=<id>&…
```

Labels travel as **text** all the way down. Ids are resolved **per dialer, at run time** — never in the frontend, never in the DB.

---

## 2. The three moving pieces

### a) Live per-dialer map — `init_call_log()` (`readymode_http.py:107`)

POSTs `/CCS Reports/call_log` once, regex-scrapes `<select name='report[types][]'>`
and returns `{label.lower(): id}`. Cached on the client instance.

**Why this exists:** disposition ids are **per-dialer tenant config**, not account-wide.
Confirmed live: `96` = "Spanish Speaker" on resva2 but "Decision Maker - NYI" on resva3;
resva5 uses a third set entirely (`42/63/85/84/89/90/86`).

Note ReadyMode's markup uses **single-quoted** attributes — the regex matches `["']` for
exactly this reason.

### b) Label → id resolution — `disposition_type_ids()` (`readymode_http.py:360`)

```python
lookup = dialer_map if dialer_map else DISPOSITION_TYPE_IDS   # live preferred
ids = [BASE_TYPE]                                             # 6, always
for d in dispositions:
    key = normalize(d)                # strip + lower + collapse whitespace
    tid = lookup.get(key)             # 1. exact
    if tid is None:                   # 2. tolerant substring both ways
        for label, v in lookup.items():
            if key in label or label in key: tid = v; break
    if tid is not None: ids.append(tid)
```

- `BASE_TYPE = 6` is a **constant sentinel**, not a disposition — a hidden form field
  present on every dialer, sent on every request.
- Unresolvable label ⇒ **silently dropped** (no id appended, no warning).

### c) No filter selected — `all_type_ids()` (`readymode_http.py:383`)

`[6, *every id in this dialer's map]` = "tick every checkbox". This is why an empty
selection pulls Voicemail/Sold/Callback etc. — the empty box means *all*, not *none*.

---

## 3. Fallback ladder (what happens when things fail)

| Situation | types sent | Risk |
|---|---|---|
| live map OK + dispositions chosen | `[6, …resolved ids]` | ✅ correct |
| live map OK + nothing chosen | `[6, …all ids]` | every disposition downloaded |
| live map **empty** + dispositions chosen | `[6, …static-guess ids]` | ⚠️ ids may belong to other labels on this dialer |
| live map **empty** + nothing chosen | `types=None` → `fetch_report` uses `[6, *DISPOSITION_TYPE_IDS.values()]` (`readymode_http.py:151`) | ⚠️ same, silently |

`init_call_log()` swallows every exception (`except Exception: pass`). The only signal is
one printed line in `_collect_tasks_for_dialer:225` — the audit still runs, with wrong ids.

The static `DISPOSITION_TYPE_IDS` was captured from **resva2 on 2026-06-15** and is known
wrong on resva3/resva5. It is a last resort only.

---

## 4. Two consumers, two ways in

| Path | Dispositions | Where |
|---|---|---|
| **Agent / campaign audit** (mp3 download) | user's MultiSelect picks | `download_readymode_calls.py:247` |
| **Scoring / campaign scan** (CSV export) | hardcoded `SCORING_DISPOSITIONS = ["Wrong Number", "Decision Maker - NYI"]` | `backend/api/scoring.py:49,160,352` |

`export_call_log_csv()` (`readymode_http.py:182`) resolves the same way, then **seeds session
state** with a `fetch_report()` call before POSTing to `ExportMenu/CL.csv` — the CSV export
has no filter params of its own; it inherits whatever the last report call set.

Multi-dialer (`dialer_url_2`) resolves ids **independently per dialer** — correct by design,
since the same label has different ids on each.

---

## 5. Findings worth knowing

1. **Frontend list is hardcoded** (`readymode.ts:14`, 8 labels) and never fetched from the
   dialer. If a dialer renames or adds a disposition, the UI can't offer it, and a renamed
   one stops resolving.
2. **Substring fallback can pick the wrong id.** If exact lookup misses, `"unknown"` matches
   `"dnc - unknown"` on the first dict-order hit. Only fires on an exact miss, but when it
   fires it fails *silently and wrongly*.
3. **Unresolved labels vanish without a trace** — no warning, no count. The run "succeeds"
   with a narrower filter than requested. The printed `types` line at
   `download_readymode_calls.py:249` is the only way to catch it.
4. **Empty selection ≠ no download** — it means all dispositions. Root cause of the resva5
   "voicemail leak" report.
5. `"Not logged"` maps to id `-1` on dialers that expose it (confirmed resva5); it is absent
   from the static fallback map, so it only works while the live map loads.
