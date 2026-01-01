#!/usr/bin/env python3
"""
Migration script to add 'source' column to rebuttal_phrases table if it doesn't exist.

This fixes the error: column "source" does not exist
"""

import os
import sys
import logging
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


def add_source_column_if_missing():
    """Add source column to rebuttal_phrases table if it doesn't exist."""
    logger.info("=" * 60)
    logger.info("ADDING SOURCE COLUMN TO rebuttal_phrases TABLE")
    logger.info("=" * 60)
    
    try:
        db_manager = get_db_manager()
        if not db_manager:
            logger.error("Database manager returned None")
            return False
        
        conn = db_manager.connection_pool.getconn()
        if not conn:
            logger.error("Failed to get connection from pool")
            return False
        
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'rebuttal_phrases' AND column_name = 'source';
        """)
        
        column_exists = cursor.fetchone() is not None
        
        if column_exists:
            logger.info("✓ Column 'source' already exists in rebuttal_phrases table")
            cursor.close()
            db_manager.connection_pool.putconn(conn)
            return True
        
        # Add the column
        logger.info("Adding 'source' column to rebuttal_phrases table...")
        cursor.execute("""
            ALTER TABLE rebuttal_phrases 
            ADD COLUMN source VARCHAR(50) DEFAULT 'manual';
        """)
        
        conn.commit()
        logger.info("✓ Successfully added 'source' column to rebuttal_phrases table")
        
        # Update existing rows to have 'manual' as default source
        cursor.execute("""
            UPDATE rebuttal_phrases 
            SET source = 'manual' 
            WHERE source IS NULL;
        """)
        
        conn.commit()
        logger.info("✓ Updated existing rows with default 'manual' source")
        
        cursor.close()
        db_manager.connection_pool.putconn(conn)
        
        return True
        
    except Exception as e:
        logger.error(f"Error adding source column: {e}", exc_info=True)
        if 'conn' in locals():
            try:
                conn.rollback()
                db_manager.connection_pool.putconn(conn)
            except:
                pass
        return False


def main():
    """Main function."""
    logger.info("Starting source column migration...")
    
    success = add_source_column_if_missing()
    
    if success:
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("Migration failed!")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

