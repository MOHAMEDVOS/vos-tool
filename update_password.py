#!/usr/bin/env python3
"""
Update database password using Python.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def update_password():
    """Update vos_user password in database."""
    
    try:
        from lib.database import get_db_manager
        
        db_manager = get_db_manager()
        
        # Test connection first
        conn = db_manager.connection_pool.getconn()
        if conn:
            print("✅ Connected to database")
            
            # Create cursor
            cursor = conn.cursor()
            
            # Update password
            cursor.execute("ALTER USER vos_user PASSWORD %s", ('20101964mm',))
            
            # Commit the change
            conn.commit()
            
            # Close connection
            cursor.close()
            conn.close()
            
            print("✅ Password updated successfully!")
            
        else:
            print("❌ Failed to connect to database")
            
    except Exception as e:
        print(f"❌ Error updating password: {e}")

if __name__ == "__main__":
    update_password()
