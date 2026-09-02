"""Pure-HTTP ReadyMode client — replaces the former Playwright/Chromium automation.

Reverse-engineered from a live recon capture; the full contract is documented in
`scratch/readymode-recon/HTTP_SPEC.md`. One authenticated ``requests`` session drives
everything: login -> GET ``/CCS Reports/call_log/update`` (JSON) -> rows -> mp3 download.
No browser, no DOM, no Chromium.

Key facts (see spec for detail):
  * Login = single POST to ``/login_new/?then=/`` with ``logout_other_sessions=on`` and
    browser-like headers (Origin/Referer/Sec-Fetch-*). Success sets the ``stationId`` cookie.
    Without the browser headers the server 500s ("cURL error 3: url malformed").
  * The report endpoint returns JSON with ``campaignlist`` / ``userlist`` (name->id maps),
    ``pages`` (total page count) and ``results`` (25 rows/page). Filters are all query params.
"""

import re
import json
import requests
from html import unescape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class ReadyModeLoginError(Exception):
    """Login / session failure (bad credentials, blocked, or session not established)."""


class ReadyModeNoCallsError(Exception):
    """No matching campaign/agent, or no recordings for the given filters."""


class ReadyModeUserCreateError(Exception):
    """User creation failed (login ID taken, invalid folder, server error, etc.)."""


class ReadyModeUserDeleteError(Exception):
    """User deletion failed (unknown uid, server error, etc.)."""


class ReadyModeAgentActivityError(Exception):
    """Agent activity report couldn't be parsed. Deliberately loud: a silent empty result
    here reads downstream as "nobody is active," which flags every account for deletion."""


# Fallback disposition label -> report[types][] id, captured from ONE dialer (resva2) on
# 2026-06-15. ReadyMode disposition IDs are configured per-dialer/tenant, NOT shared across
# the account — e.g. id 96 is "Spanish Speaker" on resva2 but "Decision Maker - NYI" on
# resva3. Confirmed live 2026-06-16 (DOM dump of resva3's own <select name="report[types][]">
# showed a completely different id set: 143=Unknown, 145=Sold, 140=Influencer, 96=Decision
# Maker - NYI, 63=Dead Call, 84=Voicemail, etc). This dict is now ONLY a last-resort fallback
# for when the live per-dialer fetch (ReadyModeHTTPClient.init_call_log) fails — always
# prefer the live mapping.
DISPOSITION_TYPE_IDS = {
    "influencer": 144, "dnc - unknown": 145, "dnc - decision maker": 146,
    "unknown": 147, "agent": 143, "decision maker - lead": 138, "voicemail": 139,
    "spanish speaker": 96, "callback": 1, "wrong number": 5,
    "decision maker - nyi": 2, "dead call": 140, "prank voicemail": 148,
    "sold": 151, "listed property": 149,
}
# Base type always sent in addition to any selected dispositions (observed in capture;
# this one IS a constant sentinel, not a per-tenant disposition — it appears as a hidden
# form field on every dialer, never as a visible <option>).
BASE_TYPE = 6

# HARD RULE (2026-08-07): voicemail is NEVER downloaded, under any condition. Matched on the
# label, not the id, because ids are per-dialer and the static map above can be wrong — a
# substring match also covers "Prank Voicemail" and tenant renames like "VM - No Answer".
# Analytics-only callers (reachability / long-VM scans) opt out via block_voicemail=False;
# they read CSV rows and never pull audio. See docs/fixes/NEVER_DOWNLOAD_VOICEMAIL.md.
BLOCKED_DISPOSITION_SUBSTRINGS = ("voicemail",)
# "vm" only as a standalone word, so "VM - No Answer" is blocked but a label that merely
# contains those two letters is not.
BLOCKED_DISPOSITION_TOKENS = ("vm",)


def is_blocked_disposition(label) -> bool:
    """True if this disposition label may never be downloaded."""
    text = str(label or "").strip().lower()
    if any(s in text for s in BLOCKED_DISPOSITION_SUBSTRINGS):
        return True
    tokens = set(re.split(r"[^a-z0-9]+", text))
    return any(t in tokens for t in BLOCKED_DISPOSITION_TOKENS)


def blocked_type_ids(lookup: dict | None) -> set:
    """Every report[types][] id in ``lookup`` whose label is blocked (as strings, since the
    live map's values are the raw <option value> strings)."""
    return {
        str(v) for label, v in (lookup or {}).items() if is_blocked_disposition(label)
    }


class ReadyModeHTTPClient:
    """Thin authenticated client over one ``requests.Session``."""

    def __init__(self, dialer_url: str):
        self.dialer = (dialer_url or "").rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        self._disposition_map: dict | None = None  # this dialer's own label.lower() -> id
        self._folder_map: dict | None = None        # this dialer's own folder name.lower() -> id

    # ── auth ──────────────────────────────────────────────────────────────────
    def _browser_headers(self) -> dict:
        # These headers are REQUIRED for the logout_other_sessions login path; without
        # Origin/Referer/Sec-Fetch the server's "log out other sessions" cURL 500s.
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": self.dialer,
            "Referer": f"{self.dialer}/login_new/?then=/",
            "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin", "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    def login(self, username: str, password: str, user_tz: str = "America/New_York") -> None:
        if not username or not password:
            raise ReadyModeLoginError(
                "ReadyMode credentials are not configured. Set per-user ReadyMode credentials "
                "in the dashboard, or READYMODE_USER / READYMODE_PASSWORD in the environment."
            )
        h = self._browser_headers()
        # seed PHPSESSID / seH
        self.session.get(f"{self.dialer}/", headers=h, timeout=30)
        r = self.session.post(
            f"{self.dialer}/login_new/?then=/",
            data={
                "login_account": username, "login_password": password,
                "login_as_admin": "on", "logout_other_sessions": "on",
                "user_tz": user_tz, "autoequals": "WebRTC",
                "use_phone_module": "auto", "then": "/",
            },
            headers=h, allow_redirects=True, timeout=30,
        )
        if "stationId" not in self.session.cookies.get_dict():
            snippet = (r.text or "")[:160].replace("\n", " ")
            raise ReadyModeLoginError(
                f"ReadyMode login did not establish a session for '{username}' on {self.dialer} "
                f"(no stationId cookie; status={r.status_code}). Response: {snippet!r}"
            )

    def init_call_log(self) -> dict:
        """Mirror the browser: POST the call_log page once to initialize report state, and
        parse THIS dialer's own report[types][] <select> options while we have the HTML.

        Disposition IDs are per-dialer custom config in ReadyMode, not shared across the
        account (confirmed live 2026-06-16 — e.g. id 96 means "Spanish Speaker" on resva2
        but "Decision Maker - NYI" on resva3). Returns {label.lower(): value}, cached after
        the first call. Empty dict on failure — callers should fall back to the static
        DISPOSITION_TYPE_IDS guess in that case.
        """
        if self._disposition_map is not None:
            return self._disposition_map
        mapping: dict = {}
        try:
            r = self.session.post(
                f"{self.dialer}/CCS Reports/call_log",
                headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30,
            )
            html = r.text or ""
            # ReadyMode's markup uses single-quoted attributes (name='report[types][]'),
            # not double — match either.
            m = re.search(r'''<select[^>]*name=["']report\[types\]\[\]["'][^>]*>(.*?)</select>''', html, re.DOTALL)
            if m:
                for opt in re.finditer(r'''<option[^>]*value=["']([^"']*)["'][^>]*>([^<]*)</option>''', m.group(1)):
                    value, label = opt.group(1), unescape(opt.group(2)).strip()
                    if label:
                        mapping[label.lower()] = value
        except Exception:
            pass  # best effort; caller falls back to the static map if this is empty
        self._disposition_map = mapping
        return mapping

    # ── data ──────────────────────────────────────────────────────────────────
    def fetch_report(self, *, time_from: str, time_to: str,
                     time_from_dateonly: str = "1", time_to_dateonly: str = "1",
                     restrict_uid=0, restrict_campaign=0, types=None,
                     duration_filter="-1", page: int = 0) -> dict:
        """GET /CCS Reports/call_log/update and return the parsed JSON.

        JSON keys: campaignlist, userlist, pages, page, results (dict of 25 rows).
        """
        # Caller should always resolve a concrete list via init_call_log()'s live per-dialer
        # map (see disposition_type_ids / download_readymode_calls). This static fallback
        # only fires if that lookup totally failed.
        types = [BASE_TYPE, *DISPOSITION_TYPE_IDS.values()] if types is None else types
        params = [("update", "1")]
        for t in types:
            params.append(("report[types][]", str(t)))
        params += [
            ("report[time_from_d]", time_from), ("report[time_from_dateonly]", time_from_dateonly),
            ("report[time_to_d]", time_to), ("report[time_to_dateonly]", time_to_dateonly),
            ("report[restrict_uid]", str(restrict_uid)),
            ("report[restrict_campaign]", str(restrict_campaign)),
            ("report[restrict_batch]", "0"), ("report[sourceFilter]", "-1"),
            ("report[durationFilter]", str(duration_filter)),
            ("report[callTypeFilter]", "_"), ("report[page]", str(page)),
        ]
        r = self.session.get(
            f"{self.dialer}/CCS Reports/call_log/update", params=params,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": f"{self.dialer}/",
            },
            timeout=60,
        )
        try:
            return r.json()
        except ValueError:
            snippet = (r.text or "")[:160].replace("\n", " ")
            raise ReadyModeLoginError(
                f"Report endpoint did not return JSON (session expired?). "
                f"status={r.status_code} body={snippet!r}"
            )

    def export_call_log_csv(self, *, time_from: str, time_to: str,
                            time_from_dateonly: str = "1", time_to_dateonly: str = "1",
                            restrict_uid=0, restrict_campaign=0, types=None, dispositions=None,
                            duration_filter="-1", block_voicemail=False,
                            fields=(("CCS_Profile.phone", "Phone"), ("u.u_name", "Agent name"))) -> bytes:
        """Download the whole-day call-log CSV in ONE request and return the raw bytes.

        Mirrors the browser's "Export -> Download CSV": the template dropdown is irrelevant on
        the server side — the only thing that drives the output columns is the explicit
        ``fieldList`` we POST. Rows are scoped by the session's report-filter state, so we seed
        it first via :meth:`fetch_report` (date range + dispositions), exactly like the UI.

        This is the right primitive for "pull everything for a day": the JSON ``fetch_report``
        path returns 25 rows/page (hundreds of pages/dialer), whereas this returns the full set
        in a single GET-equivalent POST. See ``docs/READYMODE_HTTP_SPEC.md §7``.
        """
        # seed session report state (date range + dispositions) like the browser
        # ``block_voicemail`` defaults to False here: this is the CSV/analytics primitive
        # (reachability + long-VM scans) which must still SEE voicemail rows. It never pulls
        # audio — the no-voicemail rule is enforced on the download path.
        dmap = self.init_call_log()
        if types is None:
            if dispositions:
                # Resolve the requested disposition labels to THIS dialer's own ids (per-dialer).
                types = disposition_type_ids(dispositions, dmap, block_voicemail=block_voicemail)
            elif dmap:
                # No filter -> ALL of this dialer's ids (mirrors ticking every checkbox), so the
                # export contains every call for the day, not the static-guess subset.
                types = all_type_ids(dmap, block_voicemail=block_voicemail)
        self.fetch_report(
            time_from=time_from, time_to=time_to,
            time_from_dateonly=time_from_dateonly, time_to_dateonly=time_to_dateonly,
            restrict_uid=restrict_uid, restrict_campaign=restrict_campaign,
            types=types, duration_filter=duration_filter, page=0,
        )
        body = []
        for key, name in fields:
            body.append(("fieldList[keys][]", key))
            body.append(("fieldList[names][]", name))
        r = self.session.post(
            f"{self.dialer}/CCS Reports/call_log/ExportMenu/CL.csv",
            data=body,
            headers={"Referer": f"{self.dialer}/", "Origin": self.dialer},
            timeout=120,
        )
        ctype = (r.headers.get("Content-Type") or "").lower()
        if r.status_code != 200 or "csv" not in ctype:
            snippet = (r.text or "")[:160].replace("\n", " ")
            raise ReadyModeLoginError(
                f"CSV export failed on {self.dialer} (status={r.status_code}, ctype={ctype!r}). "
                f"Session expired or no permission? Body: {snippet!r}"
            )
        return r.content

    # ── user creation ─────────────────────────────────────────────────────────
    def get_writable_folders(self) -> dict:
        """This dialer's writable folders as {name.lower(): id}. Cached.

        Folder IDs are PER-INSTANCE — 'Agents' is 48-36-14 on resva/resva2/resva3,
        but 54-109- on resva4, 54-105-14 on resva5, 48-36-4 on resva6/resva7
        (confirmed live 2026-06-16). The createUser <select name='folder'> is
        JS-populated from a ``tmp.uMgmtWritableFolders = [{"name","id"},...]`` blob
        embedded in the page, so we parse that blob rather than the empty <select>.
        Empty dict on failure — callers should surface a clear per-user error.
        """
        if self._folder_map is not None:
            return self._folder_map
        mapping: dict = {}
        try:
            r = self.session.get(
                f"{self.dialer}/Team/ManageUsers/createUser",
                headers={"Referer": f"{self.dialer}/", "X-Requested-With": "XMLHttpRequest"},
                timeout=30,
            )
            m = re.search(r"uMgmtWritableFolders\s*=\s*(\[.*?\]);", r.text or "", re.DOTALL)
            if m:
                for f in json.loads(m.group(1)):
                    nm = str(f.get("name", "")).strip().lower()
                    fid = f.get("id")
                    if nm and fid:
                        mapping[nm] = fid
        except Exception:
            pass  # best effort; caller reports "folder not found" with the (empty) list
        self._folder_map = mapping
        return mapping

    def resolve_folder(self, folder: str) -> str | None:
        """Resolve a folder NAME (e.g. 'Agents') to THIS dialer's id.

        Accepts a name (preferred) or an already-correct id for this dialer.
        Returns None if it can't be resolved (unknown name / page parse failed).
        """
        folders = self.get_writable_folders()
        if not folders:
            return None
        key = (folder or "").strip().lower()
        if key in folders:
            return folders[key]
        if folder in folders.values():  # an id was passed straight through
            return folder
        return None

    def create_user(self, *, name: str, login_id: str, password: str,
                    ou: str = "4", folder: str = "48-36-14", ext: str = "") -> dict:
        """POST Team/ManageUsers/createUser/save for a single user.

        One user per request so each can carry its own password (bulkpw is batch-shared
        on the ReadyMode side but we submit one row at a time).

        Returns the success dict from ReadyMode: {uid, userName, groupId, ...}.
        Raises ReadyModeUserCreateError on any failure.
        """
        params = [
            ("saveData[0][u_name]",    name),
            ("saveData[0][u_account]", login_id),
            ("saveData[0][u_ext]",     ext),
            ("saveData[0][folder]",    folder),
            ("saveData[0][ou]",        ou),
            ("saveData[0][idx]",       "0"),
            ("bulkpw",                 password),
            ("questDisplay",           "false"),
        ]
        r = self.session.post(
            f"{self.dialer}/Team/ManageUsers/createUser/save",
            data=params,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": f"{self.dialer}/Team/ManageUsers/createUser",
            },
            timeout=30,
        )
        try:
            body = r.json()
        except ValueError:
            raise ReadyModeUserCreateError(
                f"Non-JSON response from ReadyMode (status={r.status_code}): {r.text[:200]}"
            )
        if body.get("error"):
            raise ReadyModeUserCreateError(str(body["error"]))
        if not body.get("success"):
            raise ReadyModeUserCreateError(f"Unexpected response: {body}")
        return body["success"][0]

    def delete_user(self, uid: str) -> None:
        """GET Folders/fileAction/Delete/User=<uid> — permanently deletes that user.

        Reverse-engineered from a live recon capture (2026-09-01): the Manage Users UI
        represents users as icons inside folders and deletes them via drag-to-trash, which
        is ReadyMode's generic file-manager delete action (``dropact="Delete"`` on the trash
        drop target), not a user-specific endpoint. No request body — the uid is the whole
        payload, embedded in the URL. Raises ReadyModeUserDeleteError on any non-2xx response.

        The response body's shape on success/failure was not captured (only status 200 was
        observed), so unlike create_user this can't yet distinguish "deleted" from "silently
        no-op'd" purely from the body — a non-2xx status is currently the only confirmed
        failure signal.
        """
        r = self.session.get(
            f"{self.dialer}/Folders/fileAction/Delete/User={uid}",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.dialer}/",
            },
            timeout=30,
        )
        if r.status_code != 200:
            raise ReadyModeUserDeleteError(
                f"Delete failed for uid {uid} on {self.dialer} (status={r.status_code}): {r.text[:200]}"
            )

    def list_folder_users(self, folder_id: str) -> dict:
        """POST Folders/Folder=<id> and parse EVERY user in that folder from the HTML.

        Reverse-engineered from a live recon capture (2026-09-01): this is the same generic
        Folders-app action the UI uses to open a folder and show its icon grid (paired with
        the ``dropact="Delete"`` trash target and ``Folders/fileAction/Delete/User=<uid>``
        found earlier). Unlike fetch_report()'s userlist, this is NOT limited to accounts
        with recent call activity — it returns every account currently sitting in the
        folder, live, regardless of call history. This is what closes the "zero-activity
        account can't be found" gap that both delete-by-name and duplicate-detection have
        when relying on userlist alone.

        `folder_id` here is the short numeric id used by this endpoint (confirmed live as
        "54" for resva4's Agents folder) — NOT the longer per-instance id string
        get_writable_folders() returns for the create-user form (e.g. "54-109-" on resva4).
        The numeric prefix before the first "-" in that longer id is the same value this
        endpoint expects; see resolve_folder_listing_id().

        Returns {uid: name}. Best-effort: a parse failure returns whatever was found before
        it, never raises — callers should treat an empty dict as "couldn't confirm", not
        "empty folder".
        """
        r = self.session.post(
            f"{self.dialer}/Folders/Folder={folder_id}",
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30,
        )
        html = r.text or ""
        result: dict[str, str] = {}
        try:
            markers = list(re.finditer(r"folderres='User=(\d+)'", html))
            for i, m in enumerate(markers):
                uid = m.group(1)
                start = m.start()
                end = markers[i + 1].start() if i + 1 < len(markers) else min(len(html), start + 700)
                chunk = html[start:end]
                runs = [t.strip() for t in re.findall(r">([^<>]+)<", chunk) if t.strip()]
                if not runs:
                    continue
                name = max(runs, key=len)
                if not result.get(uid):
                    result[uid] = name
        except Exception:
            pass  # best effort; whatever was parsed before the failure is still returned
        return result

    def fetch_agent_activity(self, time_from: str, time_to: str) -> dict:
        """POST CCS Reports/agent and parse per-agent shift activity in the date range.

        Reverse-engineered from a live recon capture (2026-09-01), prompted by wanting to
        find agents who are no longer active — deliberately a SHIFT/login signal (did this
        agent log in and work a shift that day), not a call-volume one: this report has no
        per-agent call count, and shift/login activity is what "still active" actually means
        here anyway (an agent with shifts but few calls is a performance question, not a
        cleanup one).

        `time_from`/`time_to` are "MM/DD/YYYY" strings, same format as fetch_report(). Returns
        {uid: {"name": str, "days_active": int, "last_day": str}} — days_active is a COUNT of
        distinct days in range with at least one shift row, not total hours; last_day is the
        raw "Mon DD" string from the last such row (no year — the request's own date range is
        the only source of truth for which year it falls in).

        Parsing note (found live 2026-09-01, after this shipped returning empty for everyone):
        this table's cells are NOT properly closed — each row has ~13 opening `<td>` tags but
        only 1-2 literal `</td>` closes (valid HTML5 "optional end tag" parsing, which browsers
        handle natively but regex matching `<td>...</td>` pairs cannot). Cells are extracted by
        POSITION instead — same technique as list_folder_users() — the text between one `<td`
        tag's own `>` and the next `<td`'s start, not by matching a closing tag. Each agent's
        block also includes one per-agent TOTAL row spanning the whole range (day cell is "-",
        not a real date) — these are excluded from the count, not treated as an extra active day.
        """
        from datetime import date as _date
        r = self.session.post(
            f"{self.dialer}/CCS Reports/agent",
            data={
                "config[dr][time_from_d]": time_from,
                "config[dr][time_to_d]": time_to,
                "config[dr][time_from_dateonly]": "1",
                "config[dr][time_to_dateonly]": "1",
                "agent_uid": "",
                "has_config_update": "1",
                "has_date_update": "1",
                "todaysDate": _date.today().strftime("%m/%d/%Y"),
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=90,
        )
        html = r.text or ""
        result: dict[str, dict] = {}
        try:
            for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
                row_html = row_match.group(1)
                td_starts = [m.start() for m in re.finditer(r"<td\b", row_html, re.IGNORECASE)]
                cells = []
                for i, start in enumerate(td_starts):
                    tag_close = row_html.find(">", start)
                    if tag_close == -1:
                        continue
                    end = td_starts[i + 1] if i + 1 < len(td_starts) else len(row_html)
                    raw = row_html[tag_close + 1:end]
                    cells.append(re.sub(r"<[^>]+>", "", raw).strip())
                if len(cells) < 3:
                    continue
                day, name, uid = cells[0], cells[1], cells[2]
                if not uid.isdigit() or not name:
                    continue
                if day == "-" or not day:
                    continue  # per-agent TOTAL row for the whole range, not a single active day
                entry = result.setdefault(uid, {"name": name, "days_active": 0, "last_day": ""})
                entry["days_active"] += 1
                entry["last_day"] = day  # rows are chronological; last match wins
        except Exception as e:
            raise ReadyModeAgentActivityError(
                f"Failed parsing the agent activity report on {self.dialer}: {e}"
            ) from e

        # Refuse to return "nobody was active" from a response that clearly HAS content.
        # This is the dangerous case: callers treat an empty result as "zero activity for
        # everyone," which flags the entire roster for deletion. It has now bitten twice
        # (unclosed <td> tags; before that, no parsing at all), both times silently. A
        # substantial response with zero parsed rows means the markup changed again — that
        # must surface as an error, not as a delete-everything recommendation.
        if not result and len(html) > 2000:
            raise ReadyModeAgentActivityError(
                f"Agent activity report on {self.dialer} returned {len(html)} bytes but no "
                f"parseable rows — the report's markup likely changed. Refusing to report "
                f"zero activity for every account, which would flag the whole roster."
            )
        return result

    @property
    def cookies(self) -> dict:
        return self.session.cookies.get_dict()


def resolve_folder_listing_id(create_form_folder_id: str) -> str:
    """The numeric id list_folder_users() expects is the prefix of the longer id
    get_writable_folders() returns for the create-user form (e.g. "54-109-" -> "54" on
    resva4). Confirmed live for one folder on one dialer (2026-09-01) — not yet verified
    this prefix relationship holds on every dialer/folder, so treat call sites as
    best-effort, not guaranteed."""
    return (create_form_folder_id or "").split("-")[0]


# ── lookup window (shared by delete-by-name and duplicate-detection) ────────────────────
# fetch_report()'s userlist only includes agents with at least one call in the queried
# date range — there is no other "list all users" endpoint anywhere in this codebase. An
# account with zero calls in this window (freshly created, or simply never dialed) will
# NOT appear in userlist, so neither name-based delete NOR duplicate-detection can see it.
# "0 duplicates found" via lookup_date_range() means "0 found among users with recent call
# activity," not "no duplicates exist on this dialer." See
# docs/investigations/READYMODE_DUPLICATE_DETECTION_WORKFRAME.md.
#
# Was 730 days originally — confirmed live (2026-09-01) that a 2-year report window times
# out fetch_report()'s 60s timeout against a real dialer (too much call history to scan in
# one request). 90 days is a practical tradeoff: still wide enough to catch a duplicate with
# any recent activity, without the request itself failing.
LOOKUP_WINDOW_DAYS = 90


def lookup_date_range(days: int = LOOKUP_WINDOW_DAYS) -> tuple[str, str]:
    from datetime import date, timedelta
    today = date.today()
    start = today - timedelta(days=days)
    return start.strftime("%m/%d/%Y"), today.strftime("%m/%d/%Y")


def group_duplicate_users(userlist: dict) -> list[dict]:
    """userlist: {'x<uid>': 'Folder|Name', ...} -> duplicate groups (2+ uids sharing a name).

    Grouping key is the display name (text after '|'), case-insensitive and trimmed — the
    same match strength as resolve_agent_id's exact-match first pass. Deliberately does NOT
    use resolve_agent_id's fuzzy dot-suffix pass (_name_match): that exists to tolerantly
    resolve a caller-supplied search term, and reusing it here would risk grouping two
    genuinely different people ahead of a delete action. Duplicates are scoped dialer-wide,
    regardless of which folder each account sits in (by design, not a limitation) — folder
    is captured per-account for display only.

    Within each group, accounts are sorted by uid ascending as INTEGERS (ReadyMode uids are
    assigned in creation order, so lowest = oldest/first-created) — NOT lexicographically,
    which would wrongly rank "1000" before "999". The lowest-uid account is tagged "keep";
    every other account in the group is "delete_candidate" — automatic, no manual per-group
    picking, per product decision.

    Groups of size 1 (no duplicate) are omitted. Returns groups sorted by name.

    NOTE: this only ever sees what's in the `userlist` it's given — see lookup_date_range()'s
    docstring for why that's not a full account roster.

    GOTCHA (confirmed live 2026-09-01): userlist keeps a name->uid entry for accounts that
    were already deleted, as long as they have historical calls in the queried range — and
    ReadyMode labels them with a literal "(deleted)" suffix (e.g. "test (deleted)"). These
    are not live duplicates — the account is gone, only its old call records remain — so
    they're excluded entirely rather than grouped. Without this, an already-deleted account
    whose name matches something still-live (or another already-deleted entry) shows up as a
    false-positive duplicate, which is exactly what a live scan caught.
    """
    by_name: dict[str, list[tuple[int, str, str, str]]] = {}  # norm -> [(uid_int, uid_str, folder, label), ...]
    for key, raw in (userlist or {}).items():
        folder, sep, label = str(raw).partition("|")
        label = (label if sep else folder).strip()  # tolerate a malformed entry with no '|'
        folder = folder.strip() if sep else ""
        if not label or "(deleted)" in label.lower():
            continue
        uid_str = str(key).lstrip("x")
        try:
            uid_int = int(uid_str)
        except ValueError:
            continue  # non-numeric uid shouldn't happen live; skip rather than crash the scan
        by_name.setdefault(label.strip().lower(), []).append((uid_int, uid_str, folder, label))

    groups = []
    for accounts in by_name.values():
        if len(accounts) < 2:
            continue
        accounts.sort(key=lambda a: a[0])  # ascending uid = oldest first
        display_name = accounts[0][3]      # canonical casing = the KEPT (oldest) account's own label
        groups.append({
            "name": display_name,
            "accounts": [
                {
                    "uid": uid_str,
                    "folder": folder,
                    "label": f"{folder}|{label}" if folder else label,
                    "role": "keep" if i == 0 else "delete_candidate",
                }
                for i, (_uid_int, uid_str, folder, label) in enumerate(accounts)
            ],
        })
    groups.sort(key=lambda g: g["name"].lower())
    return groups


# ── name -> id resolution (mirrors the exact/dot-suffix matching of the old JS) ──────────
def _name_match(option_text: str, target: str) -> bool:
    o = (option_text or "").strip().lower()
    t = (target or "").strip().lower()
    return bool(t) and (o == t or o.startswith(t + "."))


def resolve_campaign_id(campaignlist: dict, name: str):
    """campaignlist: {id: 'Name'} -> (id, name) or (None, None)."""
    # exact pass first, then dot-suffix
    for cid, nm in (campaignlist or {}).items():
        if (str(nm).strip().lower() == name.strip().lower()):
            return str(cid), str(nm)
    for cid, nm in (campaignlist or {}).items():
        if _name_match(str(nm), name):
            return str(cid), str(nm)
    return None, None


def resolve_agent_id(userlist: dict, name: str):
    """userlist: {'x<uid>': 'Admin|Name' | 'Agents|Name'} -> (uid, label) or (None, None)."""
    for key, nm in (userlist or {}).items():
        label = str(nm).split("|")[-1]
        if label.strip().lower() == name.strip().lower():
            return str(key).lstrip("x"), label.strip()
    for key, nm in (userlist or {}).items():
        label = str(nm).split("|")[-1]
        if _name_match(label, name):
            return str(key).lstrip("x"), label.strip()
    return None, None


def disposition_type_ids(dispositions, dialer_map: dict | None = None,
                         block_voicemail: bool = True) -> list:
    """Map disposition labels -> report[types][] ids: base type 6 + each matched id.

    Prefers ``dialer_map`` (this dialer's own live label->id mapping from
    ``ReadyModeHTTPClient.init_call_log()``) since disposition IDs are per-dialer custom
    config, not shared across the account. Falls back to the static, possibly-wrong
    ``DISPOSITION_TYPE_IDS`` guess only when no live mapping is available.

    With ``block_voicemail`` (the default) a voicemail label is never requested, and the
    tolerant contains-match can never land on a voicemail id.
    """
    lookup = dialer_map if dialer_map else DISPOSITION_TYPE_IDS
    banned = blocked_type_ids(lookup) if block_voicemail else set()
    ids = [BASE_TYPE]
    for d in dispositions or []:
        key = re.sub(r"\s+", " ", str(d).strip().lower())
        if block_voicemail and is_blocked_disposition(key):
            continue
        tid = lookup.get(key)
        if tid is None:  # tolerant contains-match (e.g. "Unknown / dead call" spacing variants)
            for label, v in lookup.items():
                if str(v) in banned:
                    continue
                if key and (key in label or label in key):
                    tid = v
                    break
        if tid is not None and str(tid) not in banned and tid not in ids:
            ids.append(tid)
    return ids


def all_type_ids(dialer_map: dict, block_voicemail: bool = True) -> list:
    """All ids for this dialer (used when no disposition filter is requested) — mirrors
    selecting every checkbox in the UI, scoped correctly to this specific dialer.

    Voicemail ids are dropped unless ``block_voicemail`` is False: an empty selection means
    "every disposition", which is exactly how voicemail used to leak into downloads.
    """
    banned = blocked_type_ids(dialer_map) if block_voicemail else set()
    ids = [BASE_TYPE]
    for v in (dialer_map or {}).values():
        if str(v) in banned:
            continue
        if v not in ids:
            ids.append(v)
    return ids
