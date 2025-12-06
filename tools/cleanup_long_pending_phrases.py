import argparse
import logging
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lib.phrase_learning import get_phrase_learning_manager


logger = logging.getLogger(__name__)


def cleanup_long_pending_phrases(max_chars: int, mode: str, dry_run: bool) -> None:
    manager = get_phrase_learning_manager()

    with manager._get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, phrase, category, length(phrase) FROM pending_phrases "
            "WHERE status = 'pending' AND length(phrase) > ?",
            (max_chars,),
        )
        rows = cursor.fetchall()

    if not rows:
        print(f"No pending phrases longer than {max_chars} characters found.")
        return

    print(f"Found {len(rows)} pending phrases longer than {max_chars} characters:")
    for phrase_id, phrase, category, length in rows:
        preview = (phrase or "").replace("\n", " ")
        if len(preview) > 80:
            preview = preview[:80] + "..."
        print(f"- id={phrase_id}, len={length}, category={category}, phrase='{preview}'")

    if dry_run:
        print("Dry run only. No changes applied.")
        return

    with manager._get_db_connection() as conn:
        processed = 0
        for phrase_id, phrase, category, length in rows:
            if mode == "blacklist":
                conn.execute(
                    "INSERT OR IGNORE INTO phrase_blacklist (phrase, category, reason) VALUES (?, ?, ?)",
                    (phrase, category, f"auto_cleanup_too_long_phrase_{max_chars}"),
                )
                conn.execute(
                    "UPDATE pending_phrases SET status = 'rejected' WHERE id = ?",
                    (phrase_id,),
                )
            elif mode == "delete":
                conn.execute(
                    "DELETE FROM pending_phrases WHERE id = ?",
                    (phrase_id,),
                )
            processed += 1

    print(f"Completed cleanup in mode='{mode}'. Processed {processed} phrases.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cleanup overly long pending phrases from the phrase learning database.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=100,
        help="Maximum allowed phrase length in characters (default: 100).",
    )
    parser.add_argument(
        "--mode",
        choices=["blacklist", "delete"],
        default="blacklist",
        help="Cleanup mode: 'blacklist' (default) or 'delete'.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. If omitted, runs in dry-run mode and makes no changes.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    dry_run = not args.apply
    cleanup_long_pending_phrases(max_chars=args.max_chars, mode=args.mode, dry_run=dry_run)


if __name__ == "__main__":
    main()
