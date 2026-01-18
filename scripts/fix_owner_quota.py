
from lib.database import get_db_manager
import sys

def fix_owner_quota():
    try:
        db = get_db_manager()
        username = 'Mohamed Abdo'
        admin_user = 'admin'
        
        print(f"Fixing quota for: {username}")
        
        # 1. Check if 'admin' exists in admin_limits
        admin_res = db.execute_query("SELECT * FROM admin_limits WHERE admin_username = %s", (admin_user,), fetchone=True)
        
        if not admin_res:
            print(f"Admin '{admin_user}' not found in admin_limits. Creating it...")
            # Create default admin limit
            db.execute_query("""
                INSERT INTO admin_limits (admin_username, max_active_users, per_user_daily_quota, created_by, created_at)
                VALUES (%s, 100, 1000000, 'system', NOW())
            """, (admin_user,))
            print("Created 'admin' limit.")
        else:
            print(f"Admin '{admin_user}' exists.")

        # 2. Assign Mohamed Abdo to admin with UNLIMITED quota
        print(f"Assigning {username} to {admin_user} with 999,999 daily limit...")
        
        insert_query = """
            INSERT INTO user_quota_assignments (user_username, assigned_to_admin, daily_quota, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (user_username) DO UPDATE SET
                assigned_to_admin = EXCLUDED.assigned_to_admin,
                daily_quota = EXCLUDED.daily_quota,
                updated_at = NOW()
        """
        
        db.execute_query(insert_query, (username, admin_user, 999999), fetch=False)
        print("SUCCESS: Updated user_quota_assignments table.")
        
        # 3. Verify
        verify_res = db.execute_query("SELECT * FROM user_quota_assignments WHERE user_username = %s", (username,), fetchone=True)
        print("\nVerification Result:")
        print(verify_res)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_owner_quota()
