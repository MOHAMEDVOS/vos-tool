"""Persistent claims for ReadyMode recordings selected for audit."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from backend.core.database import get_db

CLAIM_LEASE = timedelta(hours=6)


def claim_recordings(
    username: str,
    dialer_host: str,
    recording_ids: list[str],
    run_id: str,
    force_reaudit: bool = False,
) -> set[str]:
    """Atomically claim unprocessed recordings, optionally reclaiming audited ones."""
    ids = list(dict.fromkeys(recording_id for recording_id in recording_ids if recording_id))
    if not ids:
        return set()

    db = _database()
    lease_expires_at = datetime.now(timezone.utc) + CLAIM_LEASE
    if getattr(db, "db_type", "postgresql") == "sqlite":
        _claim_sqlite(db, username, dialer_host, ids, run_id, lease_expires_at, force_reaudit)
        placeholders = ", ".join("?" for _ in ids)
        rows = db.execute_query(
            f"""SELECT recording_id FROM readymode_recordings
                WHERE username = ? AND dialer_host = ? AND run_id = ?
                AND recording_id IN ({placeholders})""",
            params=(username, dialer_host, run_id, *ids),
            fetch=True,
        )
    else:
        _claim_postgresql(db, username, dialer_host, ids, run_id, lease_expires_at, force_reaudit)
        rows = db.execute_query(
            """SELECT recording_id FROM readymode_recordings
               WHERE username = %s AND dialer_host = %s AND run_id = %s
                 AND recording_id = ANY(%s)""",
            params=(username, dialer_host, run_id, ids),
            fetch=True,
        )

    return {row["recording_id"] for row in rows or []}


def mark_recordings_audited(
    username: str,
    recordings: list[dict[str, str]],
    run_id: str,
) -> int:
    """Mark only recordings claimed by this run as successfully audited."""
    return _update_recordings(username, recordings, run_id, audited=True)


def release_recordings(
    username: str,
    recordings: list[dict[str, str]],
    run_id: str,
) -> int:
    """Release failed work so a later request can retry it."""
    return _update_recordings(username, recordings, run_id, audited=False)


def _claim_sqlite(db, username, dialer_host, ids, run_id, lease_expires_at, force_reaudit):
    placeholders = ", ".join("?" for _ in ids)
    db.execute_query(
        f"""UPDATE readymode_recordings
            SET status = CASE WHEN status = 'audited' THEN status ELSE 'processing' END,
                run_id = ?, lease_expires_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE username = ? AND dialer_host = ?
              AND recording_id IN ({placeholders})
              AND (
                status = 'failed'
                OR (status = 'processing'
                    AND (lease_expires_at IS NULL OR lease_expires_at < CURRENT_TIMESTAMP))
                OR (? = 1 AND status = 'audited'
                    AND (run_id IS NULL OR lease_expires_at < CURRENT_TIMESTAMP))
              )""",
        params=(
            run_id,
            lease_expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            username,
            dialer_host,
            *ids,
            int(force_reaudit),
        ),
        fetch=False,
    )
    db.execute_many(
        """INSERT INTO readymode_recordings
            (username, dialer_host, recording_id, status, run_id, lease_expires_at)
            VALUES (?, ?, ?, 'processing', ?, ?)
            ON CONFLICT(username, dialer_host, recording_id) DO NOTHING""",
        [
            (
                username,
                dialer_host,
                recording_id,
                run_id,
                lease_expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for recording_id in ids
        ],
    )


def _claim_postgresql(db, username, dialer_host, ids, run_id, lease_expires_at, force_reaudit):
    placeholders = ", ".join("%s" for _ in ids)
    db.execute_query(
        f"""UPDATE readymode_recordings
            SET status = CASE WHEN status = 'audited' THEN status ELSE 'processing' END,
                run_id = %s, lease_expires_at = %s, updated_at = NOW()
            WHERE username = %s AND dialer_host = %s
              AND recording_id IN ({placeholders})
              AND (
                status = 'failed'
                OR (status = 'processing'
                    AND (lease_expires_at IS NULL OR lease_expires_at < NOW()))
                OR (%s AND status = 'audited'
                    AND (run_id IS NULL OR lease_expires_at < NOW()))
              )""",
        params=(run_id, lease_expires_at, username, dialer_host, *ids, force_reaudit),
        fetch=False,
    )
    db.execute_values_batch(
        """INSERT INTO readymode_recordings
            (username, dialer_host, recording_id, status, run_id, lease_expires_at)
            VALUES %s ON CONFLICT (username, dialer_host, recording_id) DO NOTHING""",
        [
            (username, dialer_host, recording_id, "processing", run_id, lease_expires_at)
            for recording_id in ids
        ],
    )


def _update_recordings(username: str, recordings: list[dict[str, str]], run_id: str, audited: bool) -> int:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for recording in recordings:
        if recording.get("dialer_host") and recording.get("recording_id"):
            grouped[recording["dialer_host"]].append(recording)
    if not grouped:
        return 0

    db = _database()
    status = "audited" if audited else "failed"
    total_updated = 0
    for dialer_host, group in grouped.items():
        ids = list(dict.fromkeys(item["recording_id"] for item in group))
        if getattr(db, "db_type", "postgresql") == "sqlite":
            placeholders = ", ".join("?" for _ in ids)
            status_sql = "CASE WHEN status = 'audited' THEN 'audited' ELSE ? END" if not audited else "?"
            query = f"""UPDATE readymode_recordings
                SET status = {status_sql}, run_id = NULL, lease_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE username = ? AND dialer_host = ? AND run_id = ?
                  AND recording_id IN ({placeholders})"""
            params = (status, username, dialer_host, run_id, *ids)
        else:
            placeholders = ", ".join("%s" for _ in ids)
            status_sql = "CASE WHEN status = 'audited' THEN 'audited' ELSE %s END" if not audited else "%s"
            query = f"""UPDATE readymode_recordings
                SET status = {status_sql}, run_id = NULL, lease_expires_at = NULL,
                    updated_at = NOW()
                WHERE username = %s AND dialer_host = %s AND run_id = %s
                  AND recording_id IN ({placeholders})"""
            params = (status, username, dialer_host, run_id, *ids)
        total_updated += db.execute_query(query, params=params, fetch=False)
    return total_updated


def _database():
    db = get_db()
    if db is None:
        raise RuntimeError("ReadyMode recording deduplication requires the database")
    return db
