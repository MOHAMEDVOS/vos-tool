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
) -> list[dict]:
    """Login to one dialer, create all users, return per-user results.

    Each result dict has: name, login_id, dialer, status ('created'|'failed'), detail.
    Prints progress lines (picked up by SSE thread-local stdout proxy).
    """
    dialer_name = dialer_url.rstrip("/").split("//")[-1].split(".")[0]
    results = []

    client = ReadyModeHTTPClient(dialer_url)
    try:
        client.login(readymode_user, readymode_pass)
        print(f"SUCCESS Login OK on {dialer_name}")
    except ReadyModeLoginError as e:
        print(f"ERROR Login failed on {dialer_name}: {e}")
        for u in users:
            results.append({
                "name": u["name"], "login_id": u["login_id"],
                "dialer": dialer_name, "status": "failed",
                "detail": f"Login failed: {e}",
            })
        return results

    for i, u in enumerate(users, 1):
        name     = u["name"]
        login_id = u["login_id"]
        password = u["password"]
        folder   = u.get("folder", "48-36-14")
        ou       = u.get("ou", "4")
        ext      = u.get("ext", "")
        try:
            client.create_user(name=name, login_id=login_id, password=password,
                               ou=ou, folder=folder, ext=ext)
            print(f"CREATED {dialer_name} | {name} ({login_id})")
            results.append({
                "name": name, "login_id": login_id,
                "dialer": dialer_name, "status": "created", "detail": "",
            })
        except ReadyModeUserCreateError as e:
            print(f"FAILED  {dialer_name} | {name} ({login_id}): {e}")
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
) -> list[dict]:
    """Create users on multiple dialers in parallel. Returns flat list of all results."""
    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(dialer_urls)) as pool:
        futures = {
            pool.submit(create_users_on_dialer, url, users, readymode_user, readymode_pass): url
            for url in dialer_urls
        }
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as e:
                url = futures[future]
                name = url.rstrip("/").split("//")[-1].split(".")[0]
                print(f"ERROR Unexpected error on {name}: {e}")
                for u in users:
                    all_results.append({
                        "name": u["name"], "login_id": u["login_id"],
                        "dialer": name, "status": "failed", "detail": str(e),
                    })

    return all_results
