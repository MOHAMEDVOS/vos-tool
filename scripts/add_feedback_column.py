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
            # PostgreSQL optimized backfill
            # 1. Direct feedback field
            backfill_query_1 = """
                UPDATE agent_audit_results 
                SET feedback = metadata->>'feedback' 
                WHERE feedback IS NULL AND metadata ? 'feedback' AND metadata->>'feedback' IS NOT NULL;
            """
            
            # 2. Extract from matched_phrases for "Yes" if feedback is missing
            backfill_query_2 = """
                UPDATE agent_audit_results 
                SET feedback = 'Detected match: ' || (metadata->'matched_phrases'->0->>'phrase') || 
                              ' (' || (metadata->'matched_phrases'->0->>'match_type') || ')'
                WHERE feedback IS NULL 
                AND metadata->'matched_phrases' IS NOT NULL 
                AND jsonb_array_length(metadata->'matched_phrases') > 0;
            """

            # 3. Handle "No" cases with a generic message if no feedback exists
            backfill_query_3 = """
                UPDATE agent_audit_results 
                SET feedback = 'No rebuttal detected.' 
                WHERE feedback IS NULL AND rebuttal_detection = 'No';
            """

            rows1 = db_manager.execute_query(backfill_query_1, fetch=False)
            rows2 = db_manager.execute_query(backfill_query_2, fetch=False)
            rows3 = db_manager.execute_query(backfill_query_3, fetch=False)
            logger.info(f"✓ Backfilled PostgreSQL: {rows1} from direct feedback, {rows2} from matches, {rows3} from defaults.")
        else:
            # SQLite backfill
            logger.info("Attempting SQLite backfill...")
            try:
                # 1. Direct feedback
                db_manager.execute_query("""
                    UPDATE agent_audit_results 
                    SET feedback = json_extract(metadata, '$.feedback') 
                    WHERE feedback IS NULL AND json_extract(metadata, '$.feedback') IS NOT NULL;
                """, fetch=False)
                
                # 2. Match info (best effort for SQLite)
                db_manager.execute_query("""
                    UPDATE agent_audit_results 
                    SET feedback = 'Detected match: ' || json_extract(metadata, '$.matched_phrases[0].phrase')
                    WHERE feedback IS NULL AND json_extract(metadata, '$.matched_phrases[0]') IS NOT NULL;
                """, fetch=False)

                # 3. Default "No"
                db_manager.execute_query("""
                    UPDATE agent_audit_results 
                    SET feedback = 'No rebuttal detected.' 
                    WHERE feedback IS NULL AND rebuttal_detection = 'No';
                """, fetch=False)
            except Exception as e:
                logger.warning(f"SQLite backfill failed or partially failed: {e}")

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
