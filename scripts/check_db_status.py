#!/usr/bin/env python3
"""Check database status and record counts."""

from lib.database import get_db_manager

def main():
    db = get_db_manager()
    
    if not db:
        print("✗ Database connection FAILED")
        return False
    
    print("✓ Database connected successfully\n")
    
    tables = [
        'users',
        'user_sessions', 
        'agent_audit_results',
        'lite_audit_results',
        'admin_limits',
        'user_quota_assignments',
        'repository_phrases',
        'pending_phrases',
        'daily_counters',
        'app_settings'
    ]
    
    print("Database Record Counts:")
    print("-" * 50)
    
    total_records = 0
    for table in tables:
        try:
            result = db.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table}", 
                fetchone=True
            )
            count = result['cnt'] if result else 0
            total_records += count
            status = "✓" if count > 0 else "○"
            print(f"{status} {table:30} {count:>8} records")
        except Exception as e:
            print(f"✗ {table:30} ERROR: {str(e)[:40]}")
    
    print("-" * 50)
    print(f"Total records across all tables: {total_records}")
    
    return True

if __name__ == "__main__":
    main()
