#!/usr/bin/env python3
"""One-time backfill: fix wrong/empty "Dialer Name" on existing audit records.

Background
----------
Dual-dialer runs used to tag every call with dialer 1's name (see the fix in
processing/batch_engine.py + audio_pipeline/audio_processor.py). The wrong value
was persisted into the JSONB columns, so already-saved audits stay wrong until
re-derived from the file path. This script does that re-derivation.

Storage:
  * agent_audit_results.metadata           JSONB, key "Dialer Name"
  * lite_audit_results.detection_results   JSONB, key "dialer_name"
Both tables carry file_path, which encodes the dialer:
  * single-dialer: ".../{agent}-{date}_{counter} {dialer}/file.mp3"
  * dual-dialer:   ".../{agent}-{date}_{counter}/{dialer}/file.mp3"

Safety
------
Dry-run by default — prints what WOULD change, writes nothing. Pass --apply to
commit. A row is only touched when the path yields a NON-EMPTY dialer that
DIFFERS from what's stored (so good rows are never blanked).

Usage
-----
  # local (needs DATABASE_URL pointing at the Railway PG, e.g. the public proxy URL)
  python scripts/backfill_dialer_names.py                 # dry-run, all users
  python scripts/backfill_dialer_names.py --user alice    # dry-run, one user
  python scripts/backfill_dialer_names.py --apply         # write changes

  # as a Railway one-off (DATABASE_URL already in the backend env)
  railway run python scripts/backfill_dialer_names.py --apply
"""
import argparse
import json
import os
import re
import sys
from pathlib import PurePosixPath, PureWindowsPath

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    sys.exit("psycopg2 not installed. Run inside the backend env (pip install psycopg2-binary).")


def _parent_name(file_path: str) -> str:
    """Folder name containing the file, robust to / or \\ separators."""
    if not file_path:
        return ""
    cls = PureWindowsPath if "\\" in file_path else PurePosixPath
    return cls(file_path).parent.name


def derive_dialer_from_path(file_path: str) -> str:
    """Mirror of processing.batch_engine.extract_dialer_name_from_path (kept standalone
    so this script has no heavy app imports). Handles single + dual-dialer layouts."""
    parent = _parent_name(file_path)
    if not parent:
        return ""
    # single-dialer: "{agent}-{date}_{counter} {dialer}" -> token after last space
    if " " in parent:
        cand = parent.rsplit(" ", 1)[1].strip().rstrip("/\\")
        if cand:
            return cand
        return ""
    # dual-dialer: per-dialer subfolder; parent name IS the dialer, unless it's
    # itself a run folder ("{name}-{date}_{counter}")
    if not re.search(r"-\d{4}-\d{2}-\d{2}_\d+$", parent):
        return parent.strip().rstrip("/\\")
    return ""


def _load_json(val):
    if val is None:
        return {}
    if isinstance(val, dict):
        return dict(val)
    try:
        return json.loads(val)
    except Exception:
        return {}


def backfill_table(cur, table, json_col, dialer_key, user, apply):
    where = "file_path IS NOT NULL AND file_path <> ''"
    params = []
    if user:
        where += " AND username = %s"
        params.append(user)
    cur.execute(f"SELECT id, file_path, {json_col} FROM {table} WHERE {where}", params)
    rows = cur.fetchall()

    changed = 0
    samples = []
    updates = []  # (new_json_str, id)
    for row in rows:
        new_dialer = derive_dialer_from_path(row["file_path"])
        if not new_dialer:
            continue  # never blank an existing value when path is inconclusive
        data = _load_json(row[json_col])
        old = (data.get(dialer_key) or "").strip()
        if old == new_dialer:
            continue
        data[dialer_key] = new_dialer
        updates.append((json.dumps(data, allow_nan=False), row["id"]))
        changed += 1
        if len(samples) < 8:
            samples.append((old or "<empty>", new_dialer, row["file_path"]))

    print(f"\n=== {table} ({json_col}->{dialer_key!r}) ===")
    print(f"  scanned: {len(rows)}   would change: {changed}")
    for old, new, fp in samples:
        print(f"    {old:>10s} -> {new:<10s}  {fp}")
    if changed > len(samples):
        print(f"    ... and {changed - len(samples)} more")

    if apply and updates:
        cur.executemany(
            f"UPDATE {table} SET {json_col} = %s::jsonb WHERE id = %s", updates
        )
        print(f"  APPLIED {len(updates)} updates")
    return changed


def main():
    ap = argparse.ArgumentParser(description="Backfill Dialer Name on existing audits")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--user", help="limit to a single username")
    args = ap.parse_args()

    dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not dsn:
        sys.exit("DATABASE_URL not set.")

    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            total = 0
            total += backfill_table(cur, "agent_audit_results", "metadata", "Dialer Name", args.user, args.apply)
            total += backfill_table(cur, "lite_audit_results", "detection_results", "dialer_name", args.user, args.apply)
        if args.apply:
            conn.commit()
            print(f"\nDONE — committed. Total rows changed: {total}")
        else:
            conn.rollback()
            print(f"\nDRY-RUN — nothing written. Rerun with --apply to fix {total} rows.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
