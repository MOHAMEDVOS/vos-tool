"""Pull a read-only evaluation sample out of the audit database.

Usage:
    DATABASE_URL='postgresql://...' .venv/bin/python scripts/rebuttal_eval/pull_sample.py \
        --no-count 300 --yes-count 50 --out eval_data/sample.jsonl

Reads only. Never writes to the source database.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dialogue_utils import agent_text, label_style, parse_turns  # noqa: E402

COLUMNS = """
    id, username, agent_name, file_name, file_path,
    releasing_detection, late_hello_detection, rebuttal_detection,
    timestamp, call_duration, transcript, confidence_score, feedback, metadata
"""

# Newest first: the complaint is about a recent run, and phrase library /
# thresholds drift over time, so old calls are not the population of interest.
QUERY = f"""
    SELECT {COLUMNS}
    FROM agent_audit_results
    WHERE rebuttal_detection = %s
    ORDER BY created_at DESC
    LIMIT %s
"""


def resolve_dsn() -> str:
    for var in ("DATABASE_URL", "POSTGRES_URL", "DATABASE_PUBLIC_URL", "POSTGRES_PUBLIC_URL"):
        dsn = os.getenv(var)
        if dsn:
            return dsn
    sys.exit(
        "No database URL found.\n"
        "Set DATABASE_URL to the Railway Postgres connection string:\n"
        "  Railway -> Postgres service -> Variables -> DATABASE_URL\n"
        "Then re-run:  DATABASE_URL='postgresql://...' .venv/bin/python "
        "scripts/rebuttal_eval/pull_sample.py"
    )


def row_to_record(row: dict, cohort: str) -> dict:
    dialogue = row.get("transcript") or ""
    turns = parse_turns(dialogue)
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except (ValueError, TypeError):
            meta = {}

    ts = row.get("timestamp")
    return {
        "id": str(row["id"]),
        "cohort": cohort,
        "agent_name": row.get("agent_name"),
        "file_name": row.get("file_name"),
        "stored_verdict": row.get("rebuttal_detection"),
        "releasing": row.get("releasing_detection"),
        "late_hello": row.get("late_hello_detection"),
        "call_duration": float(row["call_duration"]) if row.get("call_duration") is not None else None,
        "stored_confidence": float(row["confidence_score"]) if row.get("confidence_score") is not None else None,
        "feedback": row.get("feedback"),
        "dialogue": dialogue,
        # --- diagnostics that need no judgement, computed once at pull time ---
        "transcript_empty": not dialogue.strip(),
        "label_style": label_style(dialogue),
        "turn_count": len(turns),
        "agent_turns": sum(1 for s, _ in turns if s == "Agent"),
        "owner_turns": sum(1 for s, _ in turns if s == "Owner"),
        "first_speaker": turns[0][0] if turns else None,
        "agent_char_count": len(agent_text(dialogue)),
        "disposition": meta.get("Disposition"),
        "dialer": meta.get("Dialer Name"),
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ts,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-count", type=int, default=300, help="calls stored as 'No' (the population being complained about)")
    ap.add_argument("--yes-count", type=int, default=50, help="calls stored as 'Yes' (control group)")
    ap.add_argument("--out", default="eval_data/sample.jsonl")
    args = ap.parse_args()

    dsn = resolve_dsn()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    with psycopg2.connect(dsn, connect_timeout=20) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT count(*) AS n FROM agent_audit_results")
            print(f"agent_audit_results total rows: {cur.fetchone()['n']}")

            cur.execute(
                "SELECT rebuttal_detection AS v, count(*) AS n "
                "FROM agent_audit_results GROUP BY 1 ORDER BY 2 DESC"
            )
            print("verdict distribution:")
            for r in cur.fetchall():
                print(f"  {str(r['v']):>6} : {r['n']}")

            for verdict, limit, cohort in (("No", args.no_count, "no"), ("Yes", args.yes_count, "yes_control")):
                if limit <= 0:
                    continue
                cur.execute(QUERY, (verdict, limit))
                rows = cur.fetchall()
                print(f"pulled {len(rows)} rows for verdict={verdict!r}")
                records.extend(row_to_record(dict(r), cohort) for r in rows)

    with out_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nwrote {len(records)} records -> {out_path}")
    summarize(records)


def summarize(records: list[dict]) -> None:
    """The free answers -- these need no LLM and no human."""
    no_rows = [r for r in records if r["cohort"] == "no"]
    if not no_rows:
        return
    total = len(no_rows)
    empty = sum(1 for r in no_rows if r["transcript_empty"])
    styles: dict[str, int] = {}
    for r in no_rows:
        styles[r["label_style"]] = styles.get(r["label_style"], 0) + 1
    owner_first = sum(1 for r in no_rows if r["first_speaker"] == "Owner")
    releasing = sum(1 for r in no_rows if r.get("releasing") == "Yes")

    def pct(n: int) -> str:
        return f"{n:>4} / {total}  ({100.0 * n / total:5.1f}%)"

    print("\n--- 'No Rebuttal' cohort, no judgement required ---")
    print(f"empty transcript (never analysed) : {pct(empty)}")
    print(f"releasing=Yes (detection skipped) : {pct(releasing)}")
    print(f"owner spoke first (swap risk)     : {pct(owner_first)}")
    print("speaker label style:")
    for style, n in sorted(styles.items(), key=lambda kv: -kv[1]):
        note = {
            "letter": "diarization - identity is a positional guess",
            "named": "multichannel - identity trustworthy",
            "none": "no speaker structure - objection gate cannot run",
        }.get(style, "")
        print(f"  {style:>6} : {pct(n)}  {note}")


if __name__ == "__main__":
    main()
