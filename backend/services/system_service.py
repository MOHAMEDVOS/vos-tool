"""
System service (gaps G7, G8, G10).

- G7: readonly-mode / migration status
- G8: UI-facing system health (CPU / mem / disk)
- G10: active sessions listing + invalidation for admins
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


def get_readonly_status() -> Dict[str, Any]:
    """Is the app currently in migration/readonly mode?"""
    try:
        from lib.migration_lock import is_application_read_only, get_migration_status
        return {
            "read_only": bool(is_application_read_only()),
            "migration_status": get_migration_status(),
        }
    except Exception as e:
        logger.error(f"get_readonly_status failed: {e}", exc_info=True)
        return {"read_only": False, "migration_status": None}


def get_system_health() -> Dict[str, Any]:
    """Lightweight host metrics used by the Settings > System Health tab."""
    try:
        import psutil
        process = psutil.Process()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "used_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            },
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except Exception as e:
        logger.error(f"get_system_health failed: {e}", exc_info=True)
        return {"cpu_percent": 0.0, "memory": {"percent": 0.0, "used_mb": 0.0}, "disk_percent": 0.0}


def list_active_sessions() -> List[Dict[str, Any]]:
    """All active sessions (admin view)."""
    try:
        from lib.dashboard_manager import session_manager
        sessions = session_manager.get_active_sessions()
        # Dict keyed by username -> list of session_info records
        return list(sessions.values())
    except Exception as e:
        logger.error(f"list_active_sessions failed: {e}", exc_info=True)
        return []


def invalidate_session(username: str, session_id: str = None) -> bool:
    try:
        from lib.dashboard_manager import session_manager
        return bool(session_manager.invalidate_session(username, session_id))
    except Exception as e:
        logger.error(f"invalidate_session failed: {e}", exc_info=True)
        return False


def caller_owns_recording(username: str, resolved: Path) -> bool:
    """Return True if the caller is allowed to access the resolved recording path.

    Allowed cases:
    1. File lives anywhere under RECORDINGS_ROOT (shared deployment — no per-user dirs).
    2. Filename appears in one of the caller's audit rows (agent or lite).
    """
    from config import RECORDINGS_ROOT
    from lib.dashboard_manager import dashboard_manager
    import json as _json

    recordings_dir = Path(RECORDINGS_ROOT)

    # Case 1: file is under the shared recordings root — always permitted
    try:
        resolved.relative_to(recordings_dir)
        return True
    except ValueError:
        pass

    # Case 2: file referenced in caller's audit data
    try:
        agent_data = dashboard_manager.get_combined_agent_audit_data(username)
        lite_data = dashboard_manager.get_combined_lite_audit_data(username)
        for df in (agent_data, lite_data):
            if df is None or df.empty:
                continue
            try:
                rows = _json.loads(df.to_json(orient="records", force_ascii=False))
            except Exception:
                continue
            for row in rows:
                fp = row.get("File Path") or row.get("file_path") or ""
                fn = row.get("File Name") or row.get("filename") or ""
                if fp and Path(fp) == resolved:
                    return True
                if fn and fn == resolved.name:
                    return True
    except Exception:
        pass

    return False


def get_word_timestamps(resolved: Path) -> list:
    """Fetch word-level timestamps from transcription_cache for a resolved audio file.

    Returns a list of {word, start, end, speaker} dicts with times in seconds.
    Returns [] if no cache entry or no words stored.
    """
    try:
        from lib.transcription_caching import TranscriptionCacheManager
        cache = TranscriptionCacheManager()
        if not cache.enabled:
            return []

        file_hash = cache.calculate_file_hash(resolved)
        if not file_hash:
            return []

        cached = cache.get_cached_transcript(file_hash)
        if not cached:
            return []

        raw = cached.get("raw_response") or {}
        words_raw = raw.get("words") or []

        result = []
        for w in words_raw:
            text = w.get("text") or w.get("word") or ""
            start_ms = w.get("start", 0)
            end_ms = w.get("end", 0)
            if not text:
                continue
            result.append({
                "word": text,
                "start": round(start_ms / 1000, 3),
                "end": round(end_ms / 1000, 3),
                "speaker": w.get("speaker"),
            })
        return result
    except Exception as e:
        logger.error(f"get_word_timestamps failed: {e}", exc_info=True)
        return []


def resolve_recording_path(file_path: str = None, filename: str = None, phone: str = None) -> Path | None:
    """3-priority audio file lookup for the React call review player.

    Priority 1: explicit file_path column value
    Priority 2: filename  → recursive search in RECORDINGS_ROOT
    Priority 3: phone     → recursive .mp3 search by digits in RECORDINGS_ROOT
    Returns a resolved Path or None.
    """
    from config import RECORDINGS_ROOT

    recordings_dir = Path(RECORDINGS_ROOT)

    # Priority 1 — direct path
    if file_path:
        p = Path(file_path)
        if p.exists() and p.is_file():
            return p

    # Priority 2 — filename search
    if filename and filename != 'Unknown':
        if recordings_dir.exists():
            for f in recordings_dir.rglob(filename):
                if f.is_file() and f.name == filename:
                    return f

    # Priority 3 — phone number match inside .mp3 filenames
    if phone and recordings_dir.exists():
        # Try formatted phone string first
        for f in recordings_dir.rglob("*.mp3"):
            if f.is_file() and phone in f.name:
                return f
        # Digits-only fallback
        clean = ''.join(c for c in phone if c.isdigit())
        if clean:
            for f in recordings_dir.rglob("*.mp3"):
                if f.is_file() and clean in ''.join(c for c in f.name if c.isdigit()):
                    return f

    return None
