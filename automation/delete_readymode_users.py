"""Bulk user deletion orchestrator — pure HTTP, no browser.

Login once per dialer, then delete each target either by exact uid (when the caller
already knows it — e.g. from a duplicate scan) or by resolving a name to a uid. Name
resolution tries the call-log report's userlist first (fast, one request, but only
covers accounts with recent call activity — see readymode_http.lookup_date_range()'s
docstring), then falls back to scanning every writable folder's live listing via
ReadyModeHTTPClient.list_folder_users() (slower — one request per folder — but covers
every account regardless of call history; see docs/investigations/
READYMODE_DELETE_USER_WORKFRAME.md for how that endpoint was found). Prints a progress
line per user consumed by the SSE stream in backend/api/readymode_users.py.
"""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from automation.readymode_http import (
    ReadyModeHTTPClient,
    ReadyModeLoginError,
    ReadyModeUserDeleteError,
    resolve_agent_id,
    lookup_date_range,
    resolve_folder_listing_id,
)


def _resolve_by_folder_scan(client: "ReadyModeHTTPClient", name: str, folder_cache: dict) -> tuple[str | None, str | None]:
    """Fallback for when userlist (call-log-derived) doesn't have the name — scans every
    writable folder's live listing instead (see ReadyModeHTTPClient.list_folder_users()),
    which isn't limited to accounts with recent call activity. `folder_cache` is a plain
    dict the caller keeps across targets so each folder is only fetched once per dialer,
    not once per target. Folders are fetched in parallel — each is an independent HTTP
    request against the same session, and a folder can return 1000+ users worth of HTML
    to parse, so scanning ~6 folders sequentially was the actual source of slowness
    (confirmed live 2026-09-01). Returns (uid, matched_name) or (None, None)."""
    if not folder_cache.get("_loaded"):
        folder_cache["_loaded"] = True
        folders = (client.get_writable_folders() or {}).items()
        listing_ids = [
            (folder_name, resolve_folder_listing_id(create_form_id))
            for folder_name, create_form_id in folders
        ]
        listing_ids = [(n, lid) for n, lid in listing_ids if lid]

        with ThreadPoolExecutor(max_workers=max(1, len(listing_ids))) as pool:
            futures = {
                pool.submit(client.list_folder_users, listing_id): folder_name
                for folder_name, listing_id in listing_ids
            }
            for future in as_completed(futures):
                try:
                    for uid, label in future.result().items():
                        folder_cache.setdefault(label.strip().lower(), (uid, label.strip()))
                except Exception:
                    continue  # best effort — a broken folder scan shouldn't fail the whole batch
    hit = folder_cache.get(name.strip().lower())
    return hit if hit else (None, None)


def delete_users_on_dialer(
    dialer_url: str,
    targets: list[dict],  # [{"name": str, "uid": str | None}, ...]
    readymode_user: str,
    readymode_pass: str,
    update_callback: Optional[Callable[[int, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Login to one dialer, delete all targets, return per-target results.

    A target with a `uid` is deleted directly — no name resolution, no ambiguity. A
    target with only a `name` goes through the existing resolve_agent_id() lookup.
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    dialer_name = dialer_url.rstrip("/").split("//")[-1].split(".")[0]
    results: list[dict] = []

    client = ReadyModeHTTPClient(dialer_url)
    try:
        client.login(readymode_user, readymode_pass)
        log(f"SUCCESS Login OK on {dialer_name}")
    except ReadyModeLoginError as e:
        log(f"ERROR Login failed on {dialer_name}: {e}")
        for t in targets:
            results.append({
                "name": t.get("name", ""), "uid": t.get("uid"), "dialer": dialer_name,
                "status": "failed", "detail": f"Login failed: {e}",
            })
        return results

    # Only worth the round trip if at least one target needs name resolution — a batch
    # of pure uid targets (e.g. from a duplicate scan) skips it entirely.
    needs_userlist = any(not (t.get("uid") or "").strip() for t in targets)
    userlist: dict = {}
    if needs_userlist:
        time_from, time_to = lookup_date_range()
        try:
            report = client.fetch_report(time_from=time_from, time_to=time_to, page=0)
            userlist = report.get("userlist") or {}
        except Exception as e:
            log(f"ERROR Could not fetch user list on {dialer_name}: {e}")

    folder_cache: dict = {}  # lazily populated by _resolve_by_folder_scan, shared across targets

    for i, target in enumerate(targets, 1):
        name = target.get("name", "")
        uid = (target.get("uid") or "").strip()

        if uid:
            try:
                client.delete_user(uid)
                log(f"DELETED {dialer_name} | {name} (uid {uid})")
                results.append({
                    "name": name, "uid": uid, "dialer": dialer_name, "status": "deleted", "detail": "",
                })
            except ReadyModeUserDeleteError as e:
                log(f"FAILED  {dialer_name} | {name} (uid {uid}): {e}")
                results.append({
                    "name": name, "uid": uid, "dialer": dialer_name, "status": "failed", "detail": str(e),
                })
            if update_callback:
                update_callback(i, len(targets))
            continue

        resolved_uid, matched_label = resolve_agent_id(userlist, name)
        if not resolved_uid:
            # Not in the call-log userlist (no recent calls) — fall back to scanning live
            # folder listings, which cover every account regardless of call activity.
            resolved_uid, matched_label = _resolve_by_folder_scan(client, name, folder_cache)

        if not resolved_uid:
            detail = "Not found in this dialer's call-log user list or any writable folder"
            log(f"FAILED  {dialer_name} | {name}: {detail}")
            results.append({
                "name": name, "uid": None, "dialer": dialer_name, "status": "failed", "detail": detail,
            })
            if update_callback:
                update_callback(i, len(targets))
            continue

        try:
            client.delete_user(resolved_uid)
            log(f"DELETED {dialer_name} | {name} ({matched_label}, uid {resolved_uid})")
            results.append({
                "name": name, "uid": resolved_uid, "dialer": dialer_name, "status": "deleted", "detail": "",
            })
        except ReadyModeUserDeleteError as e:
            log(f"FAILED  {dialer_name} | {name}: {e}")
            results.append({
                "name": name, "uid": resolved_uid, "dialer": dialer_name, "status": "failed", "detail": str(e),
            })
        if update_callback:
            update_callback(i, len(targets))

    return results


def delete_users_multi_dialer(
    dialer_urls: list[str],
    targets: list[dict],
    readymode_user: str,
    readymode_pass: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Delete targets on multiple dialers in parallel. Returns flat list of all results."""
    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(dialer_urls)) as pool:
        futures = {
            pool.submit(
                delete_users_on_dialer, url, targets,
                readymode_user, readymode_pass,
                None, log_callback,
            ): url
            for url in dialer_urls
        }
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as e:
                url = futures[future]
                name = url.rstrip("/").split("//")[-1].split(".")[0]
                if log_callback:
                    log_callback(f"ERROR Unexpected error on {name}: {e}")
                else:
                    print(f"ERROR Unexpected error on {name}: {e}")
                for t in targets:
                    all_results.append({
                        "name": t.get("name", ""), "uid": t.get("uid"),
                        "dialer": name, "status": "failed", "detail": str(e),
                    })

    return all_results
