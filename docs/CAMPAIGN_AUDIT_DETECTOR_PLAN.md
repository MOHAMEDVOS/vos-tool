# Plan: Campaign Lite Audit — auto reachability summary

> Final scope. When a **Campaign Lite Audit** runs, also scan the whole day's call-log for that
> campaign and save a simple **reachability summary** (low vs good engagement). Shown per-campaign
> in the Campaign Audit dashboard.

## Decisions (locked)

| # | Decision |
|---|----------|
| Trigger | **No button.** Runs automatically inside **Lite Audit only** (Campaign tab), after collect + analyze. Heavy/Agent untouched. |
| Scope | **One campaign** — the one being audited. |
| Output | **Reachability summary only** — low vs good engagement with per-disposition counts + a verdict sentence. No quality flags, no distribution chart. |
| Storage | **New table** `campaign_disposition_scans` (`CREATE TABLE IF NOT EXISTS`). |
| Display | Simple panel above the existing campaign table (see `docs/campaign_disposition_panel_mockup.html`). |

## The output (exactly this)

> ⚠️ **This campaign shows low reachability.**
>
> **Low Engagement (4,566):** Dead Calls 918 · Unknown 1,879 · Voicemails 1,769
> **Good Engagement (3,932):** Decision Makers 3,198 · Wrong Numbers 734
>
> *Low engagement exceeds good engagement — action may be needed to improve contact rates.*

Flips to ✅ **good reachability** when `good >= low`.

## The logic (dead simple — no audio, no call length)

Count calls per disposition for the campaign, then:

```
LOW  = Dead Call + Unknown + Voicemail
GOOD = Decision Maker-NYI + Wrong Number
verdict = LOW if LOW > GOOD else GOOD
```

Disposition grouping (case-insensitive, ReadyMode labels):
- **low:** `Dead Call`, `Unknown`, `Voicemail`
- **good:** `Wrong Number`, and any label starting with `Decision Maker` (so `Decision Maker - NYI`
  counts; `DNC - Decision Maker` does **not**).
- everything else (DNC, Influencer, Sold, …) is ignored — matches the Audit-Detector tool.

## Data pull (lighter than before)

We only need the **Disposition** column, scoped to the campaign:
- `export_call_log_csv(fields=[("Log Type","Disposition"),("Current campaign","Campaign")])`
  for the day, then filter rows where `Campaign == campaign_name` and count `Disposition`.
- No recording length, phone, or agent needed for this feature.

## Flow

```
Campaign tab → set URL + Campaign + date → click LITE AUDIT
  ├─ (existing) download sample → batch_analyze_folder_lite → save_campaign_audit_results   [unchanged]
  └─ (NEW, lite + campaign only, after the above, try/except-isolated)
        fresh ReadyMode login → export disposition CSV (whole day)
        → filter to this campaign → count → low/good groups + verdict
        → save_campaign_disposition_scan(...)
                                                          ↓
Campaign Audit dashboard → pick campaign → reachability panel (above existing table)
```

## Files to change

| File | Change |
|------|--------|
| `lib/campaign_audit_detector.py` | **new** — `summarize_reachability(rows, campaign)` → `{verdict, low_total, good_total, low_counts, good_counts, total}` (pure/stdlib) |
| `tests/test_campaign_audit_detector.py` | **new** — low>good, good>=low, label-grouping (DNC excluded), empty |
| `backend/core/database.py` | `CREATE TABLE IF NOT EXISTS campaign_disposition_scans` at init |
| `lib/dashboard_manager.py` | **new methods** `save_campaign_disposition_scan()` + `get_campaign_disposition_scan()` (additive) |
| `backend/api/readymode.py` | `_run_campaign_disposition_scan()` + one guarded call in the lite+campaign branch |
| `backend/api/dashboard.py` | `GET /campaign-disposition?campaign=&start_date=&end_date=` |
| `webapp/src/api/dashboard.ts` + `hooks/useDashboard.ts` | `useCampaignDisposition` hook |
| `webapp/src/features/dashboard/CampaignAuditDashboard.tsx` | reachability panel |
| `webapp/src/types/api.ts` | `ReachabilityScan` type |

## New table

```sql
CREATE TABLE IF NOT EXISTS campaign_disposition_scans (
  id            SERIAL PRIMARY KEY,
  campaign_name TEXT NOT NULL,
  username      TEXT NOT NULL,
  scan_date     DATE NOT NULL,
  timestamp     TEXT NOT NULL,
  total_calls   INTEGER,
  reachability  TEXT,        -- 'GOOD' | 'LOW'
  low_total     INTEGER,
  good_total    INTEGER,
  low_counts    JSONB,       -- { "Dead Call":918, "Unknown":1879, "Voicemail":1769 }
  good_counts   JSONB,       -- { "Decision Maker - NYI":3198, "Wrong Number":734 }
  created_at    TIMESTAMP DEFAULT now()
);
```

## Testing plan

1. Unit-test `summarize_reachability` on a fixed row list: low>good, good>=low, DNC excluded from
   good, unknown labels ignored, empty input.
2. Live: run a Campaign Lite Audit today; confirm the panel appears with sane totals vs ReadyMode.
3. Confirm a scan failure (bad creds) does NOT break the lite-audit save.

## Risks & rollback

- **Low.** Additive; Heavy/Agent untouched; scan is try/except-isolated.
- Adds ~1 login + 1 CSV pull (~1–3s) after the real lite-audit work.
- Touches `dashboard_manager.py` + `readymode.py` (critical files) — additively only.
- Rollback: remove the scan call + new methods/table; lib + test files are inert.
