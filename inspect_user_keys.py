
import sys
import os

sys.path.insert(0, os.getcwd())

try:
    from lib.dashboard_manager import user_manager
    # Create a dummy user to inspect default fields
    test_user = "debug_schema_user"
    user_manager.add_user(test_user, "Auditor")
    
    user = user_manager.get_user(test_user)
    if user:
        print("User Keys:", list(user.keys()))
        if 'assemblyai_api_key' in user:
            print("FOUND: assemblyai_api_key exists")
        else:
            print("NOT FOUND: assemblyai_api_key does not exist")
            # Print closely matching keys just in case
            print([k for k in user.keys() if 'api' in k or 'key' in k])
            
    else:
        print("Failed to get user")
        
except Exception as e:
    print(e)
