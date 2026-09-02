"""Inactive-user scan orchestrator — pure HTTP, no browser.

Login to every requested dialer, build the FULL account roster from every writable
folder on each (see ReadyModeHTTPClient.list_folder_users() — not limited to accounts
with recent activity, unlike the call-log report), cross-reference each account against
its shift/login activity over a lookback window
(ReadyModeHTTPClient.fetch_agent_activity()), and flag anyone at or below a "days
active" threshold as an inactive candidate.

This is deliberately a SHIFT/login activity signal, not a call-volume one — see
fetch_agent_activity()'s docstring for why. Read-only — this module never deletes
anything; a candidate found here is removed via automation.delete_readymode_users'
uid-based delete, the same as a duplicate-scan candidate.

CROSS-DIALER RULE (added 2026-09-01, per explicit product decision): an agent can hold
a separate account on more than one dialer. Someone low-activity on dialer A but
actively working dialer B is active at the company — they should NOT be flagged just
because one specific account looks idle. So a candidate is only flagged if their
activity is at-or-below the threshold on EVERY dialer they were found on, among the
dialers actually scanned in this request. Matching across dialers is by display name
(case-insensitive, trimmed) — there's no other cross-dialer identity signal available;
a uid is only ever meaningful on the dialer it came from.
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

# 0 = "never logged in at all during the lookback window" — no shift, no logged hours.
# That is the only threshold that answers "should this account still exist" on its own;
# anything higher is a judgement call about someone who DID work, so the caller has to
# opt into it deliberately.
DEFAULT_MAX_DAYS_ACTIVE = 0
DEFAULT_LOOKBACK_DAYS = 60


def _is_inactive(days_active: int, minutes_active: int, max_days_active: int) -> bool:
    """Is this activity at-or-below the threshold?

    At max_days_active=0 the question is "no login record at all," so any logged time
    counts as active too, not just a day count — two independent signals from the same
    report have to both be zero before an account is offered for deletion. Above 0 the
    caller has explicitly asked a days-based question, so days alone decide it.
    """
    if days_active > max_days_active:
        return False
    if max_days_active == 0 and minutes_active > 0:
        return False
    return True


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


def _scan_dialer_full(
    dialer_url: str,
    readymode_user: str,
    readymode_pass: str,
    lookback_days: int,
    log_callback: Optional[Callable[[str], None]],
) -> dict:
    """Login to one dialer, return EVERY roster account's activity, unfiltered by any
    threshold. Unfiltered on purpose: find_inactive_users_multi_dialer needs each
    dialer's full picture to check whether a locally-low account is actually active on
    a different dialer, which it can't do from a pre-filtered "candidates only" list.

    A login/fetch failure returns status="failed", never status="ok" with an empty list
    — a failure must not look like "found nothing," and (as of the cross-dialer rule)
    must not silently make OTHER dialers' candidates look more inactive than they are
    by being left out of the "active anywhere?" check.
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
                "detail": f"Login failed: {e}", "accounts": []}

    roster = _build_full_roster(client, log)
    if not roster:
        log(f"ERROR Could not build a roster on {dialer_name} (no writable folders resolved)")
        return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "failed",
                "detail": "Could not list any writable folder", "accounts": []}

    today = date.today()
    time_from = (today - timedelta(days=lookback_days)).strftime("%m/%d/%Y")
    time_to = today.strftime("%m/%d/%Y")
    try:
        activity = client.fetch_agent_activity(time_from=time_from, time_to=time_to)
    except Exception as e:
        log(f"ERROR Could not fetch agent activity on {dialer_name}: {e}")
        return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "failed",
                "detail": f"Could not fetch agent activity: {e}", "accounts": []}

    # Matched by NAME, not uid: the built-in Agent Report preset has no User ID column, and
    # the custom templates that do are per-account (relying on one is what broke this in
    # production). Both sides are ReadyMode's own display names, so they line up. A name
    # collision resolves toward the most-active account, which fails safe — nobody gets
    # deleted because a namesake was idle.
    accounts = []
    matched = 0
    for uid, info in roster.items():
        act = activity.get(info["name"].strip().lower()) or {}
        days = act.get("days", 0)
        minutes = act.get("minutes", 0)
        if days or minutes:
            matched += 1
        accounts.append({
            "uid": uid,
            "name": info["name"],
            "folder": info["folder"],
            "days_active": days,
            "minutes_active": minutes,
            "last_day": "",
        })

    log(f"SCANNED {dialer_name} | {len(accounts)} accounts, {matched} matched to recent "
        f"activity ({len(activity)} agents active in last {lookback_days} days)")
    return {"dialer": dialer_name, "dialer_url": dialer_url, "status": "ok", "detail": "", "accounts": accounts}


def find_inactive_users_multi_dialer(
    dialer_urls: list[str],
    readymode_user: str,
    readymode_pass: str,
    max_days_active: int = DEFAULT_MAX_DAYS_ACTIVE,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Scan multiple dialers in parallel, then apply the cross-dialer rule: only flag an
    account if its name's activity is at-or-below `max_days_active` on EVERY
    successfully-scanned dialer that name appears on — an agent active elsewhere isn't a
    candidate anywhere, even on the dialer(s) where their own account looks idle.

    A dialer that failed to scan is excluded from the "active elsewhere?" check (no data
    from it either way) but still reported back with status="failed" so the caller knows
    not to trust that dialer's silence as "confirmed inactive."

    Returns one result dict per dialer — not flattened, since a uid only means something
    on the dialer it came from.
    """
    def log(msg: str):
        (log_callback or print)(msg)

    raw_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(dialer_urls)) as pool:
        futures = {
            pool.submit(
                _scan_dialer_full, url,
                readymode_user, readymode_pass,
                lookback_days, log_callback,
            ): url
            for url in dialer_urls
        }
        for future in as_completed(futures):
            url = futures[future]
            dialer_name = url.rstrip("/").split("//")[-1].split(".")[0]
            try:
                raw_results.append(future.result())
            except Exception as e:
                log(f"ERROR Unexpected error on {dialer_name}: {e}")
                raw_results.append({
                    "dialer": dialer_name, "dialer_url": url,
                    "status": "failed", "detail": str(e), "accounts": [],
                })

    ok_results = [r for r in raw_results if r["status"] == "ok"]
    scanned_count = len(ok_results)

    # name (normalized) -> highest activity seen for that name on any scanned dialer
    name_max_days: dict[str, int] = {}
    name_max_minutes: dict[str, int] = {}
    for r in ok_results:
        for acc in r["accounts"]:
            key = acc["name"].strip().lower()
            if key:
                name_max_days[key] = max(name_max_days.get(key, 0), acc["days_active"])
                name_max_minutes[key] = max(name_max_minutes.get(key, 0), acc["minutes_active"])

    final_results: list[dict] = []
    for r in raw_results:
        if r["status"] != "ok":
            final_results.append({
                "dialer": r["dialer"], "dialer_url": r["dialer_url"],
                "status": "failed", "detail": r["detail"], "users": [],
            })
            continue

        candidates = []
        excluded_active_elsewhere = 0
        for acc in r["accounts"]:
            if not _is_inactive(acc["days_active"], acc["minutes_active"], max_days_active):
                continue  # active enough right here — never a candidate regardless of elsewhere
            key = acc["name"].strip().lower()
            # scanned_count > 1 guards this from ever excluding anything when only one
            # dialer was requested — the name maps would just equal this dialer's own data
            # in that case, so the check degrades to a no-op, but being explicit here
            # avoids relying on that falling out correctly by accident.
            if scanned_count > 1 and not _is_inactive(
                name_max_days.get(key, 0), name_max_minutes.get(key, 0), max_days_active
            ):
                excluded_active_elsewhere += 1
                continue
            candidates.append(acc)
        candidates.sort(key=lambda u: (u["days_active"], u["name"].lower()))

        log(f"FILTERED {r['dialer']} | {len(candidates)} candidate(s) after cross-dialer check"
            + (f" ({excluded_active_elsewhere} excluded — active on another scanned dialer)"
               if excluded_active_elsewhere else ""))
        final_results.append({
            "dialer": r["dialer"], "dialer_url": r["dialer_url"],
            "status": "ok", "detail": "", "users": candidates,
        })

    return final_results
