"""Persistent claims for ReadyMode recordings selected for audit."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from backend.core.database import get_db

CLAIM_LEASE = timedelta(hours=6)

# An audited recording stays audited even when a later re-audit of it fails.
_RELEASED_STATUS = "CASE WHEN status = 'audited' THEN 'audited' ELSE 'failed' END"


def claim_recordings(
    username: str,
    dialer_host: str,
    recording_ids: list[str],
    run_id: str,
    force_reaudit: bool = False,
) -> set[str]:
    """Atomically claim unprocessed recordings.

    force_reaudit takes over any recording, including audited ones and ones a crashed run
    left "processing". Safe because a user can't run two audits on one dialer at once.
    """
    ids = list(dict.fromkeys(recording_id for recording_id in recording_ids if recording_id))
    if not ids:
        return set()

    db = _database()
    lease = _timestamp(db, datetime.now(timezone.utc) + CLAIM_LEASE)
    id_marks = _marks(ids)

    db.execute_query(
        _sql(db, f"""UPDATE readymode_recordings
            SET status = CASE WHEN status = 'audited' THEN status ELSE 'processing' END,
                run_id = %s, lease_expires_at = %s, updated_at = CURRENT_TIMESTAMP
            WHERE username = %s AND dialer_host = %s
              AND recording_id IN ({id_marks})
              AND (
                status = 'failed'
                OR (status = 'processing'
                    AND (lease_expires_at IS NULL OR lease_expires_at < CURRENT_TIMESTAMP))
                OR %s = 1
              )"""),
        params=(run_id, lease, username, dialer_host, *ids, int(force_reaudit)),
        fetch=False,
    )
    db.execute_values_batch(
        """INSERT INTO readymode_recordings
            (username, dialer_host, recording_id, status, run_id, lease_expires_at)
            VALUES %s ON CONFLICT (username, dialer_host, recording_id) DO NOTHING""",
        [(username, dialer_host, recording_id, "processing", run_id, lease) for recording_id in ids],
    )
    rows = db.execute_query(
        _sql(db, f"""SELECT recording_id FROM readymode_recordings
            WHERE username = %s AND dialer_host = %s AND run_id = %s
              AND recording_id IN ({id_marks})"""),
        params=(username, dialer_host, run_id, *ids),
        fetch=True,
    )
    return {row["recording_id"] for row in rows or []}


def mark_recordings_audited(
    username: str,
    recordings: list[dict[str, str]],
    run_id: str,
) -> int:
    """Mark only recordings claimed by this run as successfully audited."""
    return _update_recordings(username, recordings, run_id, "'audited'")


def release_recordings(
    username: str,
    recordings: list[dict[str, str]],
    run_id: str,
) -> int:
    """Release failed work so a later request can retry it."""
    return _update_recordings(username, recordings, run_id, _RELEASED_STATUS)


def release_unfinished_claims() -> int:
    """Release every claim still held, for startup.

    The backend runs one uvicorn worker (backend/entrypoint.sh), so at boot no run is in
    flight and any held claim belongs to a run that died with the previous process.
    """
    return _database().execute_query(
        f"""UPDATE readymode_recordings
            SET status = {_RELEASED_STATUS}, run_id = NULL, lease_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE run_id IS NOT NULL""",
        fetch=False,
    )


def _update_recordings(username: str, recordings: list[dict[str, str]], run_id: str, new_status: str) -> int:
    ids_by_host: dict[str, list[str]] = defaultdict(list)
    for recording in recordings:
        if recording.get("dialer_host") and recording.get("recording_id"):
            ids_by_host[recording["dialer_host"]].append(recording["recording_id"])

    db = _database()
    total_updated = 0
    for dialer_host, host_ids in ids_by_host.items():
        ids = list(dict.fromkeys(host_ids))
        total_updated += db.execute_query(
            _sql(db, f"""UPDATE readymode_recordings
                SET status = {new_status}, run_id = NULL, lease_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE username = %s AND dialer_host = %s AND run_id = %s
                  AND recording_id IN ({_marks(ids)})"""),
            params=(username, dialer_host, run_id, *ids),
            fetch=False,
        )
    return total_updated


def _is_sqlite(db) -> bool:
    return getattr(db, "db_type", "postgresql") == "sqlite"


def _sql(db, query: str) -> str:
    """Queries are written with %s placeholders; SQLite's execute_query needs ?."""
    return query.replace("%s", "?") if _is_sqlite(db) else query


def _marks(ids: list[str]) -> str:
    return ", ".join("%s" for _ in ids)


def _timestamp(db, value: datetime):
    """SQLite keeps timestamps as 'YYYY-MM-DD HH:MM:SS' text, which compares correctly with CURRENT_TIMESTAMP."""
    return value.strftime("%Y-%m-%d %H:%M:%S") if _is_sqlite(db) else value


def _database():
    db = get_db()
    if db is None:
        raise RuntimeError("ReadyMode recording deduplication requires the database")
    return db
