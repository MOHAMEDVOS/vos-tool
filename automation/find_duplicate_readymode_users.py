"""Duplicate-user scan orchestrator — HTTP throughout, except that
ReadyModeHTTPClient.login() can launch a real browser if a dialer puts up a Cloudflare
challenge (see automation/readymode_http.py's module docstring). Nothing else here
touches a browser.

Login once per dialer, build a name->uid roster from two sources, group by shared
display name, and return one result per dialer for the SSE stream in
backend/api/readymode_users.py. Read-only — this module never deletes anything; a
duplicate found here is removed via automation.delete_readymode_users, uid-capable so
it can target one exact account precisely.

The roster merges: (1) the call-log report's userlist (fast, one request, but only
covers accounts with recent call activity — see readymode_http.lookup_date_range()'s
docstring) and (2) every writable folder's live listing via
ReadyModeHTTPClient.list_folder_users() (slower — one request per folder — but covers
every account regardless of call history). Without (2), a duplicate where one copy has
zero recent calls is invisible — confirmed live 2026-09-01, see
docs/investigations/READYMODE_DUPLICATE_DETECTION_WORKFRAME.md.
"""

from __future__ import annotations
from typing import Callable, Optional

from automation.readymode_http import (
    ReadyModeHTTPClient,
    ReadyModeLoginError,
    group_duplicate_users,
    lookup_date_range,
    fetch_all_folder_users,
    dialer_name_from_url,
    run_per_dialer,
)


def _build_roster(client: "ReadyModeHTTPClient", userlist: dict, log: Callable[[str], None]) -> dict:
    """Merge fetch_report()'s userlist with every writable folder's live listing (via the
    shared automation.readymode_http.fetch_all_folder_users()), in userlist's own
    {"x<uid>": "Folder|Name"} shape, so group_duplicate_users() can consume the combined
    result unmodified. A uid already present from userlist is not overwritten by the
    folder scan — userlist already carries its real folder."""
    roster = dict(userlist or {})
    for uid, (name, folder_name) in fetch_all_folder_users(client, log).items():
        key = f"x{uid}"
        if key not in roster:
            roster[key] = f"{folder_name}|{name}"
    return roster


def find_duplicate_users_on_dialer(
    dialer_url: str,
    readymode_user: str,
    readymode_pass: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Login to one dialer, fetch its userlist, return its duplicate groups.

    A login/fetch failure returns status="failed", NOT status="ok" with an empty
    groups list — an empty result must never be indistinguishable from "this dialer
    genuinely has no duplicates."
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    dialer_name = dialer_name_from_url(dialer_url)
    client = ReadyModeHTTPClient(dialer_url)

    try:
        client.login(readymode_user, readymode_pass)
        log(f"SUCCESS Login OK on {dialer_name}")
    except ReadyModeLoginError as e:
        log(f"ERROR Login failed on {dialer_name}: {e}")
        return {
            "dialer": dialer_name, "dialer_url": dialer_url,
            "status": "failed", "detail": f"Login failed: {e}", "groups": [],
        }

    time_from, time_to = lookup_date_range()
    try:
        report = client.fetch_report(time_from=time_from, time_to=time_to, page=0)
        userlist = report.get("userlist") or {}
    except Exception as e:
        log(f"ERROR Could not fetch user list on {dialer_name}: {e}")
        return {
            "dialer": dialer_name, "dialer_url": dialer_url,
            "status": "failed", "detail": f"Could not fetch user list: {e}", "groups": [],
        }

    roster = _build_roster(client, userlist, log)

    groups = group_duplicate_users(roster)
    n_accounts = sum(len(g["accounts"]) for g in groups)
    log(f"SCANNED {dialer_name} | {len(groups)} duplicate name(s) found "
        f"({n_accounts} accounts, {len(roster)} total across recent calls + folder listings)")
    return {
        "dialer": dialer_name, "dialer_url": dialer_url,
        "status": "ok", "detail": "", "groups": groups,
    }


def find_duplicate_users_multi_dialer(
    dialer_urls: list[str],
    readymode_user: str,
    readymode_pass: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Scan multiple dialers in parallel. Returns one result dict per dialer (see
    find_duplicate_users_on_dialer) — NOT flattened, unlike create/delete's flat
    per-user list, since a uid is only meaningful on the dialer it came from."""
    def worker(url: str) -> dict:
        return find_duplicate_users_on_dialer(url, readymode_user, readymode_pass, log_callback)

    def on_error(url: str, e: Exception) -> dict:
        return {
            "dialer": dialer_name_from_url(url), "dialer_url": url,
            "status": "failed", "detail": str(e), "groups": [],
        }

    return run_per_dialer(dialer_urls, worker, on_error, log_callback)
