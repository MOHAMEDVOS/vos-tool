#!/usr/bin/env python3
"""
Direct verification of dashboard records.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def verify_dashboard():
    """Verify dashboard records directly."""
    
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
            
            # Show recent records
            recent_results = db_manager.execute_query(
                'SELECT agent_name, file_name, rebuttal_detection, transcript FROM agent_audit_results WHERE username = %s ORDER BY created_at DESC LIMIT 5',
                ('dashboard_test_user',),
                fetch=True
            )
            
            if recent_results:
                print(f"📊 Recent dashboard records:")
                for i, record in enumerate(recent_results, 1):
                    agent_name = record[0] if len(record) > 0 else 'N/A'
                    file_name = record[1] if len(record) > 1 else 'N/A'
                    rebuttal = record[2] if len(record) > 2 else 'N/A'
                    transcript = record[3] if len(record) > 3 else 'N/A'
                    
                    print(f"  {i}. Agent: {agent_name}")
                    print(f"  {i}. File: {file_name}")
                    print(f"  {i}. Rebuttal: {rebuttal}")
                    print(f"  {i}. Transcript: {transcript[:50]}...")
            else:
                print("❌ No recent records found")
                
    except Exception as e:
        print(f"❌ Error verifying dashboard: {e}")

if __name__ == "__main__":
    verify_dashboard()
