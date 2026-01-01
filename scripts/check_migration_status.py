"""
Check migration status and lock information.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.migration_lock import MigrationLock, is_application_read_only, get_migration_status
    LOCK_AVAILABLE = True
except ImportError:
    print("ERROR: Migration lock system not available")
    sys.exit(1)

def main():
    """Check and display migration status."""
    print("=" * 80)
    print("MIGRATION STATUS CHECK")
    print("=" * 80)
    print()
    
    # Check if migration is in progress
    is_read_only = is_application_read_only()
    status = get_migration_status()
    
    if is_read_only:
        print("STATUS: Migration IN PROGRESS")
        print("APPLICATION: Read-only mode (writes disabled)")
        print()
        
        if status:
            print("Migration Details:")
            print(f"  Status: {status.get('status', 'unknown')}")
            print(f"  Started: {status.get('started_at', 'unknown')}")
            progress = status.get('progress', {})
            if progress:
                print(f"  Stage: {progress.get('stage', 'unknown')}")
                print(f"  Progress: {progress.get('progress', 0)}%")
                if 'total_imported' in progress:
                    print(f"  Records Imported: {progress.get('total_imported', 0)}")
                if 'total_errors' in progress:
                    print(f"  Errors: {progress.get('total_errors', 0)}")
        else:
            print("No detailed status available")
    else:
        print("STATUS: No migration in progress")
        print("APPLICATION: Normal operation (read-write)")
        
        if status:
            print()
            print("Last Migration:")
            print(f"  Status: {status.get('status', 'unknown')}")
            print(f"  Completed: {status.get('started_at', 'unknown')}")
    
    print()
    print("=" * 80)
    
    # Check lock file
    lock = MigrationLock()
    if lock.lock_file.exists():
        import time
        lock_age = time.time() - lock.lock_file.stat().st_mtime
        print(f"Lock file exists: {lock.lock_file}")
        print(f"Lock file age: {lock_age:.0f} seconds")
        if lock_age > 3600:
            print("WARNING: Lock file is older than 1 hour - may be stale!")
    else:
        print("No lock file found")

if __name__ == "__main__":
    main()

