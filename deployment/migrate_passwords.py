#!/usr/bin/env python3
"""
Password Migration Script for VOS Tool
Migrates existing plain text passwords to secure hashed passwords.
"""

import json
import os
from pathlib import Path
import logging

# Import security utilities
try:
    from security_utils import security_manager
    SECURITY_AVAILABLE = True
except ImportError:
    print("❌ Security utilities not available. Please install: pip install cryptography")
    exit(1)

# Import dashboard manager
try:
    from dashboard_manager import user_manager
    DASHBOARD_AVAILABLE = True
except ImportError:
    print("❌ Dashboard manager not available")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_user_passwords():
    """Migrate all users from plain text to hashed passwords."""
    
    print("🔒 VOS TOOL PASSWORD MIGRATION")
    print("=" * 50)
    
    # Get all users
    users = user_manager.get_all_users()
    
    if not users:
        print("📝 No users found to migrate")
        return
    
    migrated_count = 0
    already_secure_count = 0
    failed_count = 0
    
    for username, user_data in users.items():
        print(f"\n👤 Processing user: {username}")
        
        # Check if already using hashed passwords
        if 'app_pass_hash' in user_data and 'app_pass_salt' in user_data:
            print(f"  ✅ Already using secure hashed password")
            already_secure_count += 1
            continue
        
        # Check if has plain text password
        if 'app_pass' not in user_data:
            print(f"  ⚠️ No password found - skipping")
            continue
        
        try:
            # Get plain text password
            plain_password = user_data['app_pass']
            
            # Hash the password
            hashed_password, salt = security_manager.hash_password(plain_password)
            
            # Update user data
            user_data['app_pass_hash'] = hashed_password
            user_data['app_pass_salt'] = salt
            del user_data['app_pass']  # Remove plain text
            
            # Encrypt ReadyMode password if exists
            if 'readymode_pass' in user_data and user_data['readymode_pass']:
                encrypted_rm_pass = security_manager.encrypt_string(user_data['readymode_pass'])
                user_data['readymode_pass_encrypted'] = encrypted_rm_pass
                del user_data['readymode_pass']  # Remove plain text
                print(f"  🔐 Encrypted ReadyMode password")
            
            # Update user in database
            if user_manager.update_user(username, user_data):
                print(f"  ✅ Migrated to secure hashed password")
                migrated_count += 1
            else:
                print(f"  ❌ Failed to save migrated user")
                failed_count += 1
                
        except Exception as e:
            print(f"  ❌ Migration failed: {e}")
            failed_count += 1
    
    # Summary
    print(f"\n" + "=" * 50)
    print(f"MIGRATION SUMMARY:")
    print(f"✅ Migrated: {migrated_count} users")
    print(f"✅ Already secure: {already_secure_count} users")
    print(f"❌ Failed: {failed_count} users")
    print(f"📊 Total users: {len(users)}")
    
    if migrated_count > 0:
        print(f"\n🎉 Successfully migrated {migrated_count} users to secure password storage!")
    
    if failed_count > 0:
        print(f"\n⚠️ {failed_count} users failed migration - check logs for details")

def backup_users_file():
    """Create a backup of the users file before migration."""
    
    users_file = Path("dashboard_data/users/users.json")
    if users_file.exists():
        backup_file = users_file.with_suffix('.backup.json')
        
        try:
            import shutil
            shutil.copy2(users_file, backup_file)
            print(f"📁 Created backup: {backup_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to create backup: {e}")
            return False
    else:
        print("📝 No users file found - no backup needed")
        return True

def verify_migration():
    """Verify that migration was successful."""
    
    print(f"\n🔍 VERIFYING MIGRATION...")
    print("-" * 30)
    
    users = user_manager.get_all_users()
    
    for username, user_data in users.items():
        has_hash = 'app_pass_hash' in user_data and 'app_pass_salt' in user_data
        has_plain = 'app_pass' in user_data
        
        if has_hash and not has_plain:
            print(f"✅ {username}: Secure hashed password")
        elif has_plain and not has_hash:
            print(f"⚠️ {username}: Still using plain text password")
        elif has_hash and has_plain:
            print(f"🔄 {username}: Both hash and plain text (migration incomplete)")
        else:
            print(f"❓ {username}: No password data found")

def test_password_verification():
    """Test password verification with a sample user."""
    
    print(f"\n🧪 TESTING PASSWORD VERIFICATION...")
    print("-" * 30)
    
    # This is just a test - in real usage, passwords should never be hardcoded
    test_users = [
        ("Mohamed Abdo", "20101964mm"),
        ("auditor1", "res-2045")
    ]
    
    for username, expected_password in test_users:
        if user_manager.user_exists(username):
            # Test correct password
            if user_manager.verify_user_password(username, expected_password):
                print(f"✅ {username}: Password verification successful")
            else:
                print(f"❌ {username}: Password verification failed")
            
            # Test wrong password
            if not user_manager.verify_user_password(username, "wrong_password"):
                print(f"✅ {username}: Correctly rejected wrong password")
            else:
                print(f"❌ {username}: Incorrectly accepted wrong password")
        else:
            print(f"⚠️ {username}: User not found")

def main():
    """Run the complete migration process."""
    
    print("This script will migrate your VOS Tool user passwords from plain text to secure hashed storage.")
    print("This is a one-time migration that improves security significantly.")
    
    # Confirm migration
    response = input("\nDo you want to proceed with password migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Create backup
    if not backup_users_file():
        response = input("Backup failed. Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return
    
    # Run migration
    migrate_user_passwords()
    
    # Verify migration
    verify_migration()
    
    # Test verification (optional)
    response = input("\nRun password verification tests? (y/N): ")
    if response.lower() == 'y':
        test_password_verification()
    
    print(f"\n🎉 Password migration complete!")
    print(f"Your VOS Tool now uses secure password hashing.")

if __name__ == "__main__":
    main()
