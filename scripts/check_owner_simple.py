import sys
sys.path.insert(0, '.')
from lib.database import get_db_manager

db = get_db_manager()
if db:
    result = db.execute_query(
        "SELECT username, role, created_at FROM users WHERE role = 'Owner'", 
        fetch=True
    )
    if result:
        print("Owner users found:")
        for r in result:
            print(f"  - {r['username']}: {r['role']} (created: {r['created_at']})")
    else:
        print("No owner users found")
else:
    print("Database not available")
