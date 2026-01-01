"""
Migration lock management for concurrent access control.

Provides:
- File-based lock for migration process
- Database-level advisory locks
- Application read-only mode detection
"""

import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

# Try to import fcntl (Unix only)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

logger = logging.getLogger(__name__)

# Lock file paths
LOCK_FILE_DIR = Path("dashboard_data")
MIGRATION_LOCK_FILE = LOCK_FILE_DIR / ".migration_lock"
MIGRATION_STATUS_FILE = LOCK_FILE_DIR / ".migration_status.json"

# PostgreSQL advisory lock IDs (must be unique)
MIGRATION_ADVISORY_LOCK_ID = 1234567890  # Unique ID for migration lock


class MigrationLock:
    """Manages migration locks and status."""
    
    def __init__(self, lock_file: Path = MIGRATION_LOCK_FILE, 
                 status_file: Path = MIGRATION_STATUS_FILE):
        self.lock_file = lock_file
        self.status_file = status_file
        self.lock_fd = None
        self.db_lock_acquired = False
        self.db_conn = None
        self.db_cursor = None
        
    def is_migration_in_progress(self) -> bool:
        """Check if migration is currently in progress."""
        # Check lock file
        if self.lock_file.exists():
            try:
                # Check if lock file is stale (older than 1 hour)
                lock_age = time.time() - self.lock_file.stat().st_mtime
                if lock_age > 3600:  # 1 hour
                    logger.warning(f"Stale lock file detected (age: {lock_age:.0f}s), removing")
                    self.lock_file.unlink()
                    return False
                return True
            except Exception as e:
                logger.error(f"Error checking lock file: {e}")
                return False
        return False
    
    def get_migration_status(self) -> Optional[Dict]:
        """Get current migration status from status file."""
        if not self.status_file.exists():
            return None
        
        try:
            with open(self.status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading migration status: {e}")
            return None
    
    def acquire_file_lock(self) -> bool:
        """Acquire file-based lock (Unix/Windows compatible)."""
        try:
            # Ensure directory exists
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Try to create and lock the file
            if os.name == 'nt':  # Windows
                # On Windows, use exclusive file creation
                try:
                    self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    return True
                except OSError:
                    # File already exists
                    return False
            else:  # Unix/Linux
                if HAS_FCNTL:
                    self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
                    try:
                        fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return True
                    except BlockingIOError:
                        os.close(self.lock_fd)
                        self.lock_fd = None
                        return False
                else:
                    # Fallback for systems without fcntl
                    try:
                        self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                        return True
                    except OSError:
                        return False
        except Exception as e:
            logger.error(f"Error acquiring file lock: {e}")
            if self.lock_fd:
                try:
                    os.close(self.lock_fd)
                except:
                    pass
                self.lock_fd = None
            return False
    
    def release_file_lock(self):
        """Release file-based lock."""
        if self.lock_fd:
            try:
                if os.name != 'nt' and HAS_FCNTL:  # Unix/Linux
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None
            except Exception as e:
                logger.error(f"Error releasing file lock: {e}")
        
        # Remove lock file
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception as e:
            logger.error(f"Error removing lock file: {e}")
    
    def acquire_db_lock(self, db_conn) -> bool:
        """Acquire PostgreSQL advisory lock."""
        try:
            self.db_conn = db_conn
            self.db_cursor = db_conn.cursor()
            
            # Try to acquire advisory lock (non-blocking)
            self.db_cursor.execute(
                "SELECT pg_try_advisory_lock(%s)",
                (MIGRATION_ADVISORY_LOCK_ID,)
            )
            result = self.db_cursor.fetchone()
            
            if result and result[0]:
                self.db_lock_acquired = True
                logger.info("Database advisory lock acquired")
                return True
            else:
                logger.warning("Database advisory lock already held by another process")
                return False
        except Exception as e:
            logger.error(f"Error acquiring database lock: {e}")
            return False
    
    def release_db_lock(self):
        """Release PostgreSQL advisory lock."""
        if self.db_lock_acquired and self.db_cursor:
            try:
                self.db_cursor.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (MIGRATION_ADVISORY_LOCK_ID,)
                )
                self.db_cursor.close()
                self.db_lock_acquired = False
                logger.info("Database advisory lock released")
            except Exception as e:
                logger.error(f"Error releasing database lock: {e}")
    
    def update_status(self, status: str, progress: Optional[Dict] = None):
        """Update migration status file."""
        try:
            status_data = {
                'status': status,  # 'running', 'completed', 'failed', 'idle'
                'started_at': datetime.now().isoformat(),
                'progress': progress or {}
            }
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating migration status: {e}")
    
    def acquire_all_locks(self, db_conn) -> bool:
        """Acquire both file and database locks."""
        # First check if migration is already in progress
        if self.is_migration_in_progress():
            logger.error("Migration is already in progress (lock file exists)")
            return False
        
        # Try to acquire file lock
        if not self.acquire_file_lock():
            logger.error("Failed to acquire file lock (another migration may be running)")
            return False
        
        # Try to acquire database lock
        if not self.acquire_db_lock(db_conn):
            self.release_file_lock()
            logger.error("Failed to acquire database lock (another migration may be running)")
            return False
        
        # Update status
        self.update_status('running', {'stage': 'initializing'})
        
        logger.info("All locks acquired successfully")
        return True
    
    def release_all_locks(self):
        """Release both file and database locks."""
        self.release_db_lock()
        self.release_file_lock()
        logger.info("All locks released")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup locks."""
        self.release_all_locks()
        if exc_type:
            self.update_status('failed', {'error': str(exc_val)})
        else:
            self.update_status('completed')


def is_application_read_only() -> bool:
    """Check if application should be in read-only mode (migration in progress)."""
    lock = MigrationLock()
    return lock.is_migration_in_progress()


def get_migration_status() -> Optional[Dict]:
    """Get current migration status for application display."""
    lock = MigrationLock()
    return lock.get_migration_status()

