#!/usr/bin/env python3
"""
Security utilities for VOS Tool
Provides encryption, password hashing, and secure credential management.
"""

import os
import secrets
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

class SecurityManager:
    """Handles encryption, password hashing, and secure credential management."""
    
    def __init__(self):
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key) if self.encryption_key else None
    
    def _get_or_create_encryption_key(self):
        """Get encryption key from environment or create a persistent one.
        
        SECURITY: Prefers ENCRYPTION_KEY_PATH or ENCRYPTION_KEY environment variable.
        Falls back to .encryption_key file for backward compatibility but warns.
        """
        # Priority 1: Try to get path from environment
        env_key_path = os.getenv('ENCRYPTION_KEY_PATH')
        if env_key_path and os.path.exists(env_key_path):
            try:
                with open(env_key_path, 'rb') as f:
                    key_data = f.read()
                # Validate the key
                Fernet(key_data)
                logger.info(f"Using encryption key from secure path: {env_key_path}")
                return key_data
            except Exception as e:
                logger.warning(f"Invalid encryption key at path {env_key_path}: {e}")
        
        # Priority 2: Try to get key directly from environment
        env_key = os.getenv('ENCRYPTION_KEY')
        if env_key:
            env_key = env_key.strip().strip('"').strip("'")
            try:
                # Validate the key format
                Fernet(env_key.encode())
                logger.info("Using encryption key from ENCRYPTION_KEY environment variable")
                return env_key.encode()
            except Exception as e:
                logger.warning(f"Invalid ENCRYPTION_KEY in environment: {e}")

        # Priority 3: Try to load from persistent file (DEPRECATED - for backward compatibility)
        key_file = os.path.join(os.path.dirname(__file__), '.encryption_key')
        if os.path.exists(key_file):
            logger.warning(
                "⚠️  SECURITY WARNING: Using encryption key from .encryption_key file. "
                "This is deprecated for security reasons. "
                "Please migrate to environment variable: "
                "1. Set ENCRYPTION_KEY_PATH in .env to point to secure location "
                "   (e.g., ENCRYPTION_KEY_PATH=/home/user/.vos_secure/encryption_key)"
                "2. Move .encryption_key to that secure location "
                "3. Delete .encryption_key from project directory"
            )
            try:
                with open(key_file, 'rb') as f:
                    key_data = f.read()
                # Validate the key
                Fernet(key_data)
                return key_data
            except Exception as e:
                logger.error(f"Invalid encryption key in file: {e}")
                # Remove corrupted key file
                try:
                    os.remove(key_file)
                except Exception:
                    pass

        # No key found anywhere - generate new one and save to secure location if possible
        logger.warning("No encryption key found. Generating new key.")
        key = Fernet.generate_key()

        # Try to save to secure location if ENCRYPTION_KEY_PATH is set
        if env_key_path:
            try:
                # Create directory if needed
                os.makedirs(os.path.dirname(env_key_path), exist_ok=True)
                with open(env_key_path, 'wb') as f:
                    f.write(key)
                # Set secure permissions
                secure_file_permissions(env_key_path)
                logger.info(f"✓ New encryption key saved to secure location: {env_key_path}")
                return key
            except Exception as e:
                logger.error(f"Could not save encryption key to {env_key_path}: {e}")
        
        # Fallback: Save to file with strong warning
        logger.error(
            "⚠️  CRITICAL: Saving encryption key to .encryption_key file in project directory. "
            "This is NOT secure for production! "
            "Set ENCRYPTION_KEY_PATH in your .env file to use a secure location."
        )
        try:
            with open(key_file, 'wb') as f:
                f.write(key)
            secure_file_permissions(key_file)
        except Exception as e:
            logger.error(f"Could not save encryption key: {e}")

        return key
    
    def encrypt_string(self, plaintext: str) -> str:
        """
        Encrypt a string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not self.fernet:
            logger.error("No encryption key available")
            return plaintext
        
        try:
            encrypted = self.fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return plaintext
    
    def decrypt_string(self, encrypted_text: str) -> str:
        """
        Decrypt a string.
        
        Args:
            encrypted_text: Base64 encoded encrypted string (can be None)
            
        Returns:
            Decrypted plaintext string or empty string if input is None
        """
        if not encrypted_text:
            return ""
        
        if not self.fernet:
            logger.error("No encryption key available")
            return encrypted_text
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_text
    
    def hash_password(self, password: str, salt: bytes = None) -> tuple:
        """
        Hash a password with salt.
        
        Args:
            password: Password to hash
            salt: Optional salt (generates new if None)
            
        Returns:
            tuple: (hashed_password, salt)
        """
        if salt is None:
            salt = os.urandom(32)  # 32 bytes = 256 bits
        
        # Use PBKDF2 with SHA256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # Recommended minimum
        )
        
        hashed = kdf.derive(password.encode())
        return base64.urlsafe_b64encode(hashed).decode(), base64.urlsafe_b64encode(salt).decode()
    
    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Password to verify
            hashed_password: Base64 encoded hashed password
            salt: Base64 encoded salt
            
        Returns:
            bool: True if password matches
        """
        try:
            salt_bytes = base64.urlsafe_b64decode(salt.encode())
            expected_hash = base64.urlsafe_b64decode(hashed_password.encode())
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=100000,
            )
            
            kdf.verify(password.encode(), expected_hash)
            return True
        except Exception:
            return False
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate a secure random token.
        
        Args:
            length: Token length in bytes
            
        Returns:
            URL-safe base64 encoded token
        """
        return secrets.token_urlsafe(length)
    
    def generate_session_key(self) -> str:
        """Generate a secure session key."""
        return self.generate_secure_token(64)

# Global security manager instance
security_manager = SecurityManager()

def encrypt_credentials(credentials: dict) -> dict:
    """
    Encrypt sensitive fields in credentials dictionary.
    
    Args:
        credentials: Dictionary with credentials
        
    Returns:
        Dictionary with encrypted sensitive fields
    """
    sensitive_fields = ['app_pass', 'readymode_pass', 'password']
    encrypted_creds = credentials.copy()
    
    for field in sensitive_fields:
        if field in encrypted_creds:
            encrypted_creds[field] = security_manager.encrypt_string(encrypted_creds[field])
            encrypted_creds[f'{field}_encrypted'] = True
    
    return encrypted_creds

def decrypt_credentials(credentials: dict) -> dict:
    """
    Decrypt sensitive fields in credentials dictionary.
    
    Args:
        credentials: Dictionary with encrypted credentials
        
    Returns:
        Dictionary with decrypted sensitive fields
    """
    sensitive_fields = ['app_pass', 'readymode_pass', 'password']
    decrypted_creds = credentials.copy()
    
    for field in sensitive_fields:
        if f'{field}_encrypted' in decrypted_creds and decrypted_creds[f'{field}_encrypted']:
            decrypted_creds[field] = security_manager.decrypt_string(decrypted_creds[field])
            del decrypted_creds[f'{field}_encrypted']
    
    return decrypted_creds

def secure_file_permissions(file_path: str):
    """
    Set secure file permissions (owner read/write only).
    
    Args:
        file_path: Path to file to secure
    """
    try:
        if os.name == 'posix':  # Unix/Linux/Mac
            os.chmod(file_path, 0o600)  # Owner read/write only
        else:  # Windows
            import stat
            os.chmod(file_path, stat.S_IREAD | stat.S_IWRITE)
        logger.info(f"Secured file permissions for {file_path}")
    except Exception as e:
        logger.warning(f"Could not set secure permissions for {file_path}: {e}")

def check_environment_security():
    """
    Check environment for security issues and provide recommendations.
    
    Returns:
        dict: Security check results
    """
    issues = []
    recommendations = []
    
    # Check if .env exists and has secure permissions
    env_file = '.env'
    if os.path.exists(env_file):
        try:
            stat_info = os.stat(env_file)
            if os.name == 'posix' and (stat_info.st_mode & 0o077) != 0:
                issues.append(".env file has overly permissive permissions")
                recommendations.append("Run: chmod 600 .env")
        except Exception as e:
            issues.append(f"Could not check .env permissions: {e}")
    else:
        issues.append(".env file not found")
        recommendations.append("Create .env file from .env.example")

    # Check encryption key sources
    encryption_key_file = os.path.join(os.path.dirname(__file__), '.encryption_key')
    if os.path.exists(encryption_key_file):
        try:
            stat_info = os.stat(encryption_key_file)
            if os.name == 'posix' and (stat_info.st_mode & 0o077) != 0:
                issues.append("Encryption key file has overly permissive permissions")
                recommendations.append("Run: chmod 600 .encryption_key")
        except Exception as e:
            issues.append(f"Could not check encryption key file permissions: {e}")
    elif not os.getenv('ENCRYPTION_KEY'):
        recommendations.append("Set ENCRYPTION_KEY in .env for better security (currently using auto-generated key)")

    # Check for hardcoded credentials in common files
    # Note: This is a basic check - in production environments, 
    # consider using more sophisticated security scanning tools
    try:
        common_files = ['app.py', 'config.py']
        for file_name in common_files:
            if os.path.exists(file_name):
                # Basic check for potential hardcoded credentials
                # This is intentionally simple to avoid false positives
                recommendations.append(f"Review {file_name} for hardcoded credentials")
    except Exception as e:
        logger.debug(f"Error during credential check: {e}")
    
    return {
        'issues': issues,
        'recommendations': recommendations,
        'status': 'secure' if not issues else 'needs_attention'
    }

if __name__ == "__main__":
    # Security check and demo
    print("VOS TOOL SECURITY UTILITIES")
    print("=" * 50)
    
    # Run security check
    security_check = check_environment_security()
    print(f"Security Status: {security_check['status'].upper()}")
    
    if security_check['issues']:
        print("\nSecurity Issues:")
        for issue in security_check['issues']:
            print(f"  - {issue}")
    
    if security_check['recommendations']:
        print("\nRecommendations:")
        for rec in security_check['recommendations']:
            print(f"  - {rec}")
    
    # Demo encryption
    print(f"\nEncryption Demo:")
    test_password = "MySecretPassword123!"
    encrypted = security_manager.encrypt_string(test_password)
    decrypted = security_manager.decrypt_string(encrypted)
    print(f"Original: {test_password}")
    print(f"Encrypted: {encrypted[:20]}...")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_password == decrypted}")
    
    # Demo password hashing
    print(f"\nPassword Hashing Demo:")
    hashed, salt = security_manager.hash_password(test_password)
    is_valid = security_manager.verify_password(test_password, hashed, salt)
    print(f"Password: {test_password}")
    print(f"Hash: {hashed[:20]}...")
    print(f"Valid: {is_valid}")
