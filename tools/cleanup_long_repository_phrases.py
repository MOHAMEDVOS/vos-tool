import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Ensure project root is on sys.path so we can import lib.phrase_learning
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lib.phrase_learning import get_phrase_learning_manager


logger = logging.getLogger(__name__)


def cleanup_long_repository_phrases(max_chars: int, dry_run: bool) -> None:
    manager = get_phrase_learning_manager()
    repo_path = manager.repository_path

    if not os.path.exists(repo_path):
        print(f"Repository file not found at: {repo_path}")
        return

    with open(repo_path, "r", encoding="utf-8") as f:
        repository = json.load(f)

    phrases_by_category = repository.get("phrases", {}) or {}

    to_remove = []  # list of (category, phrase, length)
    for category, phrases in phrases_by_category.items():
        for phrase in phrases:
            if phrase and len(phrase) > max_chars:
                to_remove.append((category, phrase, len(phrase)))

    if not to_remove:
        print(f"No repository phrases longer than {max_chars} characters found.")
        return

    print(f"Found {len(to_remove)} repository phrases longer than {max_chars} characters:")
    preview_limit = 80
    max_listed = 50
    for idx, (category, phrase, length) in enumerate(to_remove):
        if idx >= max_listed:
            remaining = len(to_remove) - max_listed
            print(f"... and {remaining} more")
            break
        preview = (phrase or "").replace("\n", " ")
        if len(preview) > preview_limit:
            preview = preview[:preview_limit] + "..."
        print(f"- len={length}, category={category}, phrase='{preview}'")

    if dry_run:
        print("Dry run only. No changes applied.")
        return

    # Update JSON repository
    new_phrases_by_category = {}
    removed_count = 0
    for category, phrases in phrases_by_category.items():
        kept = []
        for phrase in phrases:
            if phrase and len(phrase) > max_chars:
                removed_count += 1
            else:
                kept.append(phrase)
        new_phrases_by_category[category] = kept

    repository["phrases"] = new_phrases_by_category
    repository["last_updated"] = datetime.now().isoformat()

    with open(repo_path, "w", encoding="utf-8") as f:
        json.dump(repository, f, indent=2)

    # Update SQLite repository_phrases table to stay in sync
    with manager._get_db_connection() as conn:
        for category, phrase, _ in to_remove:
            clean_phrase = (phrase or "").lower().strip()
            clean_category = (category or "").strip()
            conn.execute(
                "DELETE FROM repository_phrases WHERE phrase = ? AND category = ?",
                (clean_phrase, clean_category),
            )

    print(f"Completed repository cleanup. Removed {removed_count} phrases.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cleanup overly long phrases from the phrase repository (JSON + DB).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=100,
        help="Maximum allowed phrase length in characters (default: 100).",
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
    cleanup_long_repository_phrases(max_chars=args.max_chars, dry_run=dry_run)


if __name__ == "__main__":
    main()
