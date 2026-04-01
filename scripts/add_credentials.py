
import sys
import os
import getpass
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.getcwd())

# Setup logging
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def add_credentials():
    print("\n🔐 VOS Tool - Secure Credential Manager")
    print("=======================================")
    
    try:
        from lib.dashboard_manager import user_manager
        from lib.security_utils import security_manager
    except ImportError as e:
        print(f"❌ Error importing project modules: {e}")
        return

    # 1. Get Username
    username = input("\nEnter VOS Username (e.g. Auditor1): ").strip()
    if not username:
        print("❌ Username cannot be empty.")
        return

    # Check if user exists
    user = user_manager.get_user(username)
    if not user:
        print(f"⚠️  User '{username}' not found in database.")
        create = input("Do you want to create this user? (y/n): ").strip().lower()
        if create == 'y':  
            # Minimal user creation
            if not user_manager.add_user(username, "Auditor"): # Assuming add_user(username, role) exists
                 # Fallback if add_user signature is different or fails
                 print("❌ Could not create user automatically. Please contact admin.")
                 return
            print(f"✅ User '{username}' created.")
        else:
            print("❌ Operation cancelled.")
            return

    # 2. Get ReadyMode Credentials
    print(f"\nUpdate ReadyMode Credentials for '{username}'")
    rm_user = input(f"ReadyMode Username [Press Enter to use '{username}']: ").strip() or username
    
    # Secure password input
    while True:
        rm_pass = getpass.getpass("ReadyMode Password: ").strip()
        if not rm_pass:
            print("Password cannot be empty.")
            continue
        rm_pass_confirm = getpass.getpass("Confirm Password: ").strip()
        if rm_pass != rm_pass_confirm:
            print("❌ Passwords do not match. Try again.")
            continue
        break

    rm_url = input("ReadyMode URL [Press Enter to use 'resva']: ").strip() or "resva"

    # 3. Encrypt Password


    # 4. Update Database
    updates = {
        'readymode_user': rm_user,
        'readymode_pass': rm_pass,  # Pass plain text, UserManager encrypts it
        'readymode_url': rm_url,
        'has_readymode_credentials': True
    }

    # 3b. AssemblyAI API Key
    print(f"\nUpdate AssemblyAI API Key for '{username}'")
    print("(Leave empty to keep existing key or skip)")
    api_key_input = input("AssemblyAI API Key: ").strip()
    
    if api_key_input:
        updates['assemblyai_api_key'] = api_key_input # Pass plain text, UserManager encrypts it
        print(f"✅ API Key staged for encryption.")

    try:
        print("💾 Saving to database...")
        success = user_manager.update_user(username, updates, updated_by=username)
        if success:
            print(f"\n✅ SUCCESS! Credentials for '{username}' have been secured in the database.")
            print("The system will now automatically decrypt them during login.")
        else:
            print("\n❌ Failed to update user in database.")
    except Exception as e:
        print(f"\n❌ Database update error: {e}")

if __name__ == "__main__":
    add_credentials()
