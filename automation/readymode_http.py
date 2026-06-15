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
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class ReadyModeLoginError(Exception):
    """Login / session failure (bad credentials, blocked, or session not established)."""


class ReadyModeNoCallsError(Exception):
    """No matching campaign/agent, or no recordings for the given filters."""


# Disposition label -> report[types][] id  (from the call_log page <select name="report[types][]">).
DISPOSITION_TYPE_IDS = {
    "influencer": 144, "dnc - unknown": 145, "dnc - decision maker": 146,
    "unknown": 147, "agent": 143, "decision maker - lead": 138, "voicemail": 139,
    "spanish speaker": 96, "callback": 1, "wrong number": 5,
    "decision maker - nyi": 2, "dead call": 140, "prank voicemail": 148,
    "sold": 151, "listed property": 149,
}
# Base type always sent in addition to any selected dispositions (observed in capture).
BASE_TYPE = 6
# Full default type set sent when NO disposition filter is applied (captured unfiltered).
DEFAULT_TYPES = [6, 144, 145, 146, 147, 143, 138, 139, 96, 1, 5, 2, 140, 148, 151, 149,
                 "User,%", "Queue,1", "Queue,12", "Queue,13", "Queue,14", "Queue,15"]


class ReadyModeHTTPClient:
    """Thin authenticated client over one ``requests.Session``."""

    def __init__(self, dialer_url: str):
        self.dialer = (dialer_url or "").rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})

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

    def init_call_log(self) -> None:
        """Mirror the browser: POST the call_log page once to initialize report state."""
        try:
            self.session.post(
                f"{self.dialer}/CCS Reports/call_log",
                headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30,
            )
        except Exception:
            pass  # best effort; the update endpoint works without it once logged in

    # ── data ──────────────────────────────────────────────────────────────────
    def fetch_report(self, *, time_from: str, time_to: str,
                     time_from_dateonly: str = "1", time_to_dateonly: str = "1",
                     restrict_uid=0, restrict_campaign=0, types=None,
                     duration_filter="-1", page: int = 0) -> dict:
        """GET /CCS Reports/call_log/update and return the parsed JSON.

        JSON keys: campaignlist, userlist, pages, page, results (dict of 25 rows).
        """
        types = DEFAULT_TYPES if types is None else types
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


def disposition_type_ids(dispositions) -> list:
    """Map disposition labels -> report[types][] ids: base type 6 + each matched id."""
    ids = [BASE_TYPE]
    for d in dispositions or []:
        key = re.sub(r"\s+", " ", str(d).strip().lower())
        tid = DISPOSITION_TYPE_IDS.get(key)
        if tid is None:  # tolerant contains-match (e.g. "Unknown / dead call" spacing variants)
            for label, v in DISPOSITION_TYPE_IDS.items():
                if key and (key in label or label in key):
                    tid = v
                    break
        if tid is not None and tid not in ids:
            ids.append(tid)
    return ids
