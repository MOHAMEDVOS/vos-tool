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
        
        # Update using user_manager (database-only)
        success = False
        try:
            success = user_manager.update_user(username, user_data, username)
            if success:
                print("Updated user successfully via UserManager (Database)")
        except Exception as e:
            print(f"Update failed: {e}")
        
        if success:
            print(f"Successfully added AssemblyAI API key for user '{username}'")
            return True
        else:
            print(f"Failed to update user '{username}' - check database connection")
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
