#!/usr/bin/env python3
"""Check if placeholder password was used in production."""

import sys
sys.path.insert(0, '.')

from lib.database import get_db_manager

def main():
    db = get_db_manager()
    
    if not db:
        print("✗ Cannot connect to database")
        return
    
    print("=" * 60)
    print("SECURITY CHECK: Verifying Owner User Status")
    print("=" * 60)
    
    # Check if Mohamed Abdo user exists
    query = """
        SELECT username, role, created_at, 
               CASE 
                   WHEN app_pass_hash LIKE '$2b$12$placeholder%' THEN 'PLACEHOLDER (INSECURE!)'
                   ELSE 'CUSTOM HASH' 
               END as password_status
        FROM users 
        WHERE username = 'Mohamed Abdo' OR role = 'Owner'
    """
    
    try:
        results = db.execute_query(query, fetch=True)
        
        if not results:
            print("\n✓ GOOD: No owner user with default credentials found")
            print("  Owner user must be created via secure script")
            return
        
        print("\nOwner Users Found:")
        print("-" * 60)
        
        has_placeholder = False
        for row in results:
            print(f"Username: {row['username']}")
            print(f"Role: {row['role']}")
            print(f"Created: {row['created_at']}")
            print(f"Password: {row['password_status']}")
            print("-" * 60)
            
            if 'PLACEHOLDER' in row['password_status']:
                has_placeholder = True
        
        if has_placeholder:
            print("\n⚠️  CRITICAL SECURITY ISSUE:")
            print("   Owner user has PLACEHOLDER password!")
            print("\n   IMMEDIATE ACTION Required:")
            print("   1. Run: python scripts/reset_owner_password.py")
            print("   2. Or manually update via SQL:")
            print("      UPDATE users SET app_pass_hash = '<secure_hash>'")
            print("      WHERE username = 'Mohamed Abdo';")
        else:
            print("\n✓ Owner user has custom password (not placeholder)")
            
    except Exception as e:
        print(f"\n✗ Error checking users: {e}")

if __name__ == "__main__":
    main()
