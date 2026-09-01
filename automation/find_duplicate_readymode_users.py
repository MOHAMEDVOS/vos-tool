"""Duplicate-user scan orchestrator — pure HTTP, no browser.

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from automation.readymode_http import (
    ReadyModeHTTPClient,
    ReadyModeLoginError,
    group_duplicate_users,
    lookup_date_range,
    resolve_folder_listing_id,
)


def _build_roster(client: "ReadyModeHTTPClient", userlist: dict, log: Callable[[str], None]) -> dict:
    """Merge fetch_report()'s userlist with every writable folder's live listing, in
    userlist's own {"x<uid>": "Folder|Name"} shape, so group_duplicate_users() can
    consume the combined result unmodified. A uid already present from userlist is not
    overwritten by the folder scan — userlist already carries its real folder. Folders
    are fetched in parallel (each is an independent request against the same session,
    and a folder can be 1000+ users worth of HTML to parse) — sequential fetching was
    confirmed live 2026-09-01 as the actual source of scan slowness."""
    roster = dict(userlist or {})
    try:
        folders = client.get_writable_folders() or {}
    except Exception as e:
        log(f"WARN  Could not list writable folders: {e}")
        return roster

    listing_ids = [
        (folder_name, resolve_folder_listing_id(create_form_id))
        for folder_name, create_form_id in folders.items()
    ]
    listing_ids = [(n, lid) for n, lid in listing_ids if lid]

    with ThreadPoolExecutor(max_workers=max(1, len(listing_ids))) as pool:
        futures = {
            pool.submit(client.list_folder_users, listing_id): folder_name
            for folder_name, listing_id in listing_ids
        }
        for future in as_completed(futures):
            folder_name = futures[future]
            try:
                for uid, name in future.result().items():
                    key = f"x{uid}"
                    if key not in roster:
                        roster[key] = f"{folder_name}|{name}"
            except Exception as e:
                log(f"WARN  Could not list folder '{folder_name}': {e}")
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

    dialer_name = dialer_url.rstrip("/").split("//")[-1].split(".")[0]
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
    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(dialer_urls)) as pool:
        futures = {
            pool.submit(
                find_duplicate_users_on_dialer, url,
                readymode_user, readymode_pass, log_callback,
            ): url
            for url in dialer_urls
        }
        for future in as_completed(futures):
            url = futures[future]
            dialer_name = url.rstrip("/").split("//")[-1].split(".")[0]
            try:
                all_results.append(future.result())
            except Exception as e:
                if log_callback:
                    log_callback(f"ERROR Unexpected error on {dialer_name}: {e}")
                else:
                    print(f"ERROR Unexpected error on {dialer_name}: {e}")
                all_results.append({
                    "dialer": dialer_name, "dialer_url": url,
                    "status": "failed", "detail": str(e), "groups": [],
                })

    return all_results
