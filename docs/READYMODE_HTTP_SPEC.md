# ReadyMode HTTP API contract (reverse-engineered from recon)

Source: live recon `session.har` / `findings.json` captured 2026-06-15 on `resva2.readymode.com`.
**Verdict: pure-HTTP replacement is fully viable. No browser, no CSRF token, no CAPTCHA.**

## 1. Auth / login  ✅ PROVEN over pure HTTP (smoke_test.py)

**Winning recipe — a single POST, no interstitial round-trip needed:**
```
GET  https://<dialer>/                       # seed PHPSESSID + seH cookies
POST https://<dialer>/login_new/?then=/
Content-Type: application/x-www-form-urlencoded
REQUIRED headers (omitting these -> server 500 'cURL error 3: url malformed'):
  Origin: https://<dialer>
  Referer: https://<dialer>/login_new/?then=/
  Sec-Fetch-Site: same-origin   Sec-Fetch-Mode: navigate   Sec-Fetch-User: ?1
  Upgrade-Insecure-Requests: 1   Accept: text/html,...
body:
  login_account        = <READYMODE_USER>
  login_password       = <READYMODE_PASS>
  login_as_admin       = on
  logout_other_sessions= on        # <-- forces takeover; gives clean 302 in one shot
  user_tz              = America/New_York   (any valid tz string)
  autoequals           = WebRTC
  use_phone_module     = auto
  then                 = /
```
- Success = **302 → `/`** and cookies now include **`stationId`** + **`sp`** (in addition to `PHPSESSID`,
  `seH`, `saved_account`). Check for `stationId` as the success marker — `PHPSESSID` alone is NOT enough.
- GOTCHA: without `logout_other_sessions=on` you get the "already logged in" interstitial and the data
  endpoint returns `"Your session has expired"`. Without the browser-like headers, `logout_other_sessions`
  triggers a server-side **500** (the server cURLs the other station; bad/missing Origin → malformed URL).
- The `set_st`/`set_sp` hidden fields in the interstitial come from browser `localStorage` and are NOT
  needed for the HTTP client (empty is fine once the headers above are present).
- Same `Auditing AI` credentials authenticate on multiple dialers (resva2 AND resva6 verified).
- Keep the cookie jar for all subsequent calls.

## 2. Results + filter maps — the ONE endpoint that does everything

```
GET https://<dialer>/CCS Reports/call_log/update?update=1&<report params>
Headers:
  X-Requested-With: XMLHttpRequest
  Accept: application/json, text/javascript, */*; q=0.01
```
Note: the path contains a literal space ("CCS Reports/call_log/update"); URL-encode as `%20`.

### report[...] query params (repeatable keys use `[]`)
| Param | Meaning | Example |
|-------|---------|---------|
| `report[time_from_d]` | start date `MM/DD/YYYY` | `06/15/2026` |
| `report[time_from_dateonly]` | =1 | `1` |
| `report[time_to_d]` | end date `MM/DD/YYYY` | `06/15/2026` |
| `report[time_to_dateonly]` | =1 | `1` |
| `report[restrict_uid]` | **agent id** (0 = all) | `1379` |
| `report[restrict_campaign]` | **campaign id** (0 = all) | `210` |
| `report[restrict_batch]` | 0 | `0` |
| `report[sourceFilter]` | -1 | `-1` |
| `report[durationFilter]` | duration bucket (-1 = any) | `-1` |
| `report[callTypeFilter]` | `_` | `_` |
| `report[types][]` | disposition/type ids (repeated) | see §3 |
| `report[page]` | **0-indexed page** | `0`,`1`,… |

### Response JSON (top-level keys)
- `campaignlist` → `{ "<id>": "Name", ... }`  ⇐ resolve campaign **name → id**
- `userlist` → `{ "x<uid>": "Admin|Name" or "Agents|Name", ... }`  ⇐ resolve agent **name → uid** (strip `x`, take text after `|`)
- `pages` → total page count (e.g. `251`)
- `page` → current page
- `results` → `{ "1": {row}, … "25": {row} }`  (25 rows/page)

### Row object (results[n])
```json
{
  "User": "Ahmed Mohamed Abdelhamid Mahmoud",   // agent name
  "Time": "Jun 15, 4:54PM",                      // call time
  "id": "7164070",
  "Type": "Voicemail",                            // disposition label
  "go": "CCS Profile/Profile=3902435",
  "RecId": "/File types/data/callrec/db/70/57/24/7245770.mp3",  // mp3 path
  "call_type": "Manual",
  "Calltime": "<30s",                             // duration label
  "File": "Lily Chao Tampa (813) 933-3426"        // name + phone
}
```
Maps 1:1 to the current scrape: `User`→agent, `Time`→time, `Type`→type, `File`→phone(regex), `RecId`→mp3 href.

## 3. Disposition label → `report[types][]` id  (from the call_log page `<select name="report[types][]">`)
```
144 Influencer        147 Unknown           139 Voicemail        140 Dead Call
145 DNC - Unknown     143 Agent             96  Spanish Speaker  148 Prank Voicemail
146 DNC - Decision Maker  138 Decision Maker - Lead   1 Callback   151 Sold
                       2  Decision Maker - NYI  5 Wrong Number    149 Listed Property
```
- A base type **`6`** is always sent in addition to the selected ids (observed: selecting "Unknown" → `types[]=6&types[]=147`).
- **No disposition filter:** send the full default set captured unfiltered:
  `6,144,145,146,147,143,138,139,96,1,5,2,140,148,151,149,(User,%),(Queue,1),(Queue,12),(Queue,13),(Queue,14),(Queue,15)`.
- **With disposition filter:** send `6` + the id(s) for each requested disposition.
- User's "Unknown/ dead call" = ids **147 + 140**.

## 4. Download a recording
```
GET https://<dialer><RecId>?force_dl=1     (cookies from login)
→ 200, Content-Type: application/octet-stream  (mp3 bytes)
```
Already how production downloads today (cookie-based `requests`), so this half is unchanged.

## 5. Duration (`report[durationFilter]`)
Not re-captured with a value this run (was `-1`). Current production also enforces duration via a
**post-download pydub check** (`download_single_file`), which is authoritative — so HTTP parity is kept by
reusing that check. Mapping the dropdown buckets to `durationFilter` values is a minor follow-up if we want
server-side pre-filtering too.

## 6. Notes for the Python client
- One `httpx`/`requests` session, persistent cookie jar.
- Resolve name→id from `campaignlist`/`userlist` using the SAME exact / `name.`-prefix matching the current
  JS uses ([download_readymode_calls.py:613](../../automation/download_readymode_calls.py#L613)).
- Page loop: read `pages`, request `page=0..N` until `max_samples` collected.
- Per-dialer login (each dialer is a separate tenant; campaign "Vida" lives on a different dialer than agent "Omar").
```
