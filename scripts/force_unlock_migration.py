"""
Force unlock migration locks (USE WITH CAUTION).

This script should only be used if:
1. You are certain no migration is actually running
2. A previous migration crashed and left stale locks
3. You have verified no other processes are accessing the database

WARNING: Force unlocking while a migration is running can cause data corruption!
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from lib.migration_lock import MigrationLock, MIGRATION_ADVISORY_LOCK_ID
    LOCK_AVAILABLE = True
except ImportError:
    logger.error("Migration lock system not available")
    sys.exit(1)

def force_unlock():
    """Force unlock all migration locks."""
    logger.warning("=" * 80)
    logger.warning("FORCE UNLOCK MIGRATION LOCKS")
    logger.warning("=" * 80)
    logger.warning("")
    logger.warning("WARNING: This will remove all migration locks!")
    logger.warning("Only use this if you are CERTAIN no migration is running.")
    logger.warning("")
    
    response = input("Are you sure you want to force unlock? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Unlock cancelled")
        return
    
    lock = MigrationLock()
    
    # Release file lock
    try:
        if lock.lock_file.exists():
            lock.release_file_lock()
            logger.info(f"Removed lock file: {lock.lock_file}")
        else:
            logger.info("No lock file found")
    except Exception as e:
        logger.error(f"Error removing lock file: {e}")
    
    # Release database lock
    try:
        import psycopg2
        DB_CONFIG = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB', 'vos_tool'),
            'user': os.getenv('POSTGRES_USER', 'vos_user'),
            'password': os.getenv('POSTGRES_PASSWORD', '')
        }
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Try to unlock (may fail if lock not held, that's OK)
        cursor.execute(
            "SELECT pg_advisory_unlock_all()"
        )
        cursor.execute(
            "SELECT pg_advisory_unlock(%s)",
            (MIGRATION_ADVISORY_LOCK_ID,)
        )
        conn.close()
        logger.info("Released database advisory locks")
    except Exception as e:
        logger.warning(f"Could not release database locks (may not be held): {e}")
    
    # Remove status file
    try:
        if lock.status_file.exists():
            lock.status_file.unlink()
            logger.info(f"Removed status file: {lock.status_file}")
    except Exception as e:
        logger.error(f"Error removing status file: {e}")
    
    logger.info("")
    logger.info("Force unlock complete!")
    logger.info("You can now run the migration again if needed.")

if __name__ == "__main__":
    force_unlock()

