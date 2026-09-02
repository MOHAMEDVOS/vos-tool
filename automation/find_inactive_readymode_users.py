"""Inactive-user scan orchestrator — pure HTTP, no browser.

Login once per dialer, build the FULL account roster from every writable folder (see
ReadyModeHTTPClient.list_folder_users() — not limited to accounts with recent activity,
unlike the call-log report), cross-reference each account against its shift/login
activity over a lookback window (ReadyModeHTTPClient.fetch_agent_activity()), and flag
anyone at or below a "days active" threshold as an inactive candidate for review.

This is deliberately a SHIFT/login activity signal, not a call-volume one — see
fetch_agent_activity()'s docstring for why. Read-only — this module never deletes
anything; a candidate found here is removed via automation.delete_readymode_users'
uid-based delete, the same as a duplicate-scan candidate.
"""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Callable, Optional

from automation.readymode_http import (
    ReadyModeHTTPClient,
    ReadyModeLoginError,
    resolve_folder_listing_id,
)

DEFAULT_MAX_DAYS_ACTIVE = 2
DEFAULT_LOOKBACK_DAYS = 60


def _build_full_roster(client: "ReadyModeHTTPClient", log: Callable[[str], None]) -> dict:
    """{uid: {"name": str, "folder": str}} for every account in every writable folder,
    fetched in parallel (see the identical pattern in find_duplicate_readymode_users.py
    and delete_readymode_users.py — same slowness lesson: sequential folder fetches are
    the actual bottleneck, not the request itself)."""
    roster: dict[str, dict] = {}
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
                    roster.setdefault(uid, {"name": name, "folder": folder_name})
            except Exception as e:
                log(f"WARN  Could not list folder '{folder_name}': {e}")
    return roster


def find_inactive_users_on_dialer(
    dialer_url: str,
    readymode_user: str,
    readymode_pass: str,
    max_days_active: int = DEFAULT_MAX_DAYS_ACTIVE,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    log_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Login to one dialer, return every account at or below `max_days_active` shift-days
    in the last `lookback_days` days — including accounts with zero shifts at all (they
    simply never appear in fetch_agent_activity()'s result, so they default to 0).

    A login/fetch failure returns status="failed", never status="ok" with an empty list —
    same reasoning as the duplicate scan: a failure must not look like "found nothing."
    """
    def log(msg: str):
        (log_callback or print)(msg)

    dialer_name = dialer_url.rstrip("/").split("//")[-1].split(".")[0]
    client = ReadyModeHTTPClient(dialer_url)

    try:
        client.login(readymode_user, readymode_pass)
        log(f"SUCCESS Login OK on {dialer_name}")
    except ReadyModeLoginError as e:
        log(f"ERROR Login failed on {dialer_name}: {e}")
        return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "failed",
                "detail": f"Login failed: {e}", "users": []}

    roster = _build_full_roster(client, log)
    if not roster:
        log(f"ERROR Could not build a roster on {dialer_name} (no writable folders resolved)")
        return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "failed",
                "detail": "Could not list any writable folder", "users": []}

    today = date.today()
    time_from = (today - timedelta(days=lookback_days)).strftime("%m/%d/%Y")
    time_to = today.strftime("%m/%d/%Y")
    try:
        activity = client.fetch_agent_activity(time_from=time_from, time_to=time_to)
    except Exception as e:
        log(f"ERROR Could not fetch agent activity on {dialer_name}: {e}")
        return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "failed",
                "detail": f"Could not fetch agent activity: {e}", "users": []}

    inactive = []
    for uid, info in roster.items():
        a = activity.get(uid)
        days_active = a["days_active"] if a else 0
        if days_active <= max_days_active:
            inactive.append({
                "uid": uid,
                "name": info["name"],
                "folder": info["folder"],
                "days_active": days_active,
                "last_day": a["last_day"] if a else "",
            })
    inactive.sort(key=lambda u: (u["days_active"], u["name"].lower()))

    log(f"SCANNED {dialer_name} | {len(inactive)} inactive candidate(s) "
        f"(≤{max_days_active} active days in last {lookback_days}) out of {len(roster)} total accounts")
    return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "ok", "detail": "", "users": inactive}


def find_inactive_users_multi_dialer(
    dialer_urls: list[str],
    readymode_user: str,
    readymode_pass: str,
    max_days_active: int = DEFAULT_MAX_DAYS_ACTIVE,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Scan multiple dialers in parallel. Returns one result dict per dialer (see
    find_inactive_users_on_dialer) — not flattened, since a uid only means something on
    the dialer it came from."""
    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(dialer_urls)) as pool:
        futures = {
            pool.submit(
                find_inactive_users_on_dialer, url,
                readymode_user, readymode_pass,
                max_days_active, lookback_days, log_callback,
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
                    "status": "failed", "detail": str(e), "users": [],
                })

    return all_results
