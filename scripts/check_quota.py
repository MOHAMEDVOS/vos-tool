
from lib.database import get_db_manager
import sys

try:
    db = get_db_manager()
    username = 'Mohamed Abdo'
    
    print(f"Checking quota for: {username}")
    
    # Check users table (legacy/backup)
    users_res = db.execute_query("SELECT username, daily_limit FROM users WHERE username = %s", (username,), fetch=True)
    print("\n[users] table:")
    print(users_res)
    
    # Check quota assignments (new system)
    quota_res = db.execute_query("SELECT * FROM user_quota_assignments WHERE user_username = %s", (username,), fetch=True)
    print("\n[user_quota_assignments] table:")
    print(quota_res)

except Exception as e:
    print(f"Error: {e}")
