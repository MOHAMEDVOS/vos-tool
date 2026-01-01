#!/usr/bin/env python3
"""
Script to add AssemblyAI API key for user Aya
"""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from lib.dashboard_manager import user_manager
from lib.security_utils import security_manager

def add_api_key_for_user():
    username = "Aya"
    api_key = "c8ed7ab4bcd8438c8f84d3c8b7fc2b6b"
    
    try:
        # Get current user data
        user_data = user_manager.get_user(username)
        if not user_data:
            print(f"User '{username}' not found")
            return False
        
        # Encrypt the API key
        if security_manager:
            encrypted_key = security_manager.encrypt_string(api_key)
            print(f"API key encrypted successfully")
        else:
            print("Security manager not available, storing key as plain text")
            encrypted_key = api_key
        
        # Try to update using user_manager first
        user_data["assemblyai_api_key_encrypted"] = encrypted_key
        
        # Try with different update methods
        success = False
        
        # Method 1: Try updating with user_manager
        try:
            success = user_manager.update_user(username, user_data, username)
        except:
            pass
        
        # Method 2: Try direct database update if available
        if not success and hasattr(user_manager, '_db_manager') and user_manager._db_manager:
            try:
                query = "UPDATE users SET assemblyai_api_key_encrypted = %s WHERE username = %s"
                params = (encrypted_key, username)
                user_manager._db_manager.execute_query(query, params)
                success = True
                print("Updated via direct database query")
            except Exception as e:
                print(f"Direct database update failed: {e}")
        
        # Method 3: Try file-based update
        if not success and not hasattr(user_manager, '_db_manager'):
            try:
                users = user_manager.get_all_users()
                if username in users:
                    users[username]["assemblyai_api_key_encrypted"] = encrypted_key
                    from lib.dashboard_manager import safe_json_write
                    if safe_json_write(user_manager.users_file, users):
                        success = True
                        print("Updated via file storage")
            except Exception as e:
                print(f"File update failed: {e}")
        
        if success:
            print(f"Successfully added AssemblyAI API key for user '{username}'")
            return True
        else:
            print(f"All update methods failed for user '{username}'")
            return False
            
    except Exception as e:
        print(f"Error adding API key for user '{username}': {e}")
        return False

if __name__ == "__main__":
    print("Adding AssemblyAI API key for user Aya...")
    success = add_api_key_for_user()
    if success:
        print("Operation completed successfully!")
    else:
        print("Operation failed!")
