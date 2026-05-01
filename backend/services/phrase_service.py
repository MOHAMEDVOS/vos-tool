"""
Phrase management service.

Wraps lib.phrase_learning.PhraseLearningManager so the API layer stays
decoupled from the underlying singleton. All Owner-only business logic
is delegated here; the router handles auth + HTTP shape only.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.phrase_learning import get_phrase_learning_manager

logger = logging.getLogger(__name__)


def _manager():
    return get_phrase_learning_manager()


def get_stats() -> Dict[str, Any]:
    """Repository + pending statistics."""
    try:
        return _manager().get_repository_stats()
    except Exception as e:
        logger.error(f"get_stats failed: {e}", exc_info=True)
        return {
            "total_phrases": 0,
            "pending_count": 0,
            "auto_learned_count": 0,
            "categories": 0,
            "last_updated": "Unknown",
        }


def get_all_phrases() -> Dict[str, List[str]]:
    """All approved phrases grouped by category."""
    try:
        return _manager().get_repository_phrases()
    except Exception as e:
        logger.error(f"get_all_phrases failed: {e}", exc_info=True)
        return {}


def get_pending(status: str = "pending") -> List[Dict[str, Any]]:
    """Phrases awaiting review (status: pending|approved|rejected)."""
    try:
        return _manager().get_pending_phrases(status=status)
    except Exception as e:
        logger.error(f"get_pending failed: {e}", exc_info=True)
        return []


def add_phrase(phrase: str, category: str) -> Dict[str, Any]:
    """Add a single phrase manually. Returns {success, message, ...}."""
    try:
        return _manager().add_phrase_manually(phrase, category)
    except Exception as e:
        logger.error(f"add_phrase failed: {e}", exc_info=True)
        return {"success": False, "message": f"Error adding phrase: {e}"}


def add_phrases_bulk(phrases: List[str], category: str) -> Dict[str, Any]:
    """Add multiple phrases in one call. Mirrors the Streamlit textarea loop."""
    added: List[str] = []
    skipped: List[Dict[str, str]] = []
    mgr = _manager()
    for raw in phrases:
        phrase = (raw or "").strip()
        if not phrase:
            continue
        try:
            result = mgr.add_phrase_manually(phrase, category)
            if result.get("success"):
                added.append(phrase)
            else:
                skipped.append({"phrase": phrase, "reason": result.get("message", "unknown")})
        except Exception as e:
            skipped.append({"phrase": phrase, "reason": str(e)})
    return {
        "success": True,
        "added_count": len(added),
        "skipped_count": len(skipped),
        "added": added,
        "skipped": skipped,
    }


def approve(phrase_id: Union[int, str]) -> bool:
    try:
        return _manager().approve_phrase(phrase_id)
    except Exception as e:
        logger.error(f"approve failed: {e}", exc_info=True)
        return False


def reject(phrase_id: Union[int, str], reason: str = "") -> bool:
    try:
        return _manager().reject_phrase(phrase_id, reason)
    except Exception as e:
        logger.error(f"reject failed: {e}", exc_info=True)
        return False


def approve_all_pending() -> Dict[str, Any]:
    try:
        return _manager().approve_all_pending_phrases()
    except Exception as e:
        logger.error(f"approve_all_pending failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def approve_by_quality(min_quality_score: float = 0.90) -> Dict[str, Any]:
    try:
        return _manager().approve_by_quality_score(min_quality_score=min_quality_score)
    except Exception as e:
        logger.error(f"approve_by_quality failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def approve_by_category(category: str, min_quality_score: float = 0.80) -> Dict[str, Any]:
    try:
        return _manager().approve_by_category(category, min_quality_score=min_quality_score)
    except Exception as e:
        logger.error(f"approve_by_category failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def remove_duplicates() -> Dict[str, Any]:
    try:
        return _manager().remove_duplicate_phrases()
    except Exception as e:
        logger.error(f"remove_duplicates failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def update_settings(
    confidence_threshold: Optional[float] = None,
    frequency_threshold: Optional[int] = None,
    auto_approve_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        mgr = _manager()
        mgr.update_settings(
            confidence_threshold=confidence_threshold,
            frequency_threshold=frequency_threshold,
            auto_approve_threshold=auto_approve_threshold,
        )
        return {
            "success": True,
            "confidence_threshold": mgr.confidence_threshold,
            "frequency_threshold": mgr.frequency_threshold,
            "auto_approve_threshold": mgr.auto_approve_threshold,
        }
    except Exception as e:
        logger.error(f"update_settings failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def get_settings() -> Dict[str, Any]:
    try:
        mgr = _manager()
        return {
            "confidence_threshold": mgr.confidence_threshold,
            "frequency_threshold": mgr.frequency_threshold,
            "auto_approve_threshold": mgr.auto_approve_threshold,
        }
    except Exception as e:
        logger.error(f"get_settings failed: {e}", exc_info=True)
        return {}
