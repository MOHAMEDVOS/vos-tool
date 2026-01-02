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
    """Initialize database connection and create tables if needed."""
    try:
        db = get_db()
        if db is None:
            logger.warning("Database manager not available; running without PostgreSQL connection")
            return
        # Test connection
        db.execute_query("SELECT 1", fetch=True)
        logger.info("Database connection established")
        
        # Create tables if they don't exist
        create_tables_if_needed(db)
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def create_tables_if_needed(db):
    """Create essential tables if they don't exist."""
    try:
        # Best-effort: attempt to enable UUID helpers, but do not rely on them.
        try:
            db.execute_query('CREATE EXTENSION IF NOT EXISTS "pgcrypto";', fetch=False)
        except Exception as e:
            logger.warning(f"Could not ensure pgcrypto extension exists: {e}")

        # Create users table
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT (md5(random()::text || clock_timestamp()::text)::uuid),
            username TEXT UNIQUE NOT NULL,
            app_pass_hash TEXT NOT NULL,
            app_pass_salt TEXT,
            readymode_user TEXT,
            readymode_pass_encrypted TEXT,
            assemblyai_api_key_encrypted TEXT,
            daily_limit INTEGER DEFAULT 5000,
            role TEXT DEFAULT 'Auditor',
            created_by TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.execute_query(create_users_table, fetch=False)
        logger.info("✓ Users table created/verified")

        # Ensure required columns exist (safe no-op if already present)
        db.execute_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS app_pass_salt TEXT;", fetch=False)
        db.execute_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS readymode_user TEXT;", fetch=False)
        db.execute_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS readymode_pass_encrypted TEXT;", fetch=False)
        db.execute_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS assemblyai_api_key_encrypted TEXT;", fetch=False)
        db.execute_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by TEXT;", fetch=False)
        db.execute_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;", fetch=False)
        
        # Create user_sessions table
        create_sessions_table = """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id UUID PRIMARY KEY DEFAULT (md5(random()::text || clock_timestamp()::text)::uuid),
            username TEXT NOT NULL,
            session_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            ip_address INET,
            user_agent TEXT
        );
        """
        db.execute_query(create_sessions_table, fetch=False)
        logger.info("✓ User sessions table created/verified")

        db.execute_query("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;", fetch=False)
        db.execute_query("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS ip_address INET;", fetch=False)
        db.execute_query("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT;", fetch=False)
        
        # Create app_settings table
        create_settings_table = """
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.execute_query(create_settings_table, fetch=False)
        logger.info("✓ App settings table created/verified")

        db.execute_query("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;", fetch=False)
        
        logger.info("✅ Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        # Don't raise - let the app continue with fallback storage

