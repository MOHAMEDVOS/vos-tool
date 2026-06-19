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
                            duration_filter="-1",
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
        dmap = self.init_call_log()
        if types is None:
            if dispositions:
                # Resolve the requested disposition labels to THIS dialer's own ids (per-dialer).
                types = disposition_type_ids(dispositions, dmap)
            elif dmap:
                # No filter -> ALL of this dialer's ids (mirrors ticking every checkbox), so the
                # export contains every call for the day, not the static-guess subset.
                types = all_type_ids(dmap)
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

    @property
    def cookies(self) -> dict:
        return self.session.cookies.get_dict()


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


def disposition_type_ids(dispositions, dialer_map: dict | None = None) -> list:
    """Map disposition labels -> report[types][] ids: base type 6 + each matched id.

    Prefers ``dialer_map`` (this dialer's own live label->id mapping from
    ``ReadyModeHTTPClient.init_call_log()``) since disposition IDs are per-dialer custom
    config, not shared across the account. Falls back to the static, possibly-wrong
    ``DISPOSITION_TYPE_IDS`` guess only when no live mapping is available.
    """
    lookup = dialer_map if dialer_map else DISPOSITION_TYPE_IDS
    ids = [BASE_TYPE]
    for d in dispositions or []:
        key = re.sub(r"\s+", " ", str(d).strip().lower())
        tid = lookup.get(key)
        if tid is None:  # tolerant contains-match (e.g. "Unknown / dead call" spacing variants)
            for label, v in lookup.items():
                if key and (key in label or label in key):
                    tid = v
                    break
        if tid is not None and tid not in ids:
            ids.append(tid)
    return ids


def all_type_ids(dialer_map: dict) -> list:
    """All ids for this dialer (used when no disposition filter is requested) — mirrors
    selecting every checkbox in the UI, scoped correctly to this specific dialer."""
    ids = [BASE_TYPE]
    for v in dialer_map.values():
        if v not in ids:
            ids.append(v)
    return ids
