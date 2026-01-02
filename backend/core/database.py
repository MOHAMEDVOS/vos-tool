"""
Database initialization for backend.
Uses the existing database manager from lib.
"""

import sys
from pathlib import Path
from typing import List

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


def _split_sql_statements(sql: str) -> List[str]:
    statements: List[str] = []
    buf: List[str] = []
    i = 0
    in_single = False
    in_double = False
    dollar_tag = None

    def _flush():
        s = ''.join(buf).strip()
        buf.clear()
        if s:
            statements.append(s)

    while i < len(sql):
        ch = sql[i]

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        if not in_single and not in_double and ch == '$':
            j = i + 1
            while j < len(sql) and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            if j < len(sql) and sql[j] == '$':
                tag = sql[i:j + 1]
                buf.append(tag)
                dollar_tag = tag
                i = j + 1
                continue

        if ch == "'" and not in_double:
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_single = not in_single
            buf.append(ch)
            i += 1
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue

        if ch == ';' and not in_single and not in_double:
            _flush()
            i += 1
            continue

        buf.append(ch)
        i += 1

    if buf:
        _flush()

    return statements


def _normalize_schema_sql(sql: str) -> str:
    sql = sql.replace('uuid_generate_v4()', '(md5(random()::text || clock_timestamp()::text)::uuid)')
    return sql


def _apply_schema_file(db, schema_path: Path):
    try:
        sql = schema_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to read schema file {schema_path}: {e}")
        return

    sql = _normalize_schema_sql(sql)
    for stmt in _split_sql_statements(sql):
        stmt_stripped = stmt.strip()
        if not stmt_stripped:
            continue

        upper = stmt_stripped.upper()

        if upper.startswith('GRANT '):
            continue
        if ' TO VOS_USER' in upper:
            continue
        if upper.startswith('INSERT INTO USERS '):
            continue
        if upper.startswith('CREATE EXTENSION IF NOT EXISTS "UUID-OSSP"'):
            continue

        if upper.startswith('CREATE EXTENSION'):
            try:
                db.execute_query(stmt_stripped, fetch=False)
            except Exception:
                pass
            continue

        try:
            db.execute_query(stmt_stripped, fetch=False)
        except Exception as e:
            logger.warning(f"Schema statement failed (continuing): {e}")


def _apply_full_schema(db):
    root_dir = Path(__file__).resolve().parent.parent.parent
    schema_files = [
        root_dir / 'cloud-migration' / 'init.sql',
        root_dir / 'cloud-migration' / 'migration_schema.sql',
    ]

    for schema_file in schema_files:
        if schema_file.exists():
            _apply_schema_file(db, schema_file)
        else:
            logger.warning(f"Schema file missing: {schema_file}")


def create_tables_if_needed(db):
    """Create essential tables if they don't exist."""
    try:
        try:
            db.execute_query('CREATE EXTENSION IF NOT EXISTS "pgcrypto";', fetch=False)
        except Exception as e:
            logger.warning(f"Could not ensure pgcrypto extension exists: {e}")
        try:
            db.execute_query('CREATE EXTENSION IF NOT EXISTS "pg_trgm";', fetch=False)
        except Exception:
            pass

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
            id UUID PRIMARY KEY DEFAULT (md5(random()::text || clock_timestamp()::text)::uuid),
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.execute_query(create_settings_table, fetch=False)
        logger.info("✓ App settings table created/verified")

        db.execute_query("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS id UUID;", fetch=False)
        db.execute_query("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS setting_value TEXT;", fetch=False)
        db.execute_query("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS category TEXT;", fetch=False)
        db.execute_query("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;", fetch=False)
        db.execute_query("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;", fetch=False)

        _apply_full_schema(db)
        
        logger.info("✅ Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        # Don't raise - let the app continue with fallback storage

