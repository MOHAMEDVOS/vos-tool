"""
Dashboard Data Manager
Handles storage and retrieval of audit results for dashboard display.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple, Callable
import json
import logging
import streamlit as st
import os
import tempfile
import time
import contextlib
from lib.ai_campaign_report import generate_ai_campaign_summary, generate_ai_issue_notes

# File locking imports (cross-platform)
try:
    if os.name == 'posix':  # Unix/Linux/Mac
        import fcntl
        HAS_FCNTL = True
    else:
        HAS_FCNTL = False
    
    if os.name == 'nt':  # Windows
        import msvcrt
        HAS_MSVCRT = True
    else:
        HAS_MSVCRT = False
except ImportError:
    HAS_FCNTL = False
    HAS_MSVCRT = False

# Import security utilities for password hashing
try:
    from lib.security_utils import security_manager, encrypt_credentials, decrypt_credentials
    SECURITY_AVAILABLE = True
except ImportError as e:
    SECURITY_AVAILABLE = False
    logging.warning(f"Security utilities not available - passwords will be stored in plain text. Error: {e}")

# Import quota management system
try:
    from lib.quota_manager import quota_manager
    QUOTA_SYSTEM_AVAILABLE = quota_manager is not None
    if not QUOTA_SYSTEM_AVAILABLE:
        logging.warning("Quota manager failed to initialize - quota_manager is None")
except ImportError as e:
    QUOTA_SYSTEM_AVAILABLE = False
    quota_manager = None
    logging.warning(f"Quota management system not available. Error: {e}")

logger = logging.getLogger(__name__)


def safe_json_write(file_path: Path, data: Any, max_retries: int = 3, retry_delay: float = 0.1) -> bool:
    """
    Safely write JSON data to file with file locking and atomic writes.
    
    This function prevents race conditions when multiple processes try to write
    to the same JSON file simultaneously. It uses:
    1. File locking to ensure only one process writes at a time
    2. Atomic writes (write to temp file, then rename) to prevent corruption
    3. Retry logic for transient lock failures
    
    Why this is important:
    - Without locking, two users saving data at the same time can corrupt the file
    - Atomic writes ensure the file is never in a partially-written state
    - Prevents data loss and audit record corruption
    
    Args:
        file_path: Path to the JSON file to write
        data: Data to write (will be JSON serialized)
        max_retries: Maximum number of retry attempts if lock fails
        retry_delay: Delay between retries in seconds
        
    Returns:
        True if write succeeded, False otherwise
    """
    temp_file = None
    file_handle = None
    
    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temporary file in same directory (for atomic rename)
        temp_file = file_path.with_suffix(file_path.suffix + '.tmp')
        
        # Retry loop for file locking
        for attempt in range(max_retries):
            try:
                # Open temp file for writing
                file_handle = open(temp_file, 'w', encoding='utf-8')
                
                # Lock the file (cross-platform)
                try:
                    if os.name == 'posix' and HAS_FCNTL:  # Unix/Linux/Mac
                        fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    elif os.name == 'nt' and HAS_MSVCRT:  # Windows
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                except NameError:
                    # fcntl or msvcrt not available - continue without locking
                    pass
                
                # Write JSON data
                json.dump(data, file_handle, indent=2, default=str, ensure_ascii=False)
                file_handle.flush()
                os.fsync(file_handle.fileno())  # Force write to disk
                
                # Unlock before closing
                try:
                    if os.name == 'posix' and HAS_FCNTL:
                        fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                    elif os.name == 'nt' and HAS_MSVCRT:
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except (NameError, OSError):
                    pass
                
                file_handle.close()
                file_handle = None
                
                # Atomic rename: temp file -> final file
                # This ensures the file is never in a partially-written state
                os.replace(temp_file, file_path)
                
                return True
                
            except (IOError, OSError) as e:
                # Lock failed or other I/O error - retry if attempts remaining
                if file_handle:
                    try:
                        if os.name == 'posix' and HAS_FCNTL:
                            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                        elif os.name == 'nt' and HAS_MSVCRT:
                            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                        file_handle.close()
                    except:
                        pass
                    file_handle = None
                
                if attempt < max_retries - 1:
                    logger.warning(f"File lock failed for {file_path}, retrying ({attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to acquire file lock for {file_path} after {max_retries} attempts: {e}")
                    return False
                    
    except Exception as e:
        logger.error(f"Error writing JSON file {file_path}: {e}", exc_info=True)
        return False
        
    finally:
        # Cleanup: close file handle and remove temp file if rename failed
        if file_handle:
            try:
                if os.name == 'posix' and HAS_FCNTL:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                elif os.name == 'nt' and HAS_MSVCRT:
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                file_handle.close()
            except:
                pass
        
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()  # Remove temp file if it still exists
            except:
                pass
    
    return False


def safe_json_read(file_path: Path, default: Any = None, max_retries: int = 3) -> Any:
    """
    Safely read JSON file with file locking.
    
    This function prevents reading a file while it's being written,
    which could result in reading corrupted or incomplete data.
    
    Args:
        file_path: Path to the JSON file to read
        default: Default value to return if file doesn't exist or read fails
        max_retries: Maximum number of retry attempts if lock fails
        
    Returns:
        Parsed JSON data, or default value if read fails
    """
    if not file_path.exists():
        return default if default is not None else {}
    
    file_handle = None
    
    try:
        for attempt in range(max_retries):
            try:
                file_handle = open(file_path, 'r', encoding='utf-8')
                
                # Lock for reading (shared lock on Unix, exclusive on Windows)
                try:
                    if os.name == 'posix' and HAS_FCNTL:
                        fcntl.flock(file_handle.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    elif os.name == 'nt' and HAS_MSVCRT:
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
                except (NameError, OSError):
                    pass
                
                # Read and parse JSON
                data = json.load(file_handle)
                
                # Unlock
                try:
                    if os.name == 'posix' and HAS_FCNTL:
                        fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                    elif os.name == 'nt' and HAS_MSVCRT:
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except (NameError, OSError):
                    pass
                
                file_handle.close()
                file_handle = None
                
                return data
                
            except (IOError, OSError) as e:
                if file_handle:
                    try:
                        if os.name == 'posix':
                            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                        elif os.name == 'nt':
                            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                        file_handle.close()
                    except:
                        pass
                    file_handle = None
                
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    logger.error(f"Failed to read JSON file {file_path}: {e}")
                    return default if default is not None else {}
                    
            except json.JSONDecodeError as e:
                if file_handle:
                    try:
                        if os.name == 'posix':
                            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                        elif os.name == 'nt':
                            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                        file_handle.close()
                    except:
                        pass
                    file_handle = None
                
                logger.error(f"JSON decode error reading {file_path}: {e}")
                return default if default is not None else {}
                
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {e}", exc_info=True)
        return default if default is not None else {}
        
    finally:
        if file_handle:
            try:
                if os.name == 'posix' and HAS_FCNTL:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                elif os.name == 'nt' and HAS_MSVCRT:
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                file_handle.close()
            except:
                pass
    
    return default if default is not None else {}


class TransactionManager:
    """
    Simple transaction manager for JSON file operations.
    
    This ensures that multi-step operations either complete fully or roll back completely,
    preventing partial updates that could leave data in an inconsistent state.
    
    Why this is important:
    - Prevents orphaned records (e.g., user created but quota not assigned)
    - Ensures data consistency across related operations
    - Provides automatic rollback on errors
    
    Example:
        with TransactionManager() as tx:
            # Step 1: Create user
            user_manager.add_user("newuser", user_data)
            tx.add_rollback(lambda: user_manager.remove_user("newuser"))
            
            # Step 2: Assign quota
            quota_manager.assign_quota("newuser", 100)
            tx.add_rollback(lambda: quota_manager.remove_quota("newuser"))
            
            # If any step fails, all rollbacks execute automatically
            tx.commit()  # Mark as successful
    """
    
    def __init__(self):
        self.rollback_actions: List[Callable] = []
        self.committed = False
    
    def add_rollback(self, action: Callable):
        """
        Add a rollback action to be executed if transaction fails.
        
        Args:
            action: Callable that performs the rollback (e.g., lambda function)
        """
        self.rollback_actions.append(action)
    
    def commit(self):
        """Mark transaction as committed - rollbacks will not execute."""
        self.committed = True
    
    def rollback(self):
        """Execute all rollback actions in reverse order."""
        for action in reversed(self.rollback_actions):
            try:
                action()
            except Exception as e:
                logger.error(f"Rollback action failed: {e}", exc_info=True)
        self.rollback_actions.clear()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - rollback if exception occurred."""
        if exc_type is not None:
            # Exception occurred - rollback
            logger.warning(f"Transaction failed, rolling back: {exc_val}")
            self.rollback()
        elif not self.committed:
            # No exception but not committed - rollback
            logger.warning("Transaction not committed, rolling back")
            self.rollback()
        # If committed and no exception, do nothing (success)
        return False  # Don't suppress exceptions


class SessionManager:
    """Manages user sessions to enforce single concurrent session per user."""

    def __init__(self):
        self.base_dir = Path("dashboard_data")
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_file = self.sessions_dir / "active_sessions.json"
        self.session_timeout_hours = 24  # Sessions expire after 24 hours of inactivity
        self._ensure_directories()
        self._cleanup_expired_sessions()

    def _ensure_directories(self):
        """Create necessary directories."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_expired_sessions(self):
        """Remove expired sessions from storage."""
        try:
            if not self.sessions_file.exists():
                return

            sessions = safe_json_read(self.sessions_file, default={})
            if not sessions:
                return

            # Filter out expired sessions
            current_time = datetime.now()
            active_sessions = {}

            for user, session_data in sessions.items():
                session_time = datetime.fromisoformat(session_data['last_activity'])
                if current_time - session_time < timedelta(hours=self.session_timeout_hours):
                    active_sessions[user] = session_data
                else:
                    logger.info(f"Cleaned up expired session for user: {user}")

            # Save cleaned sessions with file locking
            safe_json_write(self.sessions_file, active_sessions)

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error cleaning up expired sessions: {e}")

    def create_session(self, username: str, session_id: str) -> bool:
        """
        Create a new session for user, invalidating any existing session.

        Args:
            username: Username for the session
            session_id: Unique session identifier

        Returns:
            True if session created successfully
        """
        try:
            # Load existing sessions with file locking
            sessions = safe_json_read(self.sessions_file, default={})

            # Create new session data
            session_data = {
                'session_id': session_id,
                'username': username,
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat(),
                'ip_address': getattr(st, 'request', {}).get('remote_ip', 'unknown'),
                'user_agent': getattr(st, 'request', {}).get('headers', {}).get('user-agent', 'unknown')
            }

            # Replace any existing session for this user
            old_session = sessions.get(username)
            if old_session:
                logger.info(f"Invalidating existing session for user {username}: {old_session['session_id']}")

            sessions[username] = session_data

            # Save sessions with file locking
            safe_json_write(self.sessions_file, sessions)

            logger.info(f"Created new session for user {username}: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating session for {username}: {e}")
            return False

    def validate_session(self, username: str, session_id: str) -> bool:
        """
        Validate if a session is active and belongs to the user.

        Args:
            username: Username to validate
            session_id: Session ID to validate

        Returns:
            True if session is valid and active
        """
        try:
            if not self.sessions_file.exists():
                return False

            sessions = safe_json_read(self.sessions_file, default={})
            if not sessions:
                # File might be corrupted or empty, reset it
                safe_json_write(self.sessions_file, {})
                sessions = {}

            user_session = sessions.get(username)
            if not user_session:
                return False

            # Check if session matches and is not expired
            if user_session['session_id'] != session_id:
                return False

            session_time = datetime.fromisoformat(user_session['last_activity'])
            if datetime.now() - session_time > timedelta(hours=self.session_timeout_hours):
                # Session expired, remove it
                del sessions[username]
                safe_json_write(self.sessions_file, sessions)
                return False

            # Update last activity
            user_session['last_activity'] = datetime.now().isoformat()
            sessions[username] = user_session
            safe_json_write(self.sessions_file, sessions)

            return True

        except Exception as e:
            logger.error(f"Error validating session for {username}: {e}")
            return False

    def invalidate_session(self, username: str, session_id: str = None) -> bool:
        """
        Invalidate a user's session.

        Args:
            username: Username whose session to invalidate
            session_id: Optional session ID to match (for security)

        Returns:
            True if session was invalidated
        """
        try:
            if not self.sessions_file.exists():
                return False

            sessions = safe_json_read(self.sessions_file, default={})
            if not sessions:
                safe_json_write(self.sessions_file, {})
                sessions = {}

            user_session = sessions.get(username)
            if not user_session:
                return False

            # If session_id provided, verify it matches
            if session_id and user_session['session_id'] != session_id:
                logger.warning(f"Session ID mismatch for user {username}")
                return False

            # Remove the session
            del sessions[username]
            safe_json_write(self.sessions_file, sessions)

            logger.info(f"Invalidated session for user {username}")
            return True

        except Exception as e:
            logger.error(f"Error invalidating session for {username}: {e}")
            return False

    def check_existing_session(self, username: str) -> Optional[str]:
        """
        Check if user has an existing active session.

        Args:
            username: Username to check

        Returns:
            Session ID if active session exists, None otherwise
        """
        try:
            if not self.sessions_file.exists():
                return None

            sessions = safe_json_read(self.sessions_file, default={})
            if not sessions:
                safe_json_write(self.sessions_file, {})
                sessions = {}

            user_session = sessions.get(username)
            if not user_session:
                return None

            # Check if session is not expired
            session_time = datetime.fromisoformat(user_session['last_activity'])
            if datetime.now() - session_time > timedelta(hours=self.session_timeout_hours):
                # Session expired, remove it
                del sessions[username]
                safe_json_write(self.sessions_file, sessions)
                return None

            return user_session['session_id']

        except Exception as e:
            logger.error(f"Error checking existing session for {username}: {e}")
            return None

    def get_session_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a user's active session.

        Args:
            username: Username to get session info for

        Returns:
            Session information dict or None if no active session
        """
        try:
            if not self.sessions_file.exists():
                return None

            sessions = safe_json_read(self.sessions_file, default={})
            if not sessions:
                safe_json_write(self.sessions_file, {})
                sessions = {}

            user_session = sessions.get(username)
            if not user_session:
                return None

            # Check if session is not expired
            session_time = datetime.fromisoformat(user_session['last_activity'])
            if datetime.now() - session_time > timedelta(hours=self.session_timeout_hours):
                return None

            return user_session

        except Exception as e:
            logger.error(f"Error getting session info for {username}: {e}")
            return None

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active (non-expired) sessions.

        Returns:
            Dict of username -> session_info for all active sessions
        """
        try:
            if not self.sessions_file.exists():
                return {}

            sessions = safe_json_read(self.sessions_file, default={})
            if not sessions:
                safe_json_write(self.sessions_file, {})
                sessions = {}

            # Filter out expired sessions and return active ones
            current_time = datetime.now()
            active_sessions = {}

            for user, session_data in sessions.items():
                session_time = datetime.fromisoformat(session_data['last_activity'])
                if current_time - session_time < timedelta(hours=self.session_timeout_hours):
                    active_sessions[user] = session_data

            return active_sessions

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return {}


class UserManager:
    """Manages user credentials with persistent storage and role-based access control."""
    
    # Define user roles
    ROLE_OWNER = "Owner"
    ROLE_ADMIN = "Admin"
    ROLE_AUDITOR = "Auditor"
    
    # Owner account that cannot be modified by others
    PROTECTED_OWNER = "Mohamed Abdo"

    # Relaxed security: only the exact owner account is protected
    # Keep variants list empty so no other usernames are auto-protected
    PROTECTED_VARIANTS = []

    def __init__(self):
        self.base_dir = Path("dashboard_data")
        self.users_dir = self.base_dir / "users"
        self.users_file = self.users_dir / "users.json"
        self._ensure_directories()
        self._initialize_users()
    
    def _is_protected_owner_variant(self, username: str) -> bool:
        """Check if username is a variant of the protected owner name.

        With relaxed rules, only the exact 'Mohamed Abdo' account is protected;
        other usernames (including 'abdo') are not treated as protected variants.
        """
        return False
    
    def _log_security_incident(self, incident_type: str, target_username: str, actor_username: str = None):
        """Log security incidents for audit trail."""
        try:
            import datetime
            
            incident = {
                "timestamp": datetime.datetime.now().isoformat(),
                "type": incident_type,
                "target_user": target_username,
                "actor_user": actor_username or "UNKNOWN",
                "severity": "CRITICAL" if "DELETION" in incident_type else "HIGH"
            }
            
            # Log to file for audit trail
            security_log_file = self.base_dir / "security_incidents.log"
            with open(security_log_file, 'a') as f:
                f.write(f"{incident['timestamp']} - {incident['type']} - Target: {incident['target_user']} - Actor: {incident['actor_user']}\n")
            
            logger.critical(f"SECURITY INCIDENT LOGGED: {incident}")
            
        except Exception as e:
            logger.error(f"Failed to log security incident: {e}")

    def _ensure_directories(self):
        """Create necessary directories."""
        self.users_dir.mkdir(parents=True, exist_ok=True)

    def _initialize_users(self):
        """Initialize users file with default users if it doesn't exist."""
        if not self.users_file.exists():
            # Import default users from config
            try:
                from config import USER_CREDENTIALS as default_users
                import os

                # Optional: single initial password for all default users on fresh deployments
                # This value should be provided via environment variable (e.g. on RunPod)
                # so no plaintext passwords are stored in code or JSON.
                initial_password = os.getenv("DEFAULT_APP_PASSWORD")

                if not initial_password:
                    logger.warning(
                        "DEFAULT_APP_PASSWORD is not set. Default users will be created without app passwords; "
                        "you must set passwords via the dashboard before they can log in."
                    )

                # Create each default user using the secure add_user path so passwords are hashed
                for username, user_data in default_users.items():
                    new_user_data = {}

                    # Preserve daily_limit or other numeric settings from config
                    if isinstance(user_data, dict):
                        if "daily_limit" in user_data:
                            new_user_data["daily_limit"] = user_data["daily_limit"]

                    # Assign roles based on username
                    if username == self.PROTECTED_OWNER:
                        new_user_data["role"] = self.ROLE_OWNER
                    elif username == "Aya":
                        new_user_data["role"] = self.ROLE_ADMIN
                    else:
                        new_user_data["role"] = self.ROLE_AUDITOR

                    # If an initial password is provided, use it so the account is usable on first run
                    if initial_password:
                        new_user_data["app_pass"] = initial_password

                    # Use add_user so hashing/encryption logic in security_manager is applied
                    created = self.add_user(username, new_user_data)
                    if not created:
                        logger.warning(f"Failed to create default user '{username}' during initialization")

                logger.info("Initialized users file with default users from config.py using secure password handling")
            except ImportError:
                logger.warning("Could not import default users from config.py")
                self.save_all_users({})
        else:
            # Migrate existing users to add roles if they don't have them
            self._migrate_users_to_roles()

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """Get all users from persistent storage with file locking."""
        return safe_json_read(self.users_file, default={})

    def save_all_users(self, users: Dict[str, Dict[str, Any]]) -> bool:
        """Save all users to persistent storage with file locking to prevent race conditions."""
        success = safe_json_write(self.users_file, users)
        if success:
            logger.info(f"Saved {len(users)} users to persistent storage")
        else:
            logger.error(f"Failed to save users to persistent storage")
        return success

    def add_user(self, username: str, user_data: Dict[str, Any], created_by: str = None) -> bool:
        """Add a new user with secure password handling and role assignment."""
        try:
            users = self.get_all_users()
            if username in users:
                return False  # User already exists
            
            # Ensure new users have a role (default to Auditor)
            if 'role' not in user_data:
                user_data['role'] = self.ROLE_AUDITOR
            
            # Store creator information for permission tracking
            if created_by:
                user_data['created_by'] = created_by
                user_data['created_date'] = str(datetime.now())
                
                creator_role = self.get_user_role(created_by)
                requested_role = user_data.get('role', self.ROLE_AUDITOR)
                
                # Only Owner can create Admin users
                if requested_role == self.ROLE_ADMIN and creator_role != self.ROLE_OWNER:
                    logger.warning(f"User {created_by} (role: {creator_role}) attempted to create Admin user {username}")
                    user_data['role'] = self.ROLE_AUDITOR  # Force to Auditor
                
                # Only Owner can create Owner users (though this should never happen)
                if requested_role == self.ROLE_OWNER and creator_role != self.ROLE_OWNER:
                    logger.warning(f"User {created_by} (role: {creator_role}) attempted to create Owner user {username}")
                    user_data['role'] = self.ROLE_AUDITOR  # Force to Auditor
            
            # Secure password handling
            if SECURITY_AVAILABLE and 'app_pass' in user_data:
                # Hash the app password
                password = user_data['app_pass']
                hashed_password, salt = security_manager.hash_password(password)
                user_data['app_pass_hash'] = hashed_password
                user_data['app_pass_salt'] = salt
                del user_data['app_pass']  # Remove plain text password
                
                # Encrypt ReadyMode credentials if provided
                if 'readymode_pass' in user_data and user_data['readymode_pass']:
                    # Make sure we encrypt the plain text password
                    plain_password = user_data['readymode_pass']
                    user_data['readymode_pass_encrypted'] = security_manager.encrypt_string(plain_password)
                    del user_data['readymode_pass']  # Remove plain text password
                    
                    logger.info(f"Added user {username} with secure password hashing and ReadyMode encryption")
                else:
                    logger.info(f"Added user {username} with secure password hashing")
            else:
                logger.warning(f"Added user {username} with role {user_data['role']} and plain text password (security not available)")
            
            users[username] = user_data
            return self.save_all_users(users)
        except Exception as e:
            logger.error(f"Error adding user {username}: {e}")
            return False

    def remove_user(self, username: str, removed_by: str = None) -> bool:
        """Remove a user with role-based permissions."""
        try:
            users = self.get_all_users()
            if username not in users:
                logger.warning(f"User {username} does not exist")
                return False
            
            # MAXIMUM SECURITY: Protect Mohamed Abdo account from deletion
            if username == self.PROTECTED_OWNER or username.lower() == "mohamed abdo":
                logger.critical(f"SECURITY ALERT: Attempted to delete PROTECTED Owner account {username} by {removed_by}")
                # Log security incident
                self._log_security_incident("DELETION_ATTEMPT", username, removed_by)
                return False
            
            # Additional check for any variation of the protected name
            if self._is_protected_owner_variant(username):
                logger.critical(f"SECURITY ALERT: Attempted to delete protected Owner variant {username} by {removed_by}")
                self._log_security_incident("DELETION_ATTEMPT_VARIANT", username, removed_by)
                return False
            
            # Check permissions for user removal - Owner only
            if removed_by:
                remover_role = self.get_user_role(removed_by)
                
                # Only Owner can remove users
                if remover_role != self.ROLE_OWNER:
                    logger.warning(f"User {removed_by} (role: {remover_role}) attempted to remove user {username} - insufficient permissions")
                    return False
            
            # Clean up quota system if user was managed by an admin
            if QUOTA_SYSTEM_AVAILABLE:
                try:
                    from quota_manager import quota_manager
                    if quota_manager:
                        # Check if this user was under quota management
                        user_quota_status = quota_manager.get_user_quota_status(username)
                        if user_quota_status.get("managed"):
                            admin_username = user_quota_status.get("admin")
                            if admin_username:
                                # Remove user from admin's quota management
                                quota_manager.remove_user_from_admin(username, admin_username)
                                logger.info(f"Removed user {username} from admin {admin_username}'s quota management")
                except Exception as e:
                    logger.error(f"Error cleaning up quota system for user {username}: {e}")
                    # Continue with user deletion even if quota cleanup fails
            
            del users[username]
            return self.save_all_users(users)
        except Exception as e:
            logger.error(f"Error removing user {username}: {e}")
            return False

    def update_user(self, username: str, user_data: Dict[str, Any], updated_by: str = None) -> bool:
        """Update user data with role-based permissions."""
        try:
            users = self.get_all_users()
            if username not in users:
                logger.warning(f"User {username} does not exist")
                return False
            
            # MAXIMUM SECURITY: Protect Mohamed Abdo account from ANY modifications
            if username == self.PROTECTED_OWNER or username.lower() == "mohamed abdo":
                if updated_by != self.PROTECTED_OWNER:
                    logger.critical(f"SECURITY ALERT: User {updated_by} attempted to modify PROTECTED Owner account {username}")
                    self._log_security_incident("MODIFICATION_ATTEMPT", username, updated_by)
                    return False
                else:
                    # Even when updated by the Owner, only allow ReadyMode credentials to be changed
                    if user_data:
                        allowed_fields = {"readymode_user", "readymode_pass"}
                        user_data = {k: v for k, v in user_data.items() if k in allowed_fields}
            
            # Additional check for any variation of the protected name
            if self._is_protected_owner_variant(username):
                if updated_by != self.PROTECTED_OWNER:
                    logger.critical(f"SECURITY ALERT: User {updated_by} attempted to modify protected Owner variant {username}")
                    self._log_security_incident("MODIFICATION_ATTEMPT_VARIANT", username, updated_by)
                    return False
            
            # Check if user has permission to modify this user
            if updated_by and not self.can_admin_modify_user(updated_by, username):
                logger.warning(f"User {updated_by} does not have permission to modify {username}")
                return False
            
            # Validate role change permissions
            if updated_by and 'role' in user_data:
                updater_role = self.get_user_role(updated_by)
                new_role = user_data['role']
                current_role = users[username].get('role', self.ROLE_AUDITOR)
                
                # Only Owner can change roles to/from Owner or Admin
                if (new_role in [self.ROLE_OWNER, self.ROLE_ADMIN] or 
                    current_role in [self.ROLE_OWNER, self.ROLE_ADMIN]) and updater_role != self.ROLE_OWNER:
                    logger.warning(f"User {updated_by} (role: {updater_role}) attempted to change role for {username}")
                    # Remove role change from update
                    user_data = user_data.copy()
                    del user_data['role']
            
            # Merge with existing data to preserve fields not being updated
            updated_data = users[username].copy()
            updated_data.update(user_data)
            
            # Handle ReadyMode password encryption if it's being updated
            if SECURITY_AVAILABLE and 'readymode_pass' in updated_data and updated_data['readymode_pass']:
                # Encrypt the new password
                plain_password = updated_data['readymode_pass']
                updated_data['readymode_pass_encrypted'] = security_manager.encrypt_string(plain_password)
                del updated_data['readymode_pass']  # Remove plain text
                
                # Remove any existing encrypted password to avoid conflicts
                if 'readymode_pass_encrypted' in users[username]:
                    del users[username]['readymode_pass_encrypted']
                    
            users[username] = updated_data
            
            return self.save_all_users(users)
        except Exception as e:
            logger.error(f"Error updating user {username}: {e}")
            return False

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get specific user data."""
        users = self.get_all_users()
        return users.get(username)

    def user_exists(self, username: str) -> bool:
        """Check if user exists."""
        return username in self.get_all_users()
    
    def verify_user_password(self, username: str, password: str) -> bool:
        """
        Verify user password securely.
        
        Args:
            username: Username to verify
            password: Plain text password to verify
            
        Returns:
            bool: True if password is correct
        """
        try:
            user_data = self.get_user(username)
            if not user_data:
                return False
            
            # Check if using secure hashed passwords
            if SECURITY_AVAILABLE and 'app_pass_hash' in user_data and 'app_pass_salt' in user_data:
                # Verify hashed password
                return security_manager.verify_password(
                    password, 
                    user_data['app_pass_hash'], 
                    user_data['app_pass_salt']
                )
            elif 'app_pass' in user_data:
                # Fallback to plain text comparison (legacy)
                logger.warning(f"Using plain text password verification for {username} - consider migrating to hashed passwords")
                return user_data['app_pass'] == password
            else:
                logger.error(f"No password data found for user {username}")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying password for {username}: {e}")
            return False
    
    def get_user_readymode_credentials(self, username: str) -> tuple:
        """
        Get decrypted ReadyMode credentials for a user.
        
        Args:
            username: Username
            
        Returns:
            tuple: (readymode_user, readymode_pass) or (None, None) if not found
        """
        try:
            user_data = self.get_user(username)
            if not user_data:
                logger.warning(f"No user data found for {username}")
                return None, None

            readymode_user = user_data.get('readymode_user')

            # Debug logging
            logger.info(f"ReadyMode credentials for {username}: user={readymode_user}, has_encrypted={'readymode_pass_encrypted' in user_data}, has_plain={'readymode_pass' in user_data}")

            # Check if password is encrypted
            if SECURITY_AVAILABLE and 'readymode_pass_encrypted' in user_data:
                encrypted_pass = user_data['readymode_pass_encrypted']
                readymode_pass = security_manager.decrypt_string(encrypted_pass)
                logger.info(f"Decrypted ReadyMode password for {username}: length={len(readymode_pass) if readymode_pass else 0}")
            else:
                # Fallback to plain text (legacy)
                readymode_pass = user_data.get('readymode_pass')
                logger.info(f"Using plain text ReadyMode password for {username}: length={len(readymode_pass) if readymode_pass else 0}")

            return readymode_user, readymode_pass

        except Exception as e:
            logger.error(f"Error getting ReadyMode credentials for {username}: {e}")
            return None, None
    
    def get_user_role(self, username: str) -> str:
        """
        Get the role of a user.
        
        Args:
            username: Username to get role for
            
        Returns:
            User role (Owner/Admin/Auditor) or Auditor as default
        """
        user_data = self.get_user(username)
        if not user_data:
            return self.ROLE_AUDITOR  # Default role for non-existent users
        
        return user_data.get('role', self.ROLE_AUDITOR)
    
    def has_settings_access(self, username: str) -> bool:
        """
        Check if user has access to Settings tab.
        
        Args:
            username: Username to check
            
        Returns:
            True if user can access Settings tab
        """
        role = self.get_user_role(username)
        return role in [self.ROLE_OWNER, self.ROLE_ADMIN]
    
    def can_manage_users(self, username: str) -> bool:
        """
        Check if user can manage other users.
        
        Args:
            username: Username to check
            
        Returns:
            True if user can create users (Admin can only create, Owner can create/modify/delete)
        """
        role = self.get_user_role(username)
        return role in [self.ROLE_OWNER, self.ROLE_ADMIN]
    
    def can_modify_users(self, username: str) -> bool:
        """
        Check if user can modify/delete other users.
        
        Args:
            username: Username to check
            
        Returns:
            True if user can modify/delete users (Owner only)
        """
        role = self.get_user_role(username)
        return role == self.ROLE_OWNER
    
    def can_admin_modify_user(self, admin_username: str, target_username: str) -> bool:
        """
        Check if Admin can modify a specific user they created.
        
        Args:
            admin_username: Admin username
            target_username: Target user to modify
            
        Returns:
            True if Admin can modify this user
        """
        admin_role = self.get_user_role(admin_username)
        
        # Owner can modify anyone
        if admin_role == self.ROLE_OWNER:
            return True
        
        # Admin can only modify users they created
        if admin_role == self.ROLE_ADMIN:
            # Check if this user was created by this admin
            if QUOTA_SYSTEM_AVAILABLE:
                try:
                    from lib.quota_manager import quota_manager
                    if quota_manager:
                        created_users = quota_manager.get_admin_created_users(admin_username)
                        return target_username in created_users
                except Exception as e:
                    logger.debug(f"Error checking quota manager for user creation: {e}")
                    pass
            
            # Fallback: check user creation metadata if available
            users = self.get_all_users()
            target_user_data = users.get(target_username, {})
            return target_user_data.get('created_by') == admin_username
        
        return False
    
    def can_end_sessions(self, username: str, target_username: str = None) -> bool:
        """
        Check if user can end sessions.
        
        Args:
            username: Username requesting the action
            target_username: Username whose session to end (optional)
            
        Returns:
            True if user can end the specified session
        """
        role = self.get_user_role(username)
        
        # Owner and Admin can end sessions
        if role not in [self.ROLE_OWNER, self.ROLE_ADMIN]:
            return False
        
        # If no target specified, they can end sessions in general
        if not target_username:
            return True
        
        # MAXIMUM SECURITY: Cannot end Mohamed Abdo's session unless you are Mohamed Abdo
        if target_username == self.PROTECTED_OWNER and username != self.PROTECTED_OWNER:
            logger.critical(f"SECURITY ALERT: User {username} attempted to end PROTECTED Owner session {target_username}")
            self._log_security_incident("SESSION_END_ATTEMPT", target_username, username)
            return False
        
        # Additional check for any variation of the protected name
        if target_username and self._is_protected_owner_variant(target_username):
            if username != self.PROTECTED_OWNER:
                logger.critical(f"SECURITY ALERT: User {username} attempted to end protected Owner variant session {target_username}")
                self._log_security_incident("SESSION_END_ATTEMPT_VARIANT", target_username, username)
                return False
        
        return True
    
    def can_modify_user(self, modifier_username: str, target_username: str) -> bool:
        """
        Check if user can modify another user.
        
        Args:
            modifier_username: Username requesting the modification
            target_username: Username to be modified
            
        Returns:
            True if modification is allowed
        """
        # MAXIMUM SECURITY: Mohamed Abdo account is completely protected
        if target_username == self.PROTECTED_OWNER and modifier_username != self.PROTECTED_OWNER:
            logger.critical(f"SECURITY ALERT: User {modifier_username} attempted to modify PROTECTED Owner {target_username}")
            self._log_security_incident("USER_MODIFICATION_ATTEMPT", target_username, modifier_username)
            return False
        
        # Additional check for any variation of the protected name
        if self._is_protected_owner_variant(target_username):
            if modifier_username != self.PROTECTED_OWNER:
                logger.critical(f"SECURITY ALERT: User {modifier_username} attempted to modify protected Owner variant {target_username}")
                self._log_security_incident("USER_MODIFICATION_ATTEMPT_VARIANT", target_username, modifier_username)
                return False
        
        modifier_role = self.get_user_role(modifier_username)
        
        # Owner can modify any user (except protected Owner)
        if modifier_role == self.ROLE_OWNER:
            return True
        
        # Admin can modify users they created (quota system + fallback)
        if modifier_role == self.ROLE_ADMIN:
            # Use the comprehensive method that includes both quota and non-quota users
            created_users = self.get_admin_created_users(modifier_username)
            return target_username in created_users
        
        # Auditors cannot modify other users
        return False
    
    def _migrate_users_to_roles(self):
        """
        Migrate existing users to add roles if they don't have them.
        """
        try:
            users = self.get_all_users()
            updated = False
            
            for username, user_data in users.items():
                if 'role' not in user_data:
                    # Assign role based on username
                    if username == self.PROTECTED_OWNER:
                        user_data['role'] = self.ROLE_OWNER
                    else:
                        user_data['role'] = self.ROLE_AUDITOR
                    updated = True
                    logger.info(f"Migrated user {username} to role {user_data['role']}")
                    
                # Migrate plain text ReadyMode passwords to encrypted
                if SECURITY_AVAILABLE and 'readymode_pass' in user_data and user_data['readymode_pass'] and 'readymode_pass_encrypted' not in user_data:
                    try:
                        encrypted_pass = security_manager.encrypt_string(user_data['readymode_pass'])
                        user_data['readymode_pass_encrypted'] = encrypted_pass
                        del user_data['readymode_pass']  # Remove plain text
                        updated = True
                        logger.info(f"Migrated ReadyMode password for user {username} to encrypted storage")
                    except Exception as e:
                        logger.error(f"Failed to encrypt ReadyMode password for user {username}: {e}")
            
            if updated:
                self.save_all_users(users)
                logger.info("Completed user migration (roles and password encryption)")
                
        except Exception as e:
            logger.error(f"Error during user migration: {e}")
    
    def invalidate_user_session(self, username: str, invalidated_by: str = None) -> bool:
        """
        Invalidate a user's active session (for admin use).
        
        Args:
            username: Username whose session to invalidate
            invalidated_by: Username performing the action
            
        Returns:
            True if session was invalidated successfully
        """
        # Check if the invalidator has permission
        if invalidated_by:
            if not self.can_end_sessions(invalidated_by, username):
                logger.warning(f"User {invalidated_by} attempted to invalidate session for {username} without permission")
                return False
        
        return session_manager.invalidate_session(username)
    
    # ===== QUOTA MANAGEMENT INTEGRATION =====
    
    def create_user_with_quota(self, username: str, user_data: Dict[str, Any], created_by: str, daily_quota: int = None) -> Tuple[bool, str]:
        """
        Create a user with quota assignment (for Admin users).
        
        Args:
            username: New username
            user_data: User data including password, role, etc.
            created_by: Admin username creating this user
            daily_quota: Daily quota to assign to this user
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not QUOTA_SYSTEM_AVAILABLE:
            # Fallback to regular user creation
            success = self.add_user(username, user_data, created_by)
            return success, "User created (quota system not available)"
        
        creator_role = self.get_user_role(created_by)
        
        # Only Admin and Owner can create users with quota
        if creator_role not in [self.ROLE_ADMIN, self.ROLE_OWNER]:
            return False, "Insufficient permissions to create users"
        
        # For Admin users, check quota limits
        if creator_role == self.ROLE_ADMIN:
            can_create, message = quota_manager.can_admin_create_user(created_by)
            if not can_create:
                return False, f"Cannot create user: {message}"
            
            if daily_quota and not quota_manager.can_admin_assign_quota(created_by, daily_quota):
                return False, "Insufficient quota available for assignment"
        
        # Use transaction manager to ensure atomicity
        # If user creation succeeds but quota assignment fails, rollback user creation
        with TransactionManager() as tx:
            # Step 1: Create the user
            success = self.add_user(username, user_data, created_by)
            if not success:
                return False, "Failed to create user"
        
            # Add rollback for user creation
            tx.add_rollback(lambda: self.remove_user(username, created_by))
            
            # Step 2: Assign quota if Admin is creating the user
        if creator_role == self.ROLE_ADMIN and daily_quota:
            quota_success, quota_message = quota_manager.assign_user_to_admin(username, created_by, daily_quota)
            if not quota_success:
                    # Transaction manager will automatically rollback user creation
                return False, f"User creation failed: {quota_message}"
        
                # Add rollback for quota assignment
                tx.add_rollback(lambda: quota_manager.remove_user_from_admin(username, created_by))
            
            # All steps succeeded - commit transaction
            tx.commit()
        return True, "User created successfully with quota assignment"
    
    def remove_user_with_quota(self, username: str, removed_by: str) -> Tuple[bool, str]:
        """
        Remove a user and free up quota (for Admin users).
        
        Args:
            username: Username to remove
            removed_by: Admin username removing this user
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not self.can_modify_user(removed_by, username):
            return False, "Insufficient permissions to remove user"
        
        remover_role = self.get_user_role(removed_by)
        
        # If Admin is removing user, check if it's their user and free quota
        if QUOTA_SYSTEM_AVAILABLE and remover_role == self.ROLE_ADMIN:
            quota_success, quota_message = quota_manager.remove_user_from_admin(username, removed_by)
            if not quota_success:
                return False, f"Cannot remove user: {quota_message}"
        
        # Remove the user - bypass permission check since we already validated
        try:
            users = self.get_all_users()
            if username not in users:
                return False, "User does not exist"
            
            # MAXIMUM SECURITY: Protect Mohamed Abdo account from deletion
            if username == self.PROTECTED_OWNER or username.lower() == "mohamed abdo":
                logger.critical(f"SECURITY ALERT: User {removed_by} attempted to delete PROTECTED Owner account {username} via quota system")
                self._log_security_incident("QUOTA_DELETION_ATTEMPT", username, removed_by)
                return False, "SECURITY VIOLATION: Cannot delete protected Owner account"
            
            # Additional check for any variation of the protected name
            if self._is_protected_owner_variant(username):
                logger.critical(f"SECURITY ALERT: User {removed_by} attempted to delete protected Owner variant {username} via quota system")
                self._log_security_incident("QUOTA_DELETION_ATTEMPT_VARIANT", username, removed_by)
                return False, "SECURITY VIOLATION: Cannot delete protected Owner account variant"
            
            # Delete the user
            del users[username]
            success = self.save_all_users(users)
            
            if success:
                return True, "User removed successfully, quota freed"
            else:
                return False, "Failed to save user data after removal"
        except Exception as e:
            logger.error(f"Error removing user {username}: {e}")
            return False, f"Error removing user: {str(e)}"
    
    def get_admin_quota_info(self, admin_username: str) -> Dict:
        """Get quota information for an Admin user."""
        if not QUOTA_SYSTEM_AVAILABLE:
            return {"error": "Quota system not available"}
        
        if self.get_user_role(admin_username) != self.ROLE_ADMIN:
            return {"error": "User is not an Admin"}
        
        try:
            return quota_manager.get_admin_dashboard_info(admin_username)
        except Exception as e:
            logger.error(f"Error getting admin quota info for {admin_username}: {e}")
            return {"error": f"Unable to load quota information: {str(e)}"}
    
    def get_user_quota_status(self, username: str) -> Dict:
        """Get quota status for any user."""
        if not QUOTA_SYSTEM_AVAILABLE:
            return {"managed": False, "message": "Quota system not available"}
        
        return quota_manager.get_user_quota_status(username)
    
    def set_admin_limits_as_owner(self, admin_username: str, max_users: int, daily_quota: int, owner_username: str) -> Tuple[bool, str]:
        """
        Owner sets limits for an Admin.
        
        Args:
            admin_username: Admin to set limits for
            max_users: Maximum users the admin can create
            daily_quota: Total daily quota for the admin
            owner_username: Owner performing the action
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not QUOTA_SYSTEM_AVAILABLE:
            return False, "Quota system not available"
        
        if self.get_user_role(owner_username) != self.ROLE_OWNER:
            return False, "Only Owner can set Admin limits"
        
        if self.get_user_role(admin_username) != self.ROLE_ADMIN:
            return False, "Target user is not an Admin"
        
        success = quota_manager.set_admin_limits(admin_username, max_users, daily_quota, owner_username)
        if success:
            return True, f"Limits set for {admin_username}: {max_users} users, {daily_quota} daily quota"
        else:
            return False, "Failed to set admin limits"
    
    def get_all_admin_limits_as_owner(self, owner_username: str) -> Dict:
        """Owner gets all Admin limits and usage."""
        if not QUOTA_SYSTEM_AVAILABLE:
            return {"error": "Quota system not available"}
        
        if self.get_user_role(owner_username) != self.ROLE_OWNER:
            return {"error": "Only Owner can view all admin limits"}
        
        return quota_manager.get_all_admin_limits()
    
    def get_admin_created_users(self, admin_username: str) -> List[str]:
        """Get list of users created by specific Admin (includes quota and non-quota users)."""
        created_users = []
        
        # First, get users from quota system
        if QUOTA_SYSTEM_AVAILABLE:
            created_users.extend(quota_manager.get_admin_created_users(admin_username))
        
        # Also check created_by field for users not in quota system
        all_users = self.get_all_users()
        for username, user_data in all_users.items():
            if user_data.get('created_by') == admin_username and username not in created_users:
                created_users.append(username)
        
        return created_users


# Global user manager instance
user_manager = UserManager()


class DashboardManager:
    """Manages dashboard data storage and retrieval."""
    
    def __init__(self):
        self.base_dir = Path("dashboard_data")
        self.agent_audit_dir = self.base_dir / "agent_audits"
        self.campaign_audit_dir = self.base_dir / "campaign_audits"
        self.daily_counters_dir = self.base_dir / "daily_counters"
        self.lite_audit_dir = self.base_dir / "lite_audits"
        self.sharing_config_file = self.base_dir / "dashboard_sharing.json"
        self._ensure_directories()
        
        # Initialize sharing configuration
        self._initialize_sharing_config()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        self.agent_audit_dir.mkdir(parents=True, exist_ok=True)
        self.campaign_audit_dir.mkdir(parents=True, exist_ok=True)
        self.daily_counters_dir.mkdir(parents=True, exist_ok=True)
        self.lite_audit_dir.mkdir(parents=True, exist_ok=True)
    
    def _initialize_sharing_config(self):
        """Initialize the dashboard sharing configuration."""
        if not self.sharing_config_file.exists():
            initial_config = {
                "sharing_groups": {
                    # "group_name": {
                    #     "members": ["user1", "user2"],
                    #     "created_by": "owner_username",
                    #     "created_date": "2025-01-01"
                    # }
                },
                "user_dashboard_mode": {
                    # "username": "isolated" or "group_name"
                }
            }
            safe_json_write(self.sharing_config_file, initial_config)
    
    def _load_sharing_config(self) -> Dict:
        """Load sharing configuration."""
        try:
            with open(self.sharing_config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sharing config: {e}")
            self._initialize_sharing_config()
            return self._load_sharing_config()
    
    def _save_sharing_config(self, config: Dict):
        """Save sharing configuration."""
        try:
            safe_json_write(self.sharing_config_file, config)
        except Exception as e:
            logger.error(f"Error saving sharing config: {e}")
    
    def create_sharing_group(self, group_name: str, members: List[str], created_by: str) -> bool:
        """Create a new dashboard sharing group."""
        try:
            config = self._load_sharing_config()
            
            if group_name in config["sharing_groups"]:
                return False  # Group already exists
            
            config["sharing_groups"][group_name] = {
                "members": members,
                "created_by": created_by,
                "created_date": str(date.today()),
                "last_modified": str(datetime.now())
            }
            
            # Update user dashboard modes
            for member in members:
                config["user_dashboard_mode"][member] = group_name
            
            self._save_sharing_config(config)
            return True
        except Exception as e:
            logger.error(f"Error creating sharing group: {e}")
            return False
    
    def remove_sharing_group(self, group_name: str) -> bool:
        """Remove a dashboard sharing group."""
        try:
            config = self._load_sharing_config()
            
            if group_name not in config["sharing_groups"]:
                return False
            
            group_members = config["sharing_groups"][group_name]["members"]
            
            # Remove group
            del config["sharing_groups"][group_name]
            
            # Reset user modes to isolated
            for member in group_members:
                if member in config["user_dashboard_mode"]:
                    del config["user_dashboard_mode"][member]
            
            self._save_sharing_config(config)
            return True
        except Exception as e:
            logger.error(f"Error removing sharing group: {e}")
            return False
    
    def update_sharing_group(self, group_name: str, new_members: List[str]) -> bool:
        """Update members of a sharing group."""
        try:
            config = self._load_sharing_config()
            
            if group_name not in config["sharing_groups"]:
                return False
            
            old_members = config["sharing_groups"][group_name]["members"]
            
            # Update group
            config["sharing_groups"][group_name]["members"] = new_members
            config["sharing_groups"][group_name]["last_modified"] = str(datetime.now())
            
            # Update user dashboard modes
            # Remove old members
            for member in old_members:
                if member in config["user_dashboard_mode"]:
                    del config["user_dashboard_mode"][member]
            
            # Add new members
            for member in new_members:
                config["user_dashboard_mode"][member] = group_name
            
            self._save_sharing_config(config)
            return True
        except Exception as e:
            logger.error(f"Error updating sharing group: {e}")
            return False
    
    def get_user_dashboard_mode(self, username: str) -> str:
        """Get dashboard mode for a user (isolated or group name)."""
        config = self._load_sharing_config()
        return config["user_dashboard_mode"].get(username, "isolated")
    
    def get_sharing_groups(self) -> Dict:
        """Get all sharing groups."""
        config = self._load_sharing_config()
        return config["sharing_groups"]
    
    def get_shared_users(self, username: str) -> List[str]:
        """Get list of users who share dashboard with the given user."""
        dashboard_mode = self.get_user_dashboard_mode(username)
        
        if dashboard_mode == "isolated":
            return [username]  # Only themselves
        
        config = self._load_sharing_config()
        group = config["sharing_groups"].get(dashboard_mode, {})
        return group.get("members", [username])
    
    def can_access_user_dashboard(self, requesting_user: str, target_user: str) -> bool:
        """Check if requesting user can access target user's dashboard."""
        if requesting_user == target_user:
            return True
        
        # Check if they share a dashboard group
        requesting_mode = self.get_user_dashboard_mode(requesting_user)
        target_mode = self.get_user_dashboard_mode(target_user)
        
        return requesting_mode == target_mode and requesting_mode != "isolated"
    
    def reset_user_to_isolated(self, username: str) -> bool:
        """
        Reset a user to isolated dashboard mode by removing them from their sharing group.
        
        Args:
            username: Username to reset to isolated mode
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config = self._load_sharing_config()
            current_mode = config["user_dashboard_mode"].get(username, "isolated")
            
            if current_mode != "isolated":
                if current_mode in config["sharing_groups"]:
                    group_members = config["sharing_groups"][current_mode]["members"]
                    if username in group_members:
                        group_members.remove(username)
                        
                        # If group becomes empty, remove it entirely
                        if not group_members:
                            del config["sharing_groups"][current_mode]
                        else:
                            config["sharing_groups"][current_mode]["members"] = group_members
                            config["sharing_groups"][current_mode]["last_modified"] = str(datetime.now())
                        
                        # Reset user's dashboard mode
                        if username in config["user_dashboard_mode"]:
                            del config["user_dashboard_mode"][username]
                        
                        self._save_sharing_config(config)
                        return True
            
            return False
        except Exception as e:
            print(f"Error resetting user to isolated mode: {e}")
            return False
    
    def save_agent_audit_results(self, df: pd.DataFrame, username: str = None):
        """
        Append new agent audit results to user-specific storage.
        
        Args:
            df: DataFrame with audit results
            username: Current user's username (optional)
        """
        if df.empty:
            return
        
        if not username:
            username = st.session_state.get('username', 'default_user')
        
        # Initialize storage for this user
        self.initialize_agent_audit_storage(username)
        
        # Add metadata to the DataFrame
        df_with_metadata = df.copy()
        df_with_metadata['audit_timestamp'] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        df_with_metadata['username'] = username
        
        # Load existing data
        try:
            with open(self.agent_audit_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {'login_timestamp': datetime.now().isoformat(), 'audit_results': []}
        
        # Convert DataFrame to dict and append
        df_dict = df_with_metadata.to_dict('records')
        data['audit_results'].extend(df_dict)
        
        # Save back to file with file locking
        safe_json_write(self.agent_audit_file, data)
    
    def initialize_agent_audit_storage(self, username: str = None):
        """
        Initialize agent audit storage - each user gets their own isolated storage file.
        
        SECURITY NOTE: Each user's agent audit results are completely isolated and not shared
        with other users. Each user has their own personal dashboard.
        """
        if not username:
            username = st.session_state.get('username', 'default_user')

        # Each user gets their own isolated dashboard file
        self.agent_audit_file = self.agent_audit_dir / f"agent_audits_{username}.json"
        
        # Initialize file if it doesn't exist
        if not self.agent_audit_file.exists():
            initial_data = {
                'login_timestamp': datetime.now().isoformat(),
                'audit_results': []
            }
            safe_json_write(self.agent_audit_file, initial_data)
    
    def get_combined_agent_audit_data(self, username: str = None) -> pd.DataFrame:
        """
        Combine all agent audit results from user-specific storage.
        Supports shared dashboards - users in sharing groups see combined data.
        
        Args:
            username: Username to load data for
        
        Returns:
            Combined DataFrame of all agent audit results for the user/group
        """
        if not username:
            username = st.session_state.get('username', 'default_user')
        
        # Get all users whose data this user can access
        shared_users = self.get_shared_users(username)
        
        all_data = []
        
        for shared_user in shared_users:
            # Initialize storage for this user
            self.initialize_agent_audit_storage(shared_user)
            
            # Load data from user-specific file
            try:
                with open(self.agent_audit_file, 'r') as f:
                    data = json.load(f)
                
                if not data.get('audit_results'):
                    continue  # No data for this user
                
                # Convert to DataFrame
                user_df = pd.DataFrame(data['audit_results'])
                if not user_df.empty:
                    all_data.append(user_df)
                
            except (FileNotFoundError, json.JSONDecodeError):
                continue  # Skip if file doesn't exist or is corrupted
        
        if not all_data:
            return pd.DataFrame()
        
        # Combine all data from shared users
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Remove duplicates based on phone number, keeping the most recent entry
        if not combined_df.empty and 'Phone Number' in combined_df.columns:
            # Sort by audit_timestamp (most recent first) and drop duplicates by phone number
            combined_df = combined_df.sort_values('audit_timestamp', ascending=False)
            combined_df = combined_df.drop_duplicates(subset=['Phone Number'], keep='first')
            # Sort back by timestamp for display (most recent first)
            combined_df = combined_df.sort_values('audit_timestamp', ascending=False)
        
        return combined_df
    
    def initialize_lite_audit_storage(self, username: str = None):
        """
        Initialize lite audit storage - each user gets their own isolated storage file.
        
        SECURITY NOTE: Each user's lite audit results are completely isolated and not shared
        with other users. Each user has their own personal dashboard.
        """
        if not username:
            username = 'shared'  # fallback for backwards compatibility

        # Each user gets their own isolated dashboard file
        self.lite_audit_file = self.lite_audit_dir / f"lite_audits_{username}.json"
        
        # Initialize file if it doesn't exist
        if not self.lite_audit_file.exists():
            initial_data = {
                'login_timestamp': datetime.now().isoformat(),
                'audit_results': []
            }
            safe_json_write(self.lite_audit_file, initial_data)
    
    def save_lite_audit_results(self, df: pd.DataFrame, username: str = None):
        """
        Append new lite audit results to user-specific storage.
        
        Args:
            df: DataFrame with lite audit results
            username: Current user's username (optional)
        """
        if df.empty:
            return
        
        if not username:
            username = st.session_state.get('username', 'default_user')
        
        # Initialize storage for this user
        self.initialize_lite_audit_storage(username)
        
        # Add metadata to the DataFrame
        df_with_metadata = df.copy()
        df_with_metadata['audit_timestamp'] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        df_with_metadata['username'] = username
        df_with_metadata['audit_type'] = 'lite'
        
        # Load existing data
        try:
            with open(self.lite_audit_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {'login_timestamp': datetime.now().isoformat(), 'audit_results': []}
        
        # Convert DataFrame to dict and append
        df_dict = df_with_metadata.to_dict('records')
        data['audit_results'].extend(df_dict)
        
        # Save back to file with file locking
        safe_json_write(self.lite_audit_file, data)
    
    def get_combined_lite_audit_data(self, username: str = None) -> pd.DataFrame:
        """
        Combine all lite audit results from user-specific storage.
        Supports shared dashboards - users in sharing groups see combined data.
        
        Args:
            username: Username to load data for
        
        Returns:
            Combined DataFrame of all lite audit results for the user/group
        """
        if not username:
            username = st.session_state.get('username', 'default_user')
        
        # Get all users whose data this user can access
        shared_users = self.get_shared_users(username)
        
        all_data = []
        
        for shared_user in shared_users:
            # Initialize storage for this user
            self.initialize_lite_audit_storage(shared_user)
            
            # Load data from user-specific file
            try:
                with open(self.lite_audit_file, 'r') as f:
                    data = json.load(f)
                
                if not data.get('audit_results'):
                    continue  # No data for this user
                
                # Convert to DataFrame
                user_df = pd.DataFrame(data['audit_results'])
                if not user_df.empty:
                    all_data.append(user_df)
                
            except (FileNotFoundError, json.JSONDecodeError):
                continue  # Skip if file doesn't exist or is corrupted
        
        if not all_data:
            return pd.DataFrame()
        
        # Combine all data from shared users
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Remove duplicates based on phone number, keeping the most recent entry
        if not combined_df.empty and 'Phone Number' in combined_df.columns:
            # Sort by audit_timestamp (most recent first) and drop duplicates by phone number
            combined_df = combined_df.sort_values('audit_timestamp', ascending=False)
            combined_df = combined_df.drop_duplicates(subset=['Phone Number'], keep='first')
            # Sort back by timestamp for display (most recent first)
            combined_df = combined_df.sort_values('audit_timestamp', ascending=False)
        
        return combined_df
    
    def clear_lite_audit_data(self, username: str = None):
        """Clear lite audit data for the specified user."""
        if not username:
            username = st.session_state.get('username', 'default_user')
        
        # Clear the user's individual lite audit file
        self.lite_audit_file = self.lite_audit_dir / f"lite_audits_{username}.json"
        
        # Clear the file by resetting to initial state
        initial_data = {
            'login_timestamp': datetime.now().isoformat(),
            'audit_results': []
        }
        safe_json_write(self.lite_audit_file, initial_data)
    
    def get_daily_download_count(self, username: str) -> int:
        """
        Get today's download count for a user.
        
        Args:
            username: The username to check
            
        Returns:
            int: Number of records downloaded today
        """
        today = datetime.now().date().isoformat()
        counter_file = self.daily_counters_dir / f"{username}_{today}.json"
        
        if not counter_file.exists():
            return 0
        
        try:
            with open(counter_file, 'r') as f:
                data = json.load(f)
            return data.get('download_count', 0)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0
    
    def increment_daily_download_count(self, username: str, count: int):
        """
        Increment the daily download count for a user with quota system integration.
        
        Args:
            username: The username
            count: Number of records to add to the count
        """
        # First, record usage in quota system if available
        if QUOTA_SYSTEM_AVAILABLE:
            try:
                can_use, message = quota_manager.record_user_usage(username, count)
                if can_use:
                    logger.info(f"Quota usage recorded for {username}: {count} units. {message}")
                else:
                    logger.warning(f"Quota exceeded for user {username}: {message}")
                    # Still record in legacy system but log the quota violation
            except Exception as e:
                logger.error(f"Error recording quota usage for {username}: {e}")
                # Continue with legacy system if quota system fails
        
        today = datetime.now().date().isoformat()
        counter_file = self.daily_counters_dir / f"{username}_{today}.json"
        
        # Load existing data
        if counter_file.exists():
            try:
                with open(counter_file, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {'download_count': 0, 'date': today}
        else:
            data = {'download_count': 0, 'date': today}
        
        # Increment count
        data['download_count'] += count
        data['last_updated'] = datetime.now().isoformat()
        
        # Add quota system info if available
        if QUOTA_SYSTEM_AVAILABLE:
            quota_status = quota_manager.get_user_quota_status(username)
            if quota_status.get("managed"):
                data['quota_managed'] = True
                data['quota_status'] = quota_status
        
        # Save back with file locking
        safe_json_write(counter_file, data)
    
    def get_daily_usage_info(self, username: str) -> dict:
        """
        Get daily usage information for a user with quota system integration.
        
        Args:
            username: The username
            
        Returns:
            dict: Usage information
        """
        # First check quota system if available
        if QUOTA_SYSTEM_AVAILABLE:
            quota_status = quota_manager.get_user_quota_status(username)
            if quota_status.get("managed"):
                # User is under quota management - use quota data
                today = datetime.now().date().isoformat()
                return {
                    'username': username,
                    'daily_limit': quota_status["daily_quota"],
                    'current_count': quota_status["current_usage"],
                    'remaining': quota_status["remaining"],
                    'usage_percent': quota_status["percentage_used"],
                    'date': today
                }
        
        # Fallback to legacy system
        from config import get_user_daily_limit
        
        daily_limit = get_user_daily_limit(username)
        current_count = self.get_daily_download_count(username)
        today = datetime.now().date().isoformat()
        
        return {
            'username': username,
            'daily_limit': daily_limit,
            'current_count': current_count,
            'remaining': max(0, daily_limit - current_count),
            'usage_percent': (current_count / daily_limit * 100) if daily_limit > 0 else 0,
            'date': today
        }
    
    def check_daily_download_limit(self, username: str, requested_count: int) -> tuple[bool, str]:
        """
        Check if user can download the requested number of records today with quota system integration.
        
        Args:
            username: The username to check
            requested_count: Number of records they want to download
            
        Returns:
            tuple: (can_download: bool, message: str)
        """
        # First check quota system if available
        if QUOTA_SYSTEM_AVAILABLE:
            quota_status = quota_manager.get_user_quota_status(username)
            if quota_status.get("managed"):
                # User is under quota management
                remaining_quota = quota_status["remaining"]
                if requested_count > remaining_quota:
                    return False, "Insufficient quota available"
                return True, f"Quota OK - Remaining: {remaining_quota - requested_count}"
        
        # Fallback to legacy system
        from config import get_user_daily_limit
        
        daily_limit = get_user_daily_limit(username)
        if daily_limit <= 0:
            return True, "No daily limit configured"
        
        current_count = self.get_daily_download_count(username)
        remaining = daily_limit - current_count
        
        if current_count + requested_count > daily_limit:
            return False, f"Daily limit exceeded. Used: {current_count}/{daily_limit}, Remaining: {remaining}, Requested: {requested_count}"
        
        return True, f"OK - Remaining capacity: {remaining - requested_count}"
    
    def check_agent_data_expiry(self) -> bool:
        """
        Agent audit data is now persistent - no expiry needed.
        
        Returns:
            False (data never expires)
        """
        return False
    
    def clear_agent_audit_data(self, username: str = None):
        """Clear agent audit data for the specified user."""
        if not username:
            username = st.session_state.get('username', 'default_user')
        
        # Clear the user's individual audit file
        self.agent_audit_file = self.agent_audit_dir / f"agent_audits_{username}.json"
        
        # Clear the file by resetting to initial state
        initial_data = {
            'login_timestamp': datetime.now().isoformat(),
            'audit_results': []
        }
        safe_json_write(self.agent_audit_file, initial_data)
    
    def get_agent_data_time_remaining(self) -> str:
        """
        Agent audit data is now persistent - no expiry.
        
        Returns:
            String indicating persistent storage
        """
        return "Persistent (no expiry)"
    
    def save_campaign_audit_results(self, df: pd.DataFrame, campaign_name: str, username: str):
        """
        Save campaign audit results persistently.
        
        Args:
            df: DataFrame with audit results
            campaign_name: Name of the campaign
            username: User who ran the audit
        """
        if df.empty:
            return
        
        df_to_save = df.copy()

        if 'Dialer Name' in df_to_save.columns and 'dialer_name' in df_to_save.columns:
            df_to_save['Dialer Name'] = df_to_save['Dialer Name'].fillna(df_to_save['dialer_name'])
            df_to_save = df_to_save.drop('dialer_name', axis=1)
        elif 'dialer_name' in df_to_save.columns and 'Dialer Name' not in df_to_save.columns:
            df_to_save = df_to_save.rename(columns={'dialer_name': 'Dialer Name'})

        if 'Reason for Calling' in df_to_save.columns and 'Reason for calling' in df_to_save.columns:
            df_to_save['Reason for Calling'] = df_to_save['Reason for Calling'].fillna(df_to_save['Reason for calling'])
            df_to_save = df_to_save.drop('Reason for calling', axis=1)
        elif 'Reason for calling' in df_to_save.columns and 'Reason for Calling' not in df_to_save.columns:
            df_to_save = df_to_save.rename(columns={'Reason for calling': 'Reason for Calling'})

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{campaign_name}_{timestamp}.csv"
        filepath = self.campaign_audit_dir / filename
        
        # Save the data
        df_to_save.to_csv(filepath, index=False)
        
        # Save metadata
        metadata = {
            "campaign_name": campaign_name,
            "username": username,
            "timestamp": timestamp,
            "record_count": len(df_to_save),
            "releasing_count": len(df_to_save[df_to_save["Releasing Detection"] == "Yes"]),
            "late_hello_count": len(df_to_save[df_to_save["Late Hello Detection"] == "Yes"])
        }
        
        metadata_file = filepath.with_suffix('.json')
        safe_json_write(metadata_file, metadata)
    
    def get_available_campaigns(self, username: str = None) -> List[str]:
        """
        Get list of campaigns - users in sharing groups see combined campaigns.
        Supports shared dashboards - users see campaigns from all group members.

        SECURITY NOTE: Users in sharing groups can access campaigns from all group members.
        """
        if not username:
            username = st.session_state.get('username', 'default_user')

        # Get all users whose data this user can access
        shared_users = self.get_shared_users(username)

        campaign_files = list(self.campaign_audit_dir.glob("*.csv"))
        campaigns = set()
        
        for filepath in campaign_files:
            # Check metadata for username
            metadata_file = filepath.with_suffix('.json')
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                stored_username = metadata.get('username', 'unknown')
                # Users can see campaigns from anyone in their sharing group
                if stored_username in shared_users:
                    # Extract campaign name from filename: {campaign}_{timestamp}.csv
                    parts = filepath.stem.split('_')
                    if len(parts) >= 2:
                        # Campaign name is everything except the last two parts (date and time)
                        campaign_name = '_'.join(parts[:-2])
                        campaigns.add(campaign_name)
            except (FileNotFoundError, json.JSONDecodeError):
                continue  # Skip if no metadata or invalid
        
        return sorted(list(campaigns))
    
    def load_campaign_audit_data(self, campaign_name: str, start_date: date, end_date: date, username: str = None) -> pd.DataFrame:
        """
        Load campaign audit data - users in sharing groups see combined data.
        Supports shared dashboards - users can access campaigns from all group members.

        SECURITY NOTE: Users in sharing groups can access campaigns from all group members.
        """
        if not username:
            username = st.session_state.get('username', 'default_user')

        # Get all users whose data this user can access
        shared_users = self.get_shared_users(username)

        all_data = []
        campaign_files = self.campaign_audit_dir.glob(f"{campaign_name}_*.csv")

        for filepath in campaign_files:
            # Check metadata for username
            metadata_file = filepath.with_suffix('.json')
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                stored_username = metadata.get('username', 'unknown')
                # Users can access campaigns from anyone in their sharing group
                if stored_username in shared_users:
                    # Load the CSV data
                    df = pd.read_csv(filepath)

                    # Normalize dialer columns for campaign dashboards
                    if 'Dialer Name' in df.columns and 'dialer_name' in df.columns:
                        df['Dialer Name'] = df['Dialer Name'].fillna(df['dialer_name'])
                        df = df.drop('dialer_name', axis=1)
                    elif 'dialer_name' in df.columns and 'Dialer Name' not in df.columns:
                        df = df.rename(columns={'dialer_name': 'Dialer Name'})

                    # Filter by call timestamps in the data
                    if 'Timestamp' in df.columns and not df.empty:
                        # Parse ReadyMode timestamps and filter by date range
                        filtered_rows = []
                        unparseable_count = 0
                        
                        for idx, row in df.iterrows():
                            timestamp_str = str(row['Timestamp']).strip()
                            if not timestamp_str or timestamp_str == 'nan' or timestamp_str == '':
                                # Skip rows with missing timestamps
                                continue
                            
                            try:
                                # Handle quoted timestamps: "Oct 31, 7:22PM"
                                if timestamp_str.startswith('"') and timestamp_str.endswith('"'):
                                    timestamp_str = timestamp_str[1:-1]  # Remove quotes
                                
                                # Parse ReadyMode timestamp format: "Oct 31, 7:22PM"
                                current_year = datetime.now().year
                                
                                # Replace any underscores with colons (for compatibility)
                                clean_timestamp = timestamp_str.replace('_', ':')
                                
                                # Smart year determination: if the month is after current month, assume previous year
                                # For example, if it's November 2025 and we see "Oct 30", it should be Oct 30, 2024
                                current_month = datetime.now().month
                                
                                # Extract month from timestamp
                                try:
                                    # Parse just the month part to determine year
                                    month_str = clean_timestamp.split(',')[0].strip().split()[0]  # "Oct" from "Oct 30"
                                    timestamp_month = datetime.strptime(month_str, "%b").month
                                    
                                    # If timestamp month is greater than current month, it's from previous year
                                    # This handles year transitions (e.g., seeing Dec data in Jan)
                                    if timestamp_month > current_month:
                                        parsed_year = current_year - 1
                                    else:
                                        parsed_year = current_year
                                except (ValueError, AttributeError) as e:
                                    # Fallback to current year if month parsing fails
                                    logger.debug(f"Error parsing timestamp month: {e}")
                                    parsed_year = current_year
                                
                                # Extract date part before the comma
                                if ',' in clean_timestamp:
                                    date_part = clean_timestamp.split(',')[0].strip()  # "Oct 31"
                                    date_str = f"{date_part}, {parsed_year}"  # "Oct 31, 2024" or "Oct 31, 2025"
                                else:
                                    # Fallback if no comma
                                    date_str = f"{clean_timestamp}, {parsed_year}"
                                
                                # Parse the date
                                call_date = datetime.strptime(date_str, "%b %d, %Y").date()
                                
                                # Check if within date range
                                if start_date <= call_date <= end_date:
                                    filtered_rows.append(idx)
                                
                            except (ValueError, IndexError) as e:
                                # If parsing fails, include the row anyway (be more permissive)
                                # This ensures we don't lose valid data due to timestamp format issues
                                print(f"Warning: Could not parse timestamp '{timestamp_str}' for row {idx}: {e}")
                                print("Including this row in results to avoid data loss")
                                filtered_rows.append(idx)  # Include unparseable timestamps
                                unparseable_count += 1

                        # Log summary of filtering
                        total_rows = len(df)
                        filtered_count = len(filtered_rows)
                        print(f"Date filtering: {total_rows} total rows, {filtered_count} within date range, {unparseable_count} unparseable (included)")

                        # Keep only filtered rows
                        if filtered_rows:
                            df = df.loc[filtered_rows]
                        else:
                            # If no rows match the date filter, skip this file entirely
                            continue

                    # Add to results if not empty after filtering
                    if not df.empty:
                        all_data.append(df)

            except (FileNotFoundError, json.JSONDecodeError, pd.errors.EmptyDataError):
                continue  # Skip if no metadata, invalid JSON, or empty CSV

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Remove duplicates based on phone number, keeping the most recent entry
            if not combined_df.empty and 'Phone Number' in combined_df.columns:
                # Sort by timestamp if available, otherwise keep first occurrence
                if 'Timestamp' in combined_df.columns:
                    # Try to sort by parsed timestamp for most recent first
                    try:
                        # Add a temporary parsed timestamp column for sorting
                        def parse_timestamp(ts_str):
                            if pd.isna(ts_str) or ts_str == '':
                                return pd.Timestamp.min
                            try:
                                # Handle quoted timestamps and underscores
                                ts_str = str(ts_str).strip()
                                if ts_str.startswith('"') and ts_str.endswith('"'):
                                    ts_str = ts_str[1:-1]
                                clean_ts = ts_str.replace('_', ':')
                                
                                current_year = datetime.now().year
                                current_month = datetime.now().month
                                
                                # Extract month from timestamp for smart year determination
                                try:
                                    month_str = clean_ts.split(',')[0].strip().split()[0]  # "Oct" from "Oct 30"
                                    timestamp_month = datetime.strptime(month_str, "%b").month
                                    
                                    if timestamp_month > current_month:
                                        parsed_year = current_year - 1
                                    else:
                                        parsed_year = current_year
                                except (ValueError, AttributeError) as e:
                                    logger.debug(f"Error parsing timestamp month in parse_timestamp: {e}")
                                    parsed_year = current_year
                                
                                if ',' in clean_ts:
                                    date_part = clean_ts.split(',')[0].strip()
                                    date_str = f"{date_part}, {parsed_year}"
                                else:
                                    date_str = f"{clean_ts}, {parsed_year}"
                                
                                return pd.to_datetime(date_str, format="%b %d, %Y")
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Error parsing datetime in parse_timestamp: {e}")
                                return pd.Timestamp.min
                        
                        combined_df['_parsed_timestamp'] = combined_df['Timestamp'].apply(parse_timestamp)
                        combined_df = combined_df.sort_values('_parsed_timestamp', ascending=False)
                        combined_df = combined_df.drop('_parsed_timestamp', axis=1)
                    except Exception:
                        # Fallback: just drop duplicates without sorting
                        pass
                
                # Drop duplicates by phone number, keeping the first (most recent) occurrence
                combined_df = combined_df.drop_duplicates(subset=['Phone Number'], keep='first')
            
            return combined_df
        else:
            return pd.DataFrame()
    
    def get_audit_metrics(self, df: pd.DataFrame) -> dict:
        """
        Calculate audit metrics from DataFrame.
        
        Args:
            df: DataFrame with audit results
            
        Returns:
            Dictionary with calculated metrics
        """
        if df.empty:
            return {
                'total_calls': 0,
                'flagged_calls': 0,
                'releasing_calls': 0,
                'late_hello_calls': 0,
                'flag_rate': 0.0
            }
        
        # Count flagged samples per agent for warning system
        flagged_counts = {}
        if 'Agent Name' in df.columns and ('Releasing Detection' in df.columns or 'Late Hello Detection' in df.columns or 'Rebuttal Detection' in df.columns):
            for _, row in df.iterrows():
                agent_name = row.get('Agent Name', 'Unknown')
                # Count as flagged if releasing, late hello, or rebuttal not used
                releasing_flagged = row.get('Releasing Detection', 'No') == 'Yes'
                late_hello_flagged = row.get('Late Hello Detection', 'No') == 'Yes'
                rebuttal_not_used = row.get('Rebuttal Detection', 'No') == 'No'  # "No" means rebuttal not detected
                
                is_flagged = releasing_flagged or late_hello_flagged or rebuttal_not_used
                if is_flagged:
                    flagged_counts[agent_name] = flagged_counts.get(agent_name, 0) + 1
        
        # Get metrics using the new method
        # Calculate basic audit metrics directly
        total_calls = len(df)
        flagged_calls = 0
        releasing_calls = 0
        late_hello_calls = 0
        
        # Find the correct column names (they might vary slightly)
        releasing_col = None
        late_hello_col = None
        
        for col in df.columns:
            if 'releasing' in col.lower() and 'detection' in col.lower():
                releasing_col = col
            elif 'late hello' in col.lower() and 'detection' in col.lower():
                late_hello_col = col
        
        releasing_count = 0
        late_hello_count = 0
        
        if releasing_col:
            releasing_count = len(df[df[releasing_col] == "Yes"])
        
        if late_hello_col:
            late_hello_count = len(df[df[late_hello_col] == "Yes"])
        
        flagged_calls = len(df[
            (df[releasing_col] == "Yes" if releasing_col else False) |
            (df[late_hello_col] == "Yes" if late_hello_col else False)
        ]) if releasing_col or late_hello_col else 0
        
        flag_rate = (flagged_calls / total_calls * 100) if total_calls > 0 else 0
        
        metrics = {
            'total_calls': total_calls,
            'flagged_calls': flagged_calls,
            'releasing_calls': releasing_count,
            'late_hello_calls': late_hello_count,
            'flag_rate': flag_rate,
        }
        
        # Add rebuttal calls count manually (dashboard manager doesn't include it)
        metrics['rebuttal_calls'] = (df['Rebuttal Detection'] == 'No').sum() if 'Rebuttal Detection' in df.columns else 0
        
        return metrics
    
    def generate_performance_report(self, df: pd.DataFrame, username: str = None) -> dict:
        """Generate comprehensive performance report with AI-powered insights.

        Args:
            df: DataFrame with audit results
            username: Username for context

        Returns:
            Dictionary with complete performance analysis
        """
        if df.empty:
            return {
                'error': 'No audit data available for analysis',
                'agents_audited': 0,
                'total_calls': 0,
                'observations': [],
                'recommendations': []
            }

        # Base calculations
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0

        # Disposition analysis
        disposition_counts = {}
        if 'Disposition' in df.columns:
            disposition_counts = df['Disposition'].value_counts().to_dict()

        # Behavioral factors
        rebuttal_yes = len(df[df.get('Rebuttal Detection') == 'Yes']) if 'Rebuttal Detection' in df.columns else 0
        rebuttal_no = len(df[df.get('Rebuttal Detection') == 'No']) if 'Rebuttal Detection' in df.columns else 0

        releasing_yes = len(df[df.get('Releasing Detection') == 'Yes']) if 'Releasing Detection' in df.columns else 0
        releasing_no = len(df[df.get('Releasing Detection') == 'No']) if 'Releasing Detection' in df.columns else 0

        late_hello_yes = len(df[df.get('Late Hello Detection') == 'Yes']) if 'Late Hello Detection' in df.columns else 0
        late_hello_no = len(df[df.get('Late Hello Detection') == 'No']) if 'Late Hello Detection' in df.columns else 0

        # Disposition interpretation mapping (kept for future use)
        disposition_mapping = {
            'Unknown': {'meaning': 'Owner hung up too early', 'category': 'Short or early hang-up'},
            'Sold': {'meaning': 'Property already sold', 'category': 'No opportunity'},
            'DNC – Decision Maker': {'meaning': 'Owner asked to be removed (confirmed)', 'category': 'Hard DNC'},
            'DNC – Unknown': {'meaning': 'Unknown person asked to be removed', 'category': 'Soft DNC'},
            'Decision Maker – NYI': {'meaning': 'Owner reached but not interested', 'category': 'Lead reached, not convinced'},
            'Wrong Number': {'meaning': 'Reached non-owner', 'category': 'Lead quality issue'},
            'Dead Call': {'meaning': 'No response or call dropped', 'category': 'Could be agent release or bad line'},
            'Listed Property': {'meaning': 'Property already listed', 'category': 'Duplicate lead or outdated data'},
            'Voicemail': {'meaning': 'Call went to voicemail', 'category': 'Timing/list issue'}
        }

        # Calculate percentages
        disposition_percentages: Dict[str, float] = {}
        for disp, count in disposition_counts.items():
            disposition_percentages[disp] = (count / total_calls * 100) if total_calls > 0 else 0

        # Core analysis logic
        observations: List[str] = []
        recommendations: List[str] = []

        # Lead Quality Patterns
        voicemail_pct = disposition_percentages.get('Voicemail', 0)
        unknown_pct = disposition_percentages.get('Unknown', 0)
        wrong_number_pct = disposition_percentages.get('Wrong Number', 0)

        if voicemail_pct + unknown_pct + wrong_number_pct > 30:
            observations.append("Many calls are unproductive. Lead quality needs improvement.")
            recommendations.append("Focus on better lead sources and organize lists by quality.")

        sold_pct = disposition_percentages.get('Sold', 0)
        listed_pct = disposition_percentages.get('Listed Property', 0)
        if sold_pct + listed_pct > 20:
            observations.append("Many leads are already converted. Database requires updating.")
            recommendations.append("Maintain current lead database and implement scoring system.")

        # Additional lead quality patterns
        if voicemail_pct > 25:
            observations.append("High voicemail volume indicates prospects may be unavailable.")
            recommendations.append("Review lead sources and update contact information regularly.")

        if wrong_number_pct > 15:
            observations.append("Too many wrong numbers. Contact data requires cleaning.")
            recommendations.append("Review contact database and remove incorrect numbers.")

        if unknown_pct > 20:
            observations.append("Many calls reach wrong parties. Contact list needs correction.")
            recommendations.append("Remove disconnected numbers and verify contact details.")

        # Agent Performance Patterns
        nyi_pct = disposition_percentages.get('Decision Maker – NYI', 0)
        rebuttal_ratio = rebuttal_yes / max(rebuttal_yes + rebuttal_no, 1)

        if nyi_pct > 25 and rebuttal_ratio < 0.6:
            observations.append("High rejection rate with poor objection handling.")
            recommendations.append("Provide objection handling training and encourage persistence.")
        elif nyi_pct > 25 and rebuttal_ratio >= 0.6:
            observations.append("Agents show persistence but may need better qualification.")
            recommendations.append("Improve qualification scripts and develop follow-up procedures.")

        # Additional agent performance insights
        if rebuttal_ratio < 0.3:
            observations.append("Limited objection handling. Additional training required.")
            recommendations.append("Conduct comprehensive objection training with practice sessions.")

        if nyi_pct < 10 and rebuttal_ratio > 0.8:
            observations.append("Strong agent performance with effective lead generation.")

        # Process-specific patterns
        if wrong_number_pct > 10 and rebuttal_ratio >= 0.5:
            observations.append("Agents maintain process standards despite wrong numbers.")

        releasing_rate = 0.0
        if releasing_yes > 0:
            releasing_rate = releasing_yes / max(releasing_yes + releasing_no, 1)
            if releasing_rate > 0.05:
                observations.append("Early call termination detected. Quality review needed.")
                recommendations.append("Monitor calls for premature disconnection patterns.")

        # Additional call quality patterns
        if releasing_rate > 0.1:
            observations.append("Frequent call abandonment. Script or training issues possible.")
            recommendations.append("Review call scripts and enhance agent training program.")

        late_hello_rate = 0.0
        if late_hello_yes > 0:
            late_hello_rate = late_hello_yes / max(late_hello_yes + late_hello_no, 1)
            if late_hello_rate > 0.1:
                observations.append("Delayed call initiation. Faster greeting required.")
                recommendations.append("Train agents on prompt call opening procedures.")

        # Additional timing insights
        if late_hello_rate > 0.2:
            observations.append("Significant greeting delays impacting first impressions.")
            recommendations.append("Practice quick call starts and provide timing feedback.")

        # DNC analysis
        dnc_rate = 0.0
        dnc_hard = disposition_counts.get('DNC – Decision Maker', 0)
        dnc_soft = disposition_counts.get('DNC – Unknown', 0)
        if dnc_hard + dnc_soft > 0:
            dnc_rate = (dnc_hard + dnc_soft) / max(total_calls, 1)
            if dnc_rate > 0.1:
                observations.append("Elevated do-not-call requests. Compliance review required.")
                recommendations.append("Review calling procedures and ensure compliance training.")

        # Additional compliance insights
        if dnc_rate > 0.15:
            observations.append("High do-not-call volume. Approach or list quality concerns.")
            recommendations.append("Adjust calling strategy and implement DNC safeguards.")

        # Success pattern analysis
        if total_calls > 50 and nyi_pct < 15 and wrong_number_pct < 10:
            observations.append("Successful campaign with low rejection and high accuracy.")
            recommendations.append("Scale effective calling methods and expand training.")

        # Generate AI-powered observations using patterns
        ai_observations = self._generate_ai_insights(
            df,
            disposition_counts,
            {
                'rebuttal_ratio': 1 - (rebuttal_no / max(rebuttal_yes + rebuttal_no, 1)),  # attempt ratio
                'late_hello_rate': late_hello_rate,
                'releasing_rate': releasing_yes / max(total_calls, 1),
                'nyi_rate': nyi_pct / 100.0,
            },
        )

        observations.extend(ai_observations)
        observations = observations[:3]

        # Shared behavioral metrics structure
        behavioral_metrics = {
            'rebuttal_usage': f"{rebuttal_yes}/{rebuttal_yes + rebuttal_no}",
            'rebuttal_not_attempted_ratio': rebuttal_no / max(rebuttal_yes + rebuttal_no, 1),
            'releasing_detected': releasing_yes,
            'late_hello_detected': late_hello_yes,
        }

        # Automatic issue flags and ratings for campaign performance table
        total_calls_safe = max(total_calls, 1)
        skipped_ratio = behavioral_metrics['rebuttal_not_attempted_ratio']
        releasing_rate_total = releasing_yes / total_calls_safe
        late_hello_rate_total = late_hello_yes / total_calls_safe

        def _rating_from_ratio(ratio: float) -> str:
            if ratio < 0.3:
                return "Low"
            if ratio < 0.5:
                return "Medium"
            return "High"

        effort_ratio = max(skipped_ratio, late_hello_rate_total, releasing_rate_total)
        effort_feedback = "Yes" if effort_ratio >= 0.3 else "No"
        effort_rating = _rating_from_ratio(effort_ratio) if effort_feedback == "Yes" else "N/A"

        rebuttal_feedback = "Yes" if skipped_ratio >= 0.3 else "No"
        rebuttal_rating = _rating_from_ratio(skipped_ratio) if rebuttal_feedback == "Yes" else "N/A"

        releasing_feedback = "Yes" if releasing_rate_total >= 0.05 else "No"
        releasing_rating = _rating_from_ratio(releasing_rate_total) if releasing_feedback == "Yes" else "N/A"

        tonality_feedback = "N/A"
        tonality_rating = "N/A"

        list_problem_pct = 0.0
        for key in ['Wrong Number', 'Unknown', 'Voicemail', 'DNC – Decision Maker', 'DNC – Unknown']:
            list_problem_pct += disposition_percentages.get(key, 0.0)
        list_problem_ratio = list_problem_pct / 100.0
        campaign_list_feedback = "Yes" if list_problem_ratio >= 0.3 else "No"
        campaign_list_rating = _rating_from_ratio(list_problem_ratio) if campaign_list_feedback == "Yes" else "N/A"

        needs_coaching_feedback = "Yes" if any(
            flag == "Yes" for flag in [effort_feedback, rebuttal_feedback, releasing_feedback, campaign_list_feedback]
        ) else "No"
        if needs_coaching_feedback == "Yes":
            if any(r == "High" for r in [effort_rating, rebuttal_rating, releasing_rating, campaign_list_rating]):
                needs_coaching_rating = "High"
            elif any(r == "Medium" for r in [effort_rating, rebuttal_rating, releasing_rating, campaign_list_rating]):
                needs_coaching_rating = "Medium"
            else:
                needs_coaching_rating = "Low"
        else:
            needs_coaching_rating = "N/A"

        # Agents allocation issue - automatic based on uneven call volume across agents
        allocation_feedback = "N/A"
        allocation_rating = "N/A"
        if 'Agent Name' in df.columns and unique_agents > 1:
            try:
                agent_counts = df['Agent Name'].value_counts()
                max_share = agent_counts.max() / total_calls_safe

                # If one agent handles more than 40% of all calls, flag as allocation issue
                if max_share > 0.40:
                    allocation_feedback = "Yes"
                    if max_share > 0.65:
                        allocation_rating = "High"
                    elif max_share > 0.50:
                        allocation_rating = "Medium"
                    else:
                        allocation_rating = "Low"
                else:
                    allocation_feedback = "No"
                    allocation_rating = "N/A"
            except Exception as e:
                logger.warning(f"Failed to compute allocation issue metrics: {e}")
                allocation_feedback = "N/A"
                allocation_rating = "N/A"

        def _note(feedback: str, rating: str, kind: str) -> str:
            if feedback != "Yes":
                return "N/A"
            if kind == "effort":
                return (
                    "Coach agents to keep steady energy and focus during calls. "
                    "Review a small sample of long or low-energy calls each week."
                )
            if kind == "rebuttal":
                return (
                    "Train agents to always try at least one clear rebuttal before ending the call. "
                    "Provide simple scripts for the most common objections."
                )
            if kind == "releasing":
                return (
                    "Review calls that end early to understand why. Check scripts, tools, and lead quality, "
                    "and add a closing checklist if needed."
                )
            if kind == "tonality":
                return "N/A"
            if kind == "coaching":
                return (
                    "Schedule focused coaching sessions for agents whose calls show repeated issues in rebuttals, "
                    "releasing, or list quality."
                )
            if kind == "allocation":
                return (
                    "Review how calls are distributed between agents. Move some calls from very busy agents "
                    "to others so workload and opportunities are more balanced."
                )
            if kind == "campaign_list":
                return (
                    "Clean the campaign list by removing wrong or unknown numbers and updating stale records. "
                    "Consider improving the data source for future lists."
                )
            return "N/A"

        issue_table = {
            'effort_issue': {
                'label': 'Effort Issue from Agents',
                'feedback': effort_feedback,
                'rating': effort_rating,
                'notes': _note(effort_feedback, effort_rating, 'effort'),
            },
            'rebuttal_issue': {
                'label': 'Rebuttals issue',
                'feedback': rebuttal_feedback,
                'rating': rebuttal_rating,
                'notes': _note(rebuttal_feedback, rebuttal_rating, 'rebuttal'),
            },
            'releasing_issue': {
                'label': 'Releasing issue',
                'feedback': releasing_feedback,
                'rating': releasing_rating,
                'notes': _note(releasing_feedback, releasing_rating, 'releasing'),
            },
            'tonality_issue': {
                'label': 'Active Tonality issue',
                'feedback': tonality_feedback,
                'rating': tonality_rating,
                'notes': _note(tonality_feedback, tonality_rating, 'tonality'),
            },
            'agents_coaching': {
                'label': 'Agents needs Coaching',
                'feedback': needs_coaching_feedback,
                'rating': needs_coaching_rating,
                'notes': _note(needs_coaching_feedback, needs_coaching_rating, 'coaching'),
            },
            'agents_allocation': {
                'label': 'Agents allocation issue',
                'feedback': allocation_feedback,
                'rating': allocation_rating,
                'notes': _note(allocation_feedback, allocation_rating, 'allocation'),
            },
            'campaign_list': {
                'label': 'Campaign List Issue',
                'feedback': campaign_list_feedback,
                'rating': campaign_list_rating,
                'notes': _note(campaign_list_feedback, campaign_list_rating, 'campaign_list'),
            },
        }

        # Build compact campaign metrics payload for the AI helpers
        campaign_name = None
        date_range_label = None
        try:
            session_state = getattr(st, "session_state", None)
            if session_state is not None:
                campaign_name = session_state.get("campaign_select")
                start_date_val = session_state.get("campaign_start_date")
                end_date_val = session_state.get("campaign_end_date")
                if start_date_val and end_date_val:
                    date_range_label = f"{start_date_val} - {end_date_val}"
        except Exception:
            campaign_name = None
            date_range_label = None

        campaign_metrics = {
            "total_calls": total_calls,
            "agents_audited": unique_agents,
            "behavioral_metrics": behavioral_metrics,
            "disposition_breakdown": disposition_counts,
            "disposition_percentages": disposition_percentages,
            "observations": observations,
            "recommendations": recommendations,
            "campaign_name": campaign_name,
            "date_range": date_range_label,
        }

        try:
            ai_summary = generate_ai_campaign_summary(campaign_metrics)
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
            ai_summary = None

        # Let AI refine per-issue notes where feedback is Yes; keep fallbacks otherwise
        try:
            ai_issue_notes = generate_ai_issue_notes(campaign_metrics, issue_table)
            if isinstance(ai_issue_notes, dict) and ai_issue_notes:
                for key, note in ai_issue_notes.items():
                    if key in issue_table and str(issue_table[key].get('feedback', '')).strip() == "Yes":
                        if note and isinstance(note, str):
                            issue_table[key]['notes'] = note.strip()
        except Exception as e:
            logger.warning(f"AI issue notes generation failed: {e}")

        return {
            'agents_audited': unique_agents,
            'total_calls': total_calls,
            'disposition_breakdown': disposition_counts,
            'disposition_percentages': disposition_percentages,
            'behavioral_metrics': behavioral_metrics,
            'observations': observations,
            'recommendations': recommendations,
            'issue_table': issue_table,
            'ai_summary': ai_summary,
        }

    def _generate_ai_insights(self, df: pd.DataFrame, disposition_counts: dict, behavioral_ratios: dict) -> list:
        """Generate AI-powered observations based on data patterns.

        Args:
            df: Audit data
            disposition_counts: Disposition frequency counts
            behavioral_ratios: Key behavioral metrics

        Returns:
            List of AI-generated observations
        """
        observations: List[str] = []

        # Pattern-based AI insights
        rebuttal_ratio = behavioral_ratios['rebuttal_ratio']
        late_hello_rate = behavioral_ratios['late_hello_rate']
        releasing_rate = behavioral_ratios['releasing_rate']
        nyi_rate = behavioral_ratios['nyi_rate']

        # Engagement analysis - expanded
        if rebuttal_ratio > 0.8:
            observations.append("Excellent objection handling across all agents.")
        elif rebuttal_ratio > 0.7:
            observations.append("Good objection handling performance.")
        elif rebuttal_ratio < 0.4:
            observations.append("Objection handling needs improvement.")
        elif rebuttal_ratio < 0.2:
            observations.append("Urgent objection training required.")

        # Quality analysis - expanded
        if late_hello_rate > 0.15:
            observations.append("Call initiation timing requires attention.")
        elif late_hello_rate > 0.25:
            observations.append("Severe delays in call initiation.")

        if releasing_rate > 0.08:
            observations.append("Call termination patterns require review.")
        elif releasing_rate > 0.12:
            observations.append("Excessive call abandonment requires immediate action.")

        # Disposition analysis - expanded
        total_calls = sum(disposition_counts.values())
        voicemail_rate = disposition_counts.get('Voicemail', 0) / max(total_calls, 1)
        unknown_rate = disposition_counts.get('Unknown', 0) / max(total_calls, 1)

        if voicemail_rate + unknown_rate > 0.4:
            observations.append("High volume of unanswered calls.")
        elif voicemail_rate + unknown_rate > 0.6:
            observations.append("Excessive unanswered call volume.")

        # Additional disposition insights
        sold_rate = disposition_counts.get('Sold', 0) / max(total_calls, 1)
        if sold_rate > 0.25:
            observations.append("High conversion rate indicates strong targeting effectiveness.")

        dnc_rate = (
            disposition_counts.get('DNC – Decision Maker', 0)
            + disposition_counts.get('DNC – Unknown', 0)
        ) / max(total_calls, 1)
        if dnc_rate > 0.08:
            observations.append("Elevated do-not-call request volume.")

        # Success pattern analysis - expanded
        nyi_count = disposition_counts.get('Decision Maker – NYI', 0)
        if nyi_count > total_calls * 0.3 and rebuttal_ratio > 0.6:
            observations.append("Strong agent persistence in challenging conditions.")
        elif nyi_count < total_calls * 0.15 and rebuttal_ratio > 0.7:
            observations.append("Excellent campaign performance with strong engagement.")

        # Performance trend analysis
        if late_hello_rate < 0.05 and releasing_rate < 0.03 and rebuttal_ratio > 0.75:
            observations.append("Outstanding overall call quality and performance.")

        if (
            voicemail_rate < 0.15
            and unknown_rate < 0.1
            and (disposition_counts.get('Wrong Number', 0) / max(total_calls, 1)) < 0.08
        ):
            observations.append("Superior lead data quality supporting success.")

        return observations

    def clear_campaign_audit_data(self, username: str = None, campaign_name: str = None):
        """Clear campaign audit data for a user.

        If campaign_name is provided, only that campaign's data is cleared.
        Otherwise, all campaign audit data for the user is removed.

        Args:
            username: Username whose campaign data to clear
            campaign_name: Optional campaign name to scope deletion
        """
        if not username:
            username = st.session_state.get('username', 'default_user')

        # Clear campaign audit files for this user (optionally filtered by campaign)
        campaign_files = list(self.campaign_audit_dir.glob("*.csv"))

        for filepath in campaign_files:
            metadata_file = filepath.with_suffix('.json')
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                stored_username = metadata.get('username', 'unknown')
                stored_campaign = metadata.get('campaign_name')

                # Match username and optional campaign name
                if stored_username == username and (campaign_name is None or stored_campaign == campaign_name):
                    filepath.unlink(missing_ok=True)
                    metadata_file.unlink(missing_ok=True)
            except (FileNotFoundError, json.JSONDecodeError):
                # If no metadata or invalid and no specific campaign requested, remove the files anyway
                if campaign_name is None:
                    filepath.unlink(missing_ok=True)


# Global instance
dashboard_manager = DashboardManager()

# Global session manager instance
session_manager = SessionManager()

# Global user manager instance
user_manager = UserManager()
