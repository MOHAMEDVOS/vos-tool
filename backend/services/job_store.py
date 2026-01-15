"""Durable job storage for audio processing.

This module persists job state and results in PostgreSQL (or SQLite in dev) via
lib.database.DatabaseManager.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from backend.core.database import get_db

logger = logging.getLogger(__name__)


def _utc_iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def create_job(
    job_id: str,
    *,
    username: str,
    status: str,
    progress: float = 0.0,
    stage: Optional[str] = None,
    file_id: Optional[str] = None,
    file_path: Optional[str] = None,
    audit_type: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> None:
    db = get_db()
    options_payload: Any
    if options is None:
        options_payload = None
    elif getattr(db, "db_type", "postgresql") == "sqlite":
        options_payload = json.dumps(options)
    else:
        options_payload = json.dumps(options)

    if getattr(db, "db_type", "postgresql") == "sqlite":
        query = """
        INSERT INTO processing_jobs (
            job_id, username, status, progress, stage, file_id, file_path, audit_type,
            options_json, error, result_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
        """
        params = (
            job_id,
            username,
            status,
            float(progress),
            stage,
            file_id,
            file_path,
            audit_type,
            options_payload,
            _utc_iso_now(),
            _utc_iso_now(),
        )
    else:
        query = """
        INSERT INTO processing_jobs (
            job_id, username, status, progress, stage, file_id, file_path, audit_type,
            options_json, error, result_json, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NULL, NULL, NOW(), NOW())
        """
        params = (
            job_id,
            username,
            status,
            float(progress),
            stage,
            file_id,
            file_path,
            audit_type,
            options_payload,
        )

    db.execute_query(query, params=params, fetch=False)


def update_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    stage: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    db = get_db()

    fields: Dict[str, Any] = {}
    if status is not None:
        fields["status"] = status
    if progress is not None:
        fields["progress"] = float(progress)
    if stage is not None:
        fields["stage"] = stage
    if error is not None:
        fields["error"] = error

    if not fields:
        return

    if getattr(db, "db_type", "postgresql") == "sqlite":
        set_parts = []
        params_list = []
        for k, v in fields.items():
            set_parts.append(f"{k} = ?")
            params_list.append(v)
        set_parts.append("updated_at = ?")
        params_list.append(_utc_iso_now())
        params_list.append(job_id)
        query = f"UPDATE processing_jobs SET {', '.join(set_parts)} WHERE job_id = ?"
        db.execute_query(query, params=tuple(params_list), fetch=False)
        return

    set_parts = []
    params_list = []
    for k, v in fields.items():
        set_parts.append(f"{k} = %s")
        params_list.append(v)
    set_parts.append("updated_at = NOW()")

    query = f"UPDATE processing_jobs SET {', '.join(set_parts)} WHERE job_id = %s"
    params_list.append(job_id)
    db.execute_query(query, params=tuple(params_list), fetch=False)


def set_job_result(job_id: str, result: Dict[str, Any]) -> None:
    db = get_db()

    payload = json.dumps(result)

    if getattr(db, "db_type", "postgresql") == "sqlite":
        query = """
        UPDATE processing_jobs
        SET result_json = ?, updated_at = ?
        WHERE job_id = ?
        """
        params = (payload, _utc_iso_now(), job_id)
    else:
        query = """
        UPDATE processing_jobs
        SET result_json = %s::jsonb, updated_at = NOW()
        WHERE job_id = %s
        """
        params = (payload, job_id)

    db.execute_query(query, params=params, fetch=False)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()

    if getattr(db, "db_type", "postgresql") == "sqlite":
        query = "SELECT * FROM processing_jobs WHERE job_id = ?"
        rows = db.execute_query(query, params=(job_id,), fetch=True)
    else:
        query = "SELECT * FROM processing_jobs WHERE job_id = %s"
        rows = db.execute_query(query, params=(job_id,), fetch=True)

    if not rows:
        return None

    row = rows[0]

    # Normalize JSON columns
    options_val = row.get("options_json")
    if isinstance(options_val, str):
        try:
            row["options_json"] = json.loads(options_val)
        except Exception:
            pass

    result_val = row.get("result_json")
    if isinstance(result_val, str):
        try:
            row["result_json"] = json.loads(result_val)
        except Exception:
            pass

    return row
