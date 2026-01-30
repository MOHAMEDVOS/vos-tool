"""
Create jobs table for async job tracking.
Run this once to set up the database.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.database import get_db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_jobs_table():
    """Create jobs table for Celery task tracking."""
    db = get_db_manager()
    
    if not db:
        logger.error("Could not connect to database")
        return False
    
    # Create jobs table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        job_type VARCHAR(50) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        progress FLOAT DEFAULT 0.0,
        metadata JSONB,
        result JSONB,
        error TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        completed_at TIMESTAMP WITH TIME ZONE
    );
    """
    
    # Create indexes for performance
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);"
    ]
    
    try:
        logger.info("Creating jobs table...")
        db.execute_query(create_table_sql, fetch=False)
        logger.info("✅ Jobs table created")
        
        logger.info("Creating indexes...")
        for idx_sql in create_indexes_sql:
            db.execute_query(idx_sql, fetch=False)
        logger.info("✅ Indexes created")
        
        # Verify table exists
        verify_sql = "SELECT COUNT(*) as count FROM jobs;"
        result = db.execute_query(verify_sql, fetchone=True)
        logger.info(f"✅ Table verified. Current job count: {result['count']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create jobs table: {e}")
        return False

if __name__ == "__main__":
    success = create_jobs_table()
    if success:
        print("\n✅ Database setup complete!")
    else:
        print("\n❌ Database setup failed. Check logs above.")
        sys.exit(1)
