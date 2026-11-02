"""Persistence and coordination for the optional local ReadyMode worker."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.core.database import get_db

WORKER_ONLINE_SECONDS = 45
JOB_TIMEOUT_SECONDS = 600
JOB_LEASE_SECONDS = 300
SECRET_TTL_SECONDS = 3600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encrypt_secret_payload(payload: dict) -> str:
    from lib.security_utils import security_manager

    fernet = security_manager.fernet
    if fernet is None:
        raise RuntimeError("Worker secret encryption is unavailable")
    try:
        return fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")
    except Exception as exc:
        raise RuntimeError("Worker secret encryption failed") from exc


def _decrypt_secret_payload(ciphertext: str) -> dict:
    from lib.security_utils import security_manager

    fernet = security_manager.fernet
    if fernet is None:
        raise ValueError("Worker secret decryption is unavailable")
    try:
        decoded = fernet.decrypt(ciphertext.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Worker secret decryption failed") from exc
    if not isinstance(payload, dict):
        raise ValueError("Worker secret payload must be an object")
    return payload


def _db_type(db) -> str:
    return getattr(db, "db_type", "postgresql")


def _placeholder(db) -> str:
    return "?" if _db_type(db) == "sqlite" else "%s"


def get_execution_mode() -> str:
    from lib.app_settings_manager import app_settings

    mode = app_settings.get_setting("readymode_worker", "execution_mode", "railway")
    if not isinstance(mode, str):
        return "railway"
    if mode.startswith('"') and mode.endswith('"'):
        mode = mode[1:-1]
    return mode if mode in {"railway", "local_worker"} else "railway"


def issue_worker_token() -> str:
    token = secrets.token_urlsafe(32)
    db = get_db()
    marker = _timestamp()
    p = _placeholder(db)
    db.execute_query(
        f"""INSERT INTO readymode_worker_tokens (id, token_hash, created_at)
            VALUES (1, {p}, {p})
            ON CONFLICT (id) DO UPDATE SET token_hash = EXCLUDED.token_hash,
                created_at = EXCLUDED.created_at, last_seen_at = NULL""",
        params=(_token_hash(token), marker),
        fetch=False,
    )
    return token


def worker_status() -> dict[str, Any]:
    rows = get_db().execute_query(
        "SELECT created_at, last_seen_at FROM readymode_worker_tokens WHERE id = 1",
        fetch=True,
    ) or []
    row = rows[0] if rows else None
    last_seen = row.get("last_seen_at") if row else None
    online = False
    if last_seen:
        try:
            online = _now() - datetime.fromisoformat(last_seen) < timedelta(seconds=WORKER_ONLINE_SECONDS)
        except (TypeError, ValueError):
            online = False
    return {
        "configured": row is not None,
        "online": online,
        "last_seen_at": last_seen,
    }


def authenticate_worker(token: str) -> bool:
    if not token:
        return False
    db = get_db()
    digest = _token_hash(token)
    p = _placeholder(db)
    updated = db.execute_query(
        f"UPDATE readymode_worker_tokens SET last_seen_at = {p} WHERE id = 1 AND token_hash = {p}",
        params=(_timestamp(), digest),
        fetch=False,
    )
    return bool(updated)


def enqueue_worker_job(
    job_type: str,
    username: str,
    payload: dict,
    secret_payload: dict | None = None,
) -> str:
    db = get_db()
    _purge_expired_job_secrets()
    job_id = str(uuid.uuid4())
    now = _timestamp()
    p = _placeholder(db)
    if secret_payload is not None:
        ciphertext = _encrypt_secret_payload(secret_payload)
        expiry = _timestamp(_now() + timedelta(seconds=SECRET_TTL_SECONDS))
        db.execute_query(
            f"""INSERT INTO readymode_worker_job_secrets
                (job_id, secret_ciphertext, created_at, expires_at)
                VALUES ({p}, {p}, {p}, {p})""",
            params=(job_id, ciphertext, now, expiry),
            fetch=False,
        )
    try:
        db.execute_query(
            f"""INSERT INTO readymode_worker_jobs
                (job_id, job_type, username, payload_json, status, created_at, updated_at)
                VALUES ({p}, {p}, {p}, {p}, 'queued', {p}, {p})""",
            params=(job_id, job_type, username, json.dumps(payload), now, now),
            fetch=False,
        )
    except Exception:
        _delete_job_secret(job_id)
        raise
    return job_id


def enqueue_scoring_job(username: str, payload: dict) -> str:
    return enqueue_worker_job("scoring_gather", username, payload)


def claim_job() -> dict[str, Any] | None:
    db = get_db()
    _purge_expired_job_secrets()
    p = _placeholder(db)
    now = _timestamp()
    lease = _timestamp(_now() + timedelta(seconds=JOB_LEASE_SECONDS))
    claim_token = secrets.token_urlsafe(32)
    claim_hash = _token_hash(claim_token)

    if _db_type(db) == "sqlite":
        query = f"""UPDATE readymode_worker_jobs
            SET status = 'claimed', claim_token_hash = {p}, lease_expires_at = {p}, updated_at = {p}
            WHERE job_id = (
                SELECT job_id FROM readymode_worker_jobs
                WHERE status = 'queued'
                ORDER BY created_at LIMIT 1
            )
            """
        params = (claim_hash, lease, now)
    else:
        query = f"""WITH candidate AS (
                SELECT job_id FROM readymode_worker_jobs
                WHERE status = 'queued'
                ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED
            )
            UPDATE readymode_worker_jobs AS jobs
            SET status = 'claimed', claim_token_hash = {p}, lease_expires_at = {p}, updated_at = {p}
            FROM candidate WHERE jobs.job_id = candidate.job_id"""
        params = (claim_hash, lease, now)

    updated = db.execute_query(query, params=params, fetch=False)
    if not updated:
        return None
    rows = db.execute_query(
        f"""SELECT job_id, job_type, username, payload_json FROM readymode_worker_jobs
            WHERE claim_token_hash = {p} AND status = 'claimed'""",
        params=(claim_hash,),
        fetch=True,
    ) or []
    if not rows:
        return None
    row = rows[0]
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, ValueError):
        fail_job(row["job_id"], claim_token, "invalid_job_payload")
        return None

    from config import get_user_readymode_credentials

    try:
        rm_user, rm_password = get_user_readymode_credentials(row["username"])
    except Exception:
        fail_job(row["job_id"], claim_token, "readymode_credentials_lookup_failed")
        return None
    if not rm_user or not rm_password:
        fail_job(row["job_id"], claim_token, "readymode_credentials_missing")
        return None
    job = {
        "job_id": row["job_id"],
        "job_type": row["job_type"],
        "claim_token": claim_token,
        "payload": payload,
        "readymode_username": rm_user,
        "readymode_password": rm_password,
    }
    if row["job_type"] == "readymode_create_users":
        secret = _get_job_secret(row["job_id"])
        if secret is None:
            fail_job(row["job_id"], claim_token, "worker_secret_missing")
            return None
        job["secret_payload"] = secret
    return job


def _get_job_secret(job_id: str) -> dict[str, Any] | None:
    db = get_db()
    p = _placeholder(db)
    rows = db.execute_query(
        f"""SELECT secret_ciphertext FROM readymode_worker_job_secrets
            WHERE job_id = {p} AND expires_at > {p}""",
        params=(job_id, _timestamp()),
        fetch=True,
    ) or []
    if not rows:
        return None
    try:
        return _decrypt_secret_payload(rows[0]["secret_ciphertext"])
    except ValueError:
        return None


def _delete_job_secret(job_id: str) -> None:
    db = get_db()
    p = _placeholder(db)
    db.execute_query(
        f"DELETE FROM readymode_worker_job_secrets WHERE job_id = {p}",
        params=(job_id,),
        fetch=False,
    )


def _purge_expired_job_secrets() -> None:
    db = get_db()
    p = _placeholder(db)
    db.execute_query(
        f"DELETE FROM readymode_worker_job_secrets WHERE expires_at <= {p}",
        params=(_timestamp(),),
        fetch=False,
    )


def _release_job_recordings(job_id: str, username: str) -> None:
    db = get_db()
    p = _placeholder(db)
    rows = db.execute_query(
        f"""SELECT dialer_host, recording_id FROM readymode_recordings
            WHERE username = {p} AND run_id = {p}""",
        params=(username, job_id),
        fetch=True,
    ) or []
    if rows:
        from backend.services.readymode_recording_registry import release_recordings

        release_recordings(username, rows, job_id)


def get_claimed_job_context(job_id: str, claim_token: str) -> dict[str, Any] | None:
    db = get_db()
    p = _placeholder(db)
    now = _timestamp()
    rows = db.execute_query(
        f"""SELECT job_type, username, payload_json FROM readymode_worker_jobs
            WHERE job_id = {p} AND status = 'claimed' AND claim_token_hash = {p}
            AND lease_expires_at > {p}""",
        params=(job_id, _token_hash(claim_token), now),
        fetch=True,
    ) or []
    if not rows:
        return None
    row = rows[0]
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, ValueError):
        return None
    return {"job_type": row["job_type"], "username": row["username"], "payload": payload}


def recording_is_claimed(username: str, dialer_host: str, recording_id: str, job_id: str) -> bool:
    db = get_db()
    p = _placeholder(db)
    rows = db.execute_query(
        f"""SELECT recording_id FROM readymode_recordings
            WHERE username = {p} AND dialer_host = {p} AND recording_id = {p} AND run_id = {p}""",
        params=(username, dialer_host, recording_id, job_id),
        fetch=True,
    ) or []
    return bool(rows)


def get_job(job_id: str) -> dict[str, Any] | None:
    p = _placeholder(get_db())
    rows = get_db().execute_query(
        f"SELECT status, progress_message, result_json, error_code FROM readymode_worker_jobs WHERE job_id = {p}",
        params=(job_id,),
        fetch=True,
    ) or []
    if not rows:
        return None
    row = rows[0]
    result = row.get("result_json")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = None
    return {**row, "result_json": result}


def update_progress(job_id: str, claim_token: str, message: str) -> bool:
    db = get_db()
    p = _placeholder(db)
    now = _timestamp()
    updated = db.execute_query(
        f"""UPDATE readymode_worker_jobs SET progress_message = {p}, updated_at = {p},
            lease_expires_at = {p}
            WHERE job_id = {p} AND status = 'claimed' AND claim_token_hash = {p}
            AND lease_expires_at > {p}
            """,
        params=(message[:255], now, _timestamp(_now() + timedelta(seconds=JOB_LEASE_SECONDS)),
                job_id, _token_hash(claim_token), now),
        fetch=False,
    )
    return bool(updated)


def complete_job(job_id: str, claim_token: str, result: dict) -> bool:
    db = get_db()
    p = _placeholder(db)
    now = _timestamp()
    updated = db.execute_query(
        f"""UPDATE readymode_worker_jobs SET status = 'completed', result_json = {p},
            claim_token_hash = NULL, lease_expires_at = NULL, updated_at = {p}
            WHERE job_id = {p} AND status = 'claimed' AND claim_token_hash = {p}
            AND lease_expires_at > {p}
            """,
        params=(json.dumps(result), now, job_id, _token_hash(claim_token), now),
        fetch=False,
    )
    if updated:
        _delete_job_secret(job_id)
    return bool(updated)


def fail_job(job_id: str, claim_token: str, error_code: str) -> bool:
    db = get_db()
    p = _placeholder(db)
    rows = db.execute_query(
        f"SELECT username, job_type FROM readymode_worker_jobs WHERE job_id = {p}",
        params=(job_id,),
        fetch=True,
    ) or []
    now = _timestamp()
    updated = db.execute_query(
        f"""UPDATE readymode_worker_jobs SET status = 'failed', error_code = {p},
            claim_token_hash = NULL, lease_expires_at = NULL, updated_at = {p}
            WHERE job_id = {p} AND status = 'claimed' AND claim_token_hash = {p}
            AND lease_expires_at > {p}
            """,
        params=(error_code[:60], now, job_id, _token_hash(claim_token), now),
        fetch=False,
    )
    if updated:
        if rows and rows[0].get("job_type") == "readymode_recordings":
            _release_job_recordings(job_id, rows[0]["username"])
        _delete_job_secret(job_id)
    return bool(updated)


def discard_job(job_id: str) -> None:
    """Remove a finished job and its gathered call rows after VOS consumes the result."""
    db = get_db()
    p = _placeholder(db)
    rows = db.execute_query(
        f"SELECT username, job_type FROM readymode_worker_jobs WHERE job_id = {p}",
        params=(job_id,),
        fetch=True,
    ) or []
    if rows and rows[0].get("job_type") == "readymode_recordings":
        _release_job_recordings(job_id, rows[0]["username"])
    db.execute_query(
        f"DELETE FROM readymode_worker_jobs WHERE job_id = {p} AND status IN ('completed', 'failed')",
        params=(job_id,),
        fetch=False,
    )
    _delete_job_secret(job_id)


def abandon_job(job_id: str) -> None:
    """Stop a queued or leased job after the scoring request has timed out."""
    db = get_db()
    p = _placeholder(db)
    rows = db.execute_query(
        f"SELECT username, job_type FROM readymode_worker_jobs WHERE job_id = {p}",
        params=(job_id,),
        fetch=True,
    ) or []
    db.execute_query(
        f"""UPDATE readymode_worker_jobs SET status = 'failed', error_code = 'worker_timeout',
            claim_token_hash = NULL, lease_expires_at = NULL, updated_at = {p}
            WHERE job_id = {p} AND status IN ('queued', 'claimed')""",
        params=(_timestamp(), job_id),
        fetch=False,
    )
    if rows and rows[0].get("job_type") == "readymode_recordings":
        _release_job_recordings(job_id, rows[0]["username"])
    _delete_job_secret(job_id)


def wait_for_job(
    job_id: str,
    timeout: int = JOB_TIMEOUT_SECONDS,
    progress_callback=None,
    cancel_callback=None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_progress = None
    while time.monotonic() < deadline:
        if cancel_callback and cancel_callback():
            abandon_job(job_id)
            return {"status": "failed", "error_code": "job_cancelled"}
        job = get_job(job_id)
        if not job:
            return {"status": "failed", "error_code": "job_missing"}
        if job.get("progress_message") != last_progress:
            last_progress = job.get("progress_message")
            if last_progress and progress_callback:
                progress_callback(last_progress)
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.5)
    return {"status": "failed", "error_code": "worker_timeout"}
