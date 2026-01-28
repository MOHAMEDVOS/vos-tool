#!/usr/bin/env python3
"""
Migration script to add 'feedback' column to agent_audit_results table if it doesn't exist.
Surfaces LLM reasoning as a first-class citizen in the database.
"""

import os
import sys
import logging
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database manager
try:
    from lib.database import get_db_manager
except ImportError:
    logger.error("Failed to import database manager. Make sure you're running from the project root.")
    sys.exit(1)


def migrate_database():
    """Add feedback column to agent_audit_results table and backfill from metadata."""
    logger.info("=" * 60)
    logger.info("ADDING FEEDBACK COLUMN TO agent_audit_results TABLE")
    logger.info("=" * 60)
    
    db_manager = get_db_manager()
    if not db_manager:
        logger.error("Database manager not available")
        return False
    
    is_postgres = db_manager.db_type == 'postgresql'
    
    try:
        # 1. Add column if missing
        if is_postgres:
            # PostgreSQL check
            check_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'agent_audit_results' AND column_name = 'feedback';
            """
            add_query = "ALTER TABLE agent_audit_results ADD COLUMN feedback TEXT;"
        else:
            # SQLite check
            check_query = "PRAGMA table_info(agent_audit_results);"
            add_query = "ALTER TABLE agent_audit_results ADD COLUMN feedback TEXT;"

        results = db_manager.execute_query(check_query)
        
        column_exists = False
        if is_postgres:
            column_exists = len(results) > 0
        else:
            column_exists = any(row[1] == 'feedback' if isinstance(row, (list, tuple)) else row.get('name') == 'feedback' for row in results)
            
        if not column_exists:
            logger.info("Adding 'feedback' column...")
            db_manager.execute_query(add_query, fetch=False)
            logger.info("✓ Column 'feedback' added successfully.")
        else:
            logger.info("✓ Column 'feedback' already exists.")

        # 2. Backfill from metadata JSONB
        logger.info("Backfilling feedback from metadata...")
        
        if is_postgres:
            # PostgreSQL optimized backfill using JSONB operators
            backfill_query = """
                UPDATE agent_audit_results 
                SET feedback = metadata->>'feedback' 
                WHERE feedback IS NULL AND metadata ? 'feedback';
            """
            rows_updated = db_manager.execute_query(backfill_query, fetch=False)
            logger.info(f"✓ Backfilled {rows_updated} records from metadata (PostgreSQL).")
        else:
            # SQLite backfill (less optimized, row by row if needed, but let's try JSON extraction)
            # SQLite has json_extract since 3.38.0
            try:
                backfill_query = """
                    UPDATE agent_audit_results 
                    SET feedback = json_extract(metadata, '$.feedback') 
                    WHERE feedback IS NULL AND json_extract(metadata, '$.feedback') IS NOT NULL;
                """
                rows_updated = db_manager.execute_query(backfill_query, fetch=False)
                logger.info(f"✓ Backfilled {rows_updated} records from metadata (SQLite).")
            except Exception as e:
                logger.warning(f"SQLite json_extract backfill failed (likely old version): {e}")
                logger.info("Skipping backfill for SQLite.")

        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False


def main():
    """Main function."""
    success = migrate_database()
    
    if success:
        logger.info("=" * 60)
        logger.info("✓ Database migration completed successfully!")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("✗ Database migration failed!")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
