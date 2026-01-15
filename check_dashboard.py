#!/usr/bin/env python3
"""
Simple check of dashboard records.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_dashboard():
    """Check dashboard records directly."""
    
    try:
        from lib.database import get_db_manager
        
        db_manager = get_db_manager()
        result = db_manager.execute_query(
            'SELECT COUNT(*) FROM agent_audit_results WHERE username = %s',
            ('dashboard_test_user',),  # Tuple format with trailing comma
            fetchone=True
        )
        
        if result:
            count = result[0]
            print(f"✅ Dashboard records found: {count} agent audit results")
        else:
            print("❌ No dashboard records found")
            
    except Exception as e:
        print(f"❌ Error checking dashboard: {e}")

if __name__ == "__main__":
    check_dashboard()
