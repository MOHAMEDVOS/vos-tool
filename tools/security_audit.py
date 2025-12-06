#!/usr/bin/env python3
"""
Security Audit Tool for User Credentials
Checks if all user credentials are properly secured.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.dashboard_manager import user_manager
from lib.security_utils import security_manager
import json
import os

def audit_user_security():
    """Audit all users for security compliance."""
    
    print("=" * 70)
    print("🔒 USER SECURITY AUDIT")
    print("=" * 70)
    print()
    
    users = user_manager.get_all_users()
    
    if not users:
        print("⚠️  No users found in the system.")
        return
    
    print(f"📊 Total users found: {len(users)}\n")
    
    # Security checks
    insecure_users = []
    secure_users = []
    missing_credentials = []
    
    for username, user_data in users.items():
        issues = []
        is_secure = True
        
        # Check 1: App password security
        if 'app_pass' in user_data:
            issues.append("❌ App password stored in PLAIN TEXT (CRITICAL)")
            is_secure = False
        elif 'app_pass_hash' in user_data and 'app_pass_salt' in user_data:
            issues.append("✅ App password is hashed (PBKDF2-SHA256)")
        else:
            issues.append("⚠️  No app password found")
        
        # Check 2: ReadyMode credentials security
        if 'readymode_pass' in user_data:
            issues.append("❌ ReadyMode password stored in PLAIN TEXT (CRITICAL)")
            is_secure = False
        elif 'readymode_pass_encrypted' in user_data:
            issues.append("✅ ReadyMode password is encrypted (AES-256)")
        else:
            issues.append("ℹ️  No ReadyMode credentials set")
            missing_credentials.append(username)
        
        # Check 3: ReadyMode username
        if 'readymode_user' in user_data and user_data['readymode_user']:
            issues.append("✅ ReadyMode username is set")
        else:
            issues.append("ℹ️  No ReadyMode username set")
        
        # Check 4: Role assignment
        if 'role' in user_data:
            issues.append(f"✅ Role assigned: {user_data['role']}")
        else:
            issues.append("⚠️  No role assigned (defaults to Auditor)")
        
        # Summary
        if is_secure:
            secure_users.append(username)
            print(f"✅ {username}: SECURE")
        else:
            insecure_users.append(username)
            print(f"❌ {username}: INSECURE - NEEDS IMMEDIATE ATTENTION")
        
        for issue in issues:
            print(f"   {issue}")
        print()
    
    # Final Report
    print("=" * 70)
    print("📋 SECURITY AUDIT SUMMARY")
    print("=" * 70)
    print()
    
    print(f"✅ Secure users: {len(secure_users)}/{len(users)}")
    print(f"❌ Insecure users: {len(insecure_users)}/{len(users)}")
    print(f"ℹ️  Users without ReadyMode credentials: {len(missing_credentials)}")
    print()
    
    if insecure_users:
        print("🚨 CRITICAL: The following users have INSECURE credentials:")
        for username in insecure_users:
            print(f"   - {username}")
        print()
        print("⚠️  ACTION REQUIRED:")
        print("   Run the migration script to secure these users:")
        print("   python deployment/migrate_passwords.py")
        print()
    else:
        print("✅ ALL USERS ARE SECURE!")
        print()
    
    # Encryption key check
    print("=" * 70)
    print("🔑 ENCRYPTION KEY STATUS")
    print("=" * 70)
    print()
    
    encryption_key_file = Path("lib/.encryption_key")
    env_key = security_manager.encryption_key is not None
    
    if env_key:
        print("✅ Encryption key is available")
        if os.getenv('ENCRYPTION_KEY'):
            print("   Source: Environment variable (RECOMMENDED)")
        elif encryption_key_file.exists():
            print("   Source: Persistent file")
            # Check file permissions
            try:
                import stat
                file_stat = encryption_key_file.stat()
                if os.name == 'posix':
                    mode = file_stat.st_mode
                    if (mode & 0o077) == 0:  # No group/other permissions
                        print("   ✅ File permissions are secure (600)")
                    else:
                        print("   ⚠️  File permissions may be too permissive")
            except:
                pass
        print()
    else:
        print("❌ Encryption key not available - encryption will fail!")
        print()
    
    # File security check
    print("=" * 70)
    print("📁 FILE SECURITY")
    print("=" * 70)
    print()
    
    users_file = Path("dashboard_data/users/users.json")
    if users_file.exists():
        print(f"✅ Users file exists: {users_file}")
        try:
            import stat
            file_stat = users_file.stat()
            if os.name == 'posix':
                mode = file_stat.st_mode
                if (mode & 0o077) == 0:
                    print("   ✅ File permissions are secure (600)")
                else:
                    print("   ⚠️  File permissions may be too permissive")
                    print("   Recommendation: chmod 600 dashboard_data/users/users.json")
        except:
            pass
    else:
        print("⚠️  Users file not found")
    print()
    
    # Recommendations
    print("=" * 70)
    print("💡 RECOMMENDATIONS")
    print("=" * 70)
    print()
    
    if insecure_users:
        print("1. 🚨 URGENT: Migrate insecure users immediately")
        print("   python deployment/migrate_passwords.py")
        print()
    
    if not os.getenv('ENCRYPTION_KEY'):
        print("2. 🔑 Set ENCRYPTION_KEY in .env for better key management")
        print("   This ensures the encryption key is not stored in files")
        print()
    
    if missing_credentials:
        print(f"3. ℹ️  {len(missing_credentials)} users don't have ReadyMode credentials")
        print("   They can set them via the Settings dashboard")
        print()
    
    print("4. ✅ Keep the users.json file secure and backed up")
    print("5. ✅ Regularly audit user access and permissions")
    print()
    
    return {
        'total_users': len(users),
        'secure_users': len(secure_users),
        'insecure_users': len(insecure_users),
        'missing_credentials': len(missing_credentials),
        'insecure_usernames': insecure_users
    }

if __name__ == "__main__":
    import os
    try:
        results = audit_user_security()
        
        # Exit code based on security status
        if results['insecure_users'] > 0:
            print("❌ SECURITY AUDIT FAILED - Action required!")
            sys.exit(1)
        else:
            print("✅ SECURITY AUDIT PASSED - All users are secure!")
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Error during security audit: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

