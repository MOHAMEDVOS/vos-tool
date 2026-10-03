"""Podio OAuth and read-only verification for TL Actions form submissions."""

from __future__ import annotations

import json
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from backend.services.tl_actions_reconciliation import normalize_details
from backend.services.tl_actions_submission import _action_fields
from lib.database import get_db_manager
from lib.security_utils import SecurityManager

PODIO_API = "https://api.podio.com"
PODIO_AUTHORIZE = "https://podio.com/oauth/authorize"
PODIO_TOKEN = f"{PODIO_API}/oauth/token/v2"
PODIO_APP_ID = os.getenv("PODIO_TL_ACTIONS_APP_ID", "2500783")
PODIO_REDIRECT_URI = os.getenv(
    "PODIO_OAUTH_REDIRECT_URI",
    "https://vos-tool.up.railway.app/api/tl-actions/podio/callback",
)
_REQUEST_TIMEOUT = (10, 30)


def _client_credentials() -> tuple[str, str]:
    client_id = os.getenv("PODIO_CLIENT_ID", "").strip()
    client_secret = os.getenv("PODIO_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ValueError("Podio Client ID and Client Secret are not configured on the backend")
    return client_id, client_secret


def _db():
    db = get_db_manager()
    if db is None:
        raise RuntimeError("Database is unavailable for Podio connection storage")
    return db


def _setting(key: str) -> str | None:
    row = _db().execute_query(
        "SELECT setting_value FROM app_settings WHERE setting_key = %s",
        (key,), fetchone=True,
    )
    if not row:
        return None
    return row.get("setting_value") if isinstance(row, dict) else row[0]


def _save_setting(key: str, value: str, category: str = "podio") -> None:
    _db().execute_query(
        """
        INSERT INTO app_settings (setting_key, setting_value, category, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (setting_key) DO UPDATE
            SET setting_value = EXCLUDED.setting_value,
                category = EXCLUDED.category,
                updated_at = NOW()
        """,
        (key, value, category), fetch=False,
    )


def _delete_setting(key: str) -> None:
    _db().execute_query("DELETE FROM app_settings WHERE setting_key = %s", (key,), fetch=False)


def status() -> dict[str, bool]:
    credentials_configured = bool(os.getenv("PODIO_CLIENT_ID") and os.getenv("PODIO_CLIENT_SECRET"))
    try:
        connected = credentials_configured and bool(_setting("podio_refresh_token_encrypted"))
    except Exception:
        connected = False
    return {"configured": credentials_configured, "connected": connected}


def create_authorization_url(username: str) -> str:
    client_id, _ = _client_credentials()
    state = secrets.token_urlsafe(32)
    _save_setting(f"podio_oauth_state:{state}", json.dumps({"username": username, "created": datetime.now(timezone.utc).isoformat()}), "podio_oauth_state")
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": PODIO_REDIRECT_URI,
        "response_type": "code",
        "scope": "app:read",
        "state": state,
    })
    return f"{PODIO_AUTHORIZE}?{query}"


def _exchange_token(payload: dict[str, str]) -> dict[str, Any]:
    response = requests.post(PODIO_TOKEN, data=payload, timeout=_REQUEST_TIMEOUT)
    if not response.ok:
        raise RuntimeError(f"Podio token request failed (HTTP {response.status_code})")
    data = response.json()
    if not data.get("access_token") or not data.get("refresh_token"):
        raise RuntimeError("Podio token response did not include the required tokens")
    return data


def complete_authorization(code: str, state: str) -> str:
    raw_state = _setting(f"podio_oauth_state:{state}")
    if not raw_state:
        raise ValueError("Podio authorization state is invalid or expired; try connecting again")
    try:
        state_data = json.loads(raw_state)
        created_at = datetime.fromisoformat(state_data["created"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("Podio authorization state is invalid; try connecting again") from exc
    if datetime.now(timezone.utc) - created_at > timedelta(minutes=15):
        _delete_setting(f"podio_oauth_state:{state}")
        raise ValueError("Podio authorization expired; try connecting again")

    client_id, client_secret = _client_credentials()
    tokens = _exchange_token({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": PODIO_REDIRECT_URI,
    })
    security = SecurityManager()
    if not security.fernet:
        raise RuntimeError("Podio tokens cannot be stored securely because ENCRYPTION_KEY is unavailable")
    _save_setting("podio_access_token_encrypted", security.encrypt_string(tokens["access_token"]))
    _save_setting("podio_refresh_token_encrypted", security.encrypt_string(tokens["refresh_token"]))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 28800)))
    _save_setting("podio_access_expires_at", expires_at.isoformat())
    _delete_setting(f"podio_oauth_state:{state}")
    return str(state_data["username"])


def _access_token() -> str:
    security = SecurityManager()
    access_encrypted = _setting("podio_access_token_encrypted")
    refresh_encrypted = _setting("podio_refresh_token_encrypted")
    expiry = _setting("podio_access_expires_at")
    if not refresh_encrypted:
        raise ValueError("Podio is not connected. An Owner must connect Podio first.")
    if access_encrypted and expiry:
        try:
            expires_at = datetime.fromisoformat(expiry)
            if expires_at - datetime.now(timezone.utc) > timedelta(minutes=1):
                return security.decrypt_string(access_encrypted)
        except ValueError:
            pass

    client_id, client_secret = _client_credentials()
    if not security.fernet:
        raise RuntimeError("Podio tokens cannot be refreshed securely because ENCRYPTION_KEY is unavailable")
    tokens = _exchange_token({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": security.decrypt_string(refresh_encrypted),
    })
    _save_setting("podio_access_token_encrypted", security.encrypt_string(tokens["access_token"]))
    _save_setting("podio_refresh_token_encrypted", security.encrypt_string(tokens["refresh_token"]))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 28800)))
    _save_setting("podio_access_expires_at", expires_at.isoformat())
    return tokens["access_token"]


def _item_text(item: dict[str, Any]) -> str:
    return normalize_details(json.dumps(item.get("fields", []), ensure_ascii=False, default=str))


def find_submitted_action(action_date: date, details: str) -> int | None:
    """Return a matching Podio item ID when the generated action report exists."""
    fields = _action_fields(details)
    team_leader = fields.get("Team Leader", "").strip()
    agent = fields.get("Agent Name", "").strip()
    if not team_leader or not agent:
        raise ValueError("Action details are missing the team leader or agent")

    marker = normalize_details(f"Action of [{agent}] was not sent by [{team_leader}]").casefold()
    date_marker = f"{action_date.month}/{action_date.day}/{action_date.year}"
    token = _access_token()
    headers = {"Authorization": f"OAuth2 {token}"}

    for offset in range(0, 500, 100):
        response = requests.post(
            f"{PODIO_API}/item/app/{PODIO_APP_ID}/filter/",
            json={"limit": 100, "offset": offset, "sort_by": "created_on", "sort_desc": True},
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise RuntimeError(f"Podio item lookup failed (HTTP {response.status_code})")
        payload = response.json()
        items = payload.get("items", [])
        for item in items:
            text = _item_text(item).casefold()
            if marker in text and normalize_details(date_marker).casefold() in text:
                return int(item["item_id"])
        if not items or offset + len(items) >= int(payload.get("filtered", payload.get("total", 0))):
            break
    return None


def callback_origin() -> str:
    parsed = urlparse(os.getenv("FRONTEND_URL", "https://vos-tool.up.railway.app"))
    return f"{parsed.scheme}://{parsed.netloc}"
