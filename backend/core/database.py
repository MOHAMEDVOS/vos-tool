"""
Database initialization for backend.
Uses the existing database manager from lib.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.database import get_db_manager
import logging

logger = logging.getLogger(__name__)

_db_manager = None


def get_db():
    """Get database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = get_db_manager()
    return _db_manager


def init_db():
    """Initialize database connection."""
    try:
        db = get_db()
        if db is None:
            logger.warning("Database manager not available; running without PostgreSQL connection")
            return
        # Test connection
        db.execute_query("SELECT 1", fetch=True)
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

