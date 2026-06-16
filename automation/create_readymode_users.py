"""Bulk user creation orchestrator — pure HTTP, no browser.

Login once per dialer, create each user sequentially (one request per user so
each carries its own password), print a progress line per user consumed by the
SSE stream in backend/api/readymode_users.py.
"""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from automation.readymode_http import ReadyModeHTTPClient, ReadyModeLoginError, ReadyModeUserCreateError


def create_users_on_dialer(
    dialer_url: str,
    users: list[dict],
    readymode_user: str,
    readymode_pass: str,
    update_callback: Optional[Callable[[int, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Login to one dialer, create all users, return per-user results."""
    def log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    dialer_name = dialer_url.rstrip("/").split("//")[-1].split(".")[0]
    results = []

    client = ReadyModeHTTPClient(dialer_url)
    try:
        client.login(readymode_user, readymode_pass)
        log(f"SUCCESS Login OK on {dialer_name}")
    except ReadyModeLoginError as e:
        log(f"ERROR Login failed on {dialer_name}: {e}")
        for u in users:
            results.append({
                "name": u["name"], "login_id": u["login_id"],
                "dialer": dialer_name, "status": "failed",
                "detail": f"Login failed: {e}",
            })
        return results

    # Folder IDs are per-dialer (e.g. 'Agents' = 48-36-14 on resva but 54-109- on
    # resva4), so resolve the requested folder NAME to THIS dialer's id once up front.
    folder_map = client.get_writable_folders()

    for i, u in enumerate(users, 1):
        name     = u["name"]
        login_id = u["login_id"]
        password = u["password"]
        folder   = u.get("folder", "Agents")
        ou       = u.get("ou", "4")
        ext      = u.get("ext", "")

        folder_id = client.resolve_folder(folder)
        if not folder_id:
            available = ", ".join(sorted(folder_map)) or "none"
            log(f"FAILED  {dialer_name} | {name} ({login_id}): folder '{folder}' not found on this dialer (available: {available})")
            results.append({
                "name": name, "login_id": login_id,
                "dialer": dialer_name, "status": "failed",
                "detail": f"Folder '{folder}' not found on {dialer_name} (available: {available})",
            })
            if update_callback:
                update_callback(i, len(users))
            continue

        try:
            client.create_user(name=name, login_id=login_id, password=password,
                               ou=ou, folder=folder_id, ext=ext)
            log(f"CREATED {dialer_name} | {name} ({login_id})")
            results.append({
                "name": name, "login_id": login_id,
                "dialer": dialer_name, "status": "created", "detail": "",
            })
        except ReadyModeUserCreateError as e:
            log(f"FAILED  {dialer_name} | {name} ({login_id}): {e}")
            results.append({
                "name": name, "login_id": login_id,
                "dialer": dialer_name, "status": "failed", "detail": str(e),
            })
        if update_callback:
            update_callback(i, len(users))

    return results


def create_users_multi_dialer(
    dialer_urls: list[str],
    users: list[dict],
    readymode_user: str,
    readymode_pass: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Create users on multiple dialers in parallel. Returns flat list of all results."""
    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(dialer_urls)) as pool:
        futures = {
            pool.submit(
                create_users_on_dialer, url, users,
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
                for u in users:
                    all_results.append({
                        "name": u["name"], "login_id": u["login_id"],
                        "dialer": name, "status": "failed", "detail": str(e),
                    })

    return all_results
