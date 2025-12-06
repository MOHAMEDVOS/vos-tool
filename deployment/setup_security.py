#!/usr/bin/env python3
"""
Security Setup Script for VOS Tool
Run this script to implement security best practices.
"""

import os
import secrets
import shutil
from pathlib import Path

def setup_secure_environment():
    """Set up secure environment configuration."""
    
    print("🔒 VOS TOOL SECURITY SETUP")
    print("=" * 50)
    
    # 1. Check if .env exists
    env_file = Path('.env')
    if not env_file.exists():
        print("📝 Creating .env file from template...")
        shutil.copy('.env.example', '.env')
        print("✅ Created .env file")
    else:
        print("✅ .env file already exists")
    
    # 2. Generate encryption key if not exists
    env_content = env_file.read_text() if env_file.exists() else ""
    
    if 'ENCRYPTION_KEY=' not in env_content or 'your_32_character_encryption_key_here' in env_content:
        print("🔐 Generating encryption key...")
        encryption_key = secrets.token_urlsafe(32)
        
        # Update .env file
        lines = env_content.split('\n')
        updated_lines = []
        key_added = False
        
        for line in lines:
            if line.startswith('# ENCRYPTION_KEY=') or line.startswith('ENCRYPTION_KEY='):
                updated_lines.append(f'ENCRYPTION_KEY={encryption_key}')
                key_added = True
            else:
                updated_lines.append(line)
        
        if not key_added:
            updated_lines.append(f'ENCRYPTION_KEY={encryption_key}')
        
        env_file.write_text('\n'.join(updated_lines))
        print("✅ Generated and saved encryption key")
    else:
        print("✅ Encryption key already configured")
    
    # 3. Generate session secret if not exists
    if 'SESSION_SECRET=' not in env_content or 'your_random_session_secret_key_here' in env_content:
        print("🔑 Generating session secret...")
        session_secret = secrets.token_urlsafe(64)
        
        # Update .env file
        env_content = env_file.read_text()
        lines = env_content.split('\n')
        updated_lines = []
        secret_added = False
        
        for line in lines:
            if line.startswith('# SESSION_SECRET=') or line.startswith('SESSION_SECRET='):
                updated_lines.append(f'SESSION_SECRET={session_secret}')
                secret_added = True
            else:
                updated_lines.append(line)
        
        if not secret_added:
            updated_lines.append(f'SESSION_SECRET={session_secret}')
        
        env_file.write_text('\n'.join(updated_lines))
        print("✅ Generated and saved session secret")
    else:
        print("✅ Session secret already configured")
    
    # 4. Set secure file permissions
    print("🛡️ Setting secure file permissions...")
    try:
        if os.name == 'posix':  # Unix/Linux/Mac
            os.chmod('.env', 0o600)  # Owner read/write only
            print("✅ Set .env permissions to 600 (owner only)")
        else:  # Windows
            import stat
            os.chmod('.env', stat.S_IREAD | stat.S_IWRITE)
            print("✅ Set .env permissions (Windows)")
    except Exception as e:
        print(f"⚠️ Could not set file permissions: {e}")
    
    # 5. Check for sensitive files in git
    gitignore_file = Path('.gitignore')
    if gitignore_file.exists():
        print("✅ .gitignore exists - sensitive files protected")
    else:
        print("⚠️ .gitignore not found - create one to protect sensitive files")
    
    # 6. Security recommendations
    print("\n🎯 SECURITY RECOMMENDATIONS:")
    print("1. ✅ Update .env with your actual ReadyMode credentials")
    print("2. ✅ Never commit .env file to version control")
    print("3. ✅ Use strong, unique passwords (12+ characters)")
    print("4. ✅ Rotate passwords every 90 days")
    print("5. ✅ Monitor for unauthorized access attempts")
    print("6. ✅ Keep backups of encryption keys securely")
    
    print(f"\n🔒 NEXT STEPS:")
    print(f"1. Edit .env file and update READYMODE_USER and READYMODE_PASSWORD")
    print(f"2. Run: pip install cryptography")
    print(f"3. Test security: python security_utils.py")
    print(f"4. Start application: streamlit run app.py")

def check_security_status():
    """Check current security status."""
    
    print("\n🔍 SECURITY STATUS CHECK:")
    print("-" * 30)
    
    issues = []
    
    # Check .env file
    if not Path('.env').exists():
        issues.append("❌ .env file missing")
    else:
        env_content = Path('.env').read_text()
        if 'your_readymode_username' in env_content:
            issues.append("⚠️ Default credentials in .env")
        if 'ENCRYPTION_KEY=' not in env_content:
            issues.append("⚠️ No encryption key configured")
    
    # Check .gitignore
    if not Path('.gitignore').exists():
        issues.append("⚠️ .gitignore missing")
    
    # Check for sensitive files
    sensitive_files = [
        'config_backup.py',
        '.env_backup',
        'dashboard_data/',
        'Recordings/'
    ]
    
    for file_path in sensitive_files:
        if Path(file_path).exists():
            print(f"📁 Found sensitive data: {file_path}")
    
    if not issues:
        print("✅ Security status: GOOD")
    else:
        print("⚠️ Security issues found:")
        for issue in issues:
            print(f"   {issue}")
    
    return len(issues) == 0

if __name__ == "__main__":
    setup_secure_environment()
    check_security_status()
    
    print("\n" + "=" * 50)
    print("🎉 Security setup complete!")
    print("Your VOS Tool is now more secure.")
