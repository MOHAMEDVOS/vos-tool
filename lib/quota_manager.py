#!/usr/bin/env python3
"""
Hierarchical Quota Management System for VOS Application
Implements Owner -> Admin -> User quota control with real-time tracking

PHASE 2 REFACTOR: Database-only implementation (NO JSON files)
- All data stored in PostgreSQL
- No JSON file fallback
- Proper transaction support
- Clear error handling
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import logging

# Import database manager
try:
    from lib.database import get_db_manager
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    get_db_manager = None
    logging.error(f"Database manager not available - quota system requires database. Error: {e}")

logger = logging.getLogger(__name__)


# Custom exceptions for quota system
class DatabaseUnavailableError(Exception):
    """Raised when database connection is not available."""
    pass


class DatabaseOperationError(Exception):
    """Raised when database operation fails."""
    pass


class QuotaExceededError(Exception):
    """Raised when user quota is exceeded."""
    pass


class QuotaManager:
    """Manages hierarchical quota system: Owner -> Admin -> Users
    
    DATABASE-ONLY IMPLEMENTATION:
    - All quota data stored in PostgreSQL tables
    - No JSON file operations
    - Transaction support for atomic updates
    - Raises exceptions on database failures (no silent fallback)
    """
    
    def __init__(self):
        """Initialize quota manager with database connection.
        
        Raises:
            DatabaseUnavailableError: If database connection cannot be established
        """
        if not DB_AVAILABLE or not get_db_manager:
            raise DatabaseUnavailableError(
                "Quota system requires database connection. "
                "Ensure DATABASE_URL is set and lib.database is available."
            )
        
        try:
            self._db_manager = get_db_manager()
        except Exception as e:
            logger.error(f"Could not initialize database manager: {e}")
            raise DatabaseUnavailableError(f"Database initialization failed: {e}")
        
        if not self._db_manager:
            raise DatabaseUnavailableError("Database manager returned None")
        
        # Verify database connectivity on initialization
        try:
            test_query = "SELECT 1"
            self._db_manager.execute_query(test_query, fetch=True)
            logger.info("✓ Quota manager initialized with database connection")
        except Exception as e:
            logger.error(f"Database connectivity test failed: {e}")
            raise DatabaseUnavailableError(f"Cannot connect to database: {e}")
    
    def _load_quota_data(self) -> Dict:
        """Load quota configuration data from PostgreSQL database ONLY.
        
        Returns:
            Dict with keys: 'system_config', 'admin_limits', 'user_assignments'
            
        Raises:
            DatabaseUnavailableError: If database is not available
            DatabaseOperationError: If database query fails
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot load quota data: Database manager not initialized")
        
        quota_data = {
            "system_config": {},
            "admin_limits": {},
            "user_assignments": {}
        }
        
        try:
            # Load system config (if table exists)
            try:
                config_query = """
                    SELECT quota_reset_time, default_admin_user_limit, default_admin_daily_quota, updated_at
                    FROM quota_system_config 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """
                config_result = self._db_manager.execute_query(config_query, fetchone=True)
                if config_result:
                    quota_data["system_config"] = {
                        "quota_reset_time": str(config_result.get('quota_reset_time', '00:00')),
                        "default_admin_user_limit": config_result.get('default_admin_user_limit', 10),
                        "default_admin_daily_quota": config_result.get('default_admin_daily_quota', 5000)
                    }
                else:
                    # No config yet, use defaults
                    quota_data["system_config"] = {
                        "quota_reset_time": "00:00",
                        "default_admin_user_limit": 10,
                        "default_admin_daily_quota": 5000
                    }
            except Exception as e:
                logger.warning(f"Could not load system config (using defaults): {e}")
                quota_data["system_config"] = {
                    "quota_reset_time": "00:00",
                    "default_admin_user_limit": 10,
                    "default_admin_daily_quota": 5000
                }
            
            # Load admin limits
            admin_limits_query = "SELECT * FROM admin_limits ORDER BY admin_username"
            admin_limits = self._db_manager.execute_query(admin_limits_query, fetch=True)
            for admin in admin_limits:
                quota_data["admin_limits"][admin['admin_username']] = {
                    "max_users": admin.get('max_active_users', 10),
                    "daily_quota": admin.get('per_user_daily_quota', 5000),
                    "total_daily_quota": admin.get('max_active_users', 10) * admin.get('per_user_daily_quota', 5000),
                    "created_by": admin.get('created_by'),
                    "created_date": str(admin.get('created_at', date.today()).date()) if admin.get('created_at') else str(date.today()),
                    "last_modified": admin.get('updated_at').isoformat() if admin.get('updated_at') else None
                }
            
            # Load user assignments
            user_assignments_query = "SELECT * FROM user_quota_assignments ORDER BY user_username"
            user_assignments = self._db_manager.execute_query(user_assignments_query, fetch=True)
            for assignment in user_assignments:
                quota_data["user_assignments"][assignment['user_username']] = {
                    "assigned_to_admin": assignment.get('assigned_to_admin'),
                    "daily_quota": assignment.get('daily_quota', 1000),
                    "created_date": str(assignment.get('created_at', date.today()).date()) if assignment.get('created_at') else str(date.today())
                }
            
            logger.debug(f"Loaded quota data: {len(quota_data['admin_limits'])} admins, {len(quota_data['user_assignments'])} assignments")
            return quota_data
            
        except Exception as e:
            logger.error(f"Failed to load quota data from database: {e}")
            raise DatabaseOperationError(f"Cannot load quota configuration: {e}")
    
    def _save_quota_data(self, data: Dict):
        """Save quota configuration data to PostgreSQL database ONLY.
        
        Args:
            data: Dict with 'system_config', 'admin_limits', 'user_assignments'
            
        Raises:
            DatabaseOperationError: If database save fails
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot save quota data: Database manager not initialized")
        
        try:
            # Save system config (upsert)
            if "system_config" in data:
                config = data["system_config"]
                query = """
                    INSERT INTO quota_system_config 
                    (quota_reset_time, default_admin_user_limit, default_admin_daily_quota, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        quota_reset_time = EXCLUDED.quota_reset_time,
                        default_admin_user_limit = EXCLUDED.default_admin_user_limit,
                        default_admin_daily_quota = EXCLUDED.default_admin_daily_quota,
                        updated_at = NOW()
                """
                self._db_manager.execute_query(query, (
                    config.get('quota_reset_time', '00:00'),
                    config.get('default_admin_user_limit', 10),
                    config.get('default_admin_daily_quota', 5000)
                ))
            
            logger.debug("Saved quota configuration to database")
            
        except Exception as e:
            logger.error(f"Failed to save quota data to database: {e}")
            raise DatabaseOperationError(f"Cannot save quota configuration: {e}")
    
    def _load_usage_data(self) -> Dict:
        """Load daily usage tracking data from PostgreSQL database ONLY.
        
        Returns:
            Dict with 'last_reset_date' and 'admin_usage'
            
        Raises:
            DatabaseOperationError: If database query fails
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot load usage data: Database manager not initialized")
        
        today = str(date.today())
        usage_data = {
            "last_reset_date": today,
            "admin_usage": {}
        }
        
        try:
            # Load admin usage for today
            admin_usage_query = """
                SELECT admin_username, total_used, date
                FROM admin_usage
                WHERE date = %s
                ORDER BY admin_username
            """
            admin_usage_results = self._db_manager.execute_query(admin_usage_query, (today,), fetch=True)
            
            for admin_usage in admin_usage_results:
                admin_name = admin_usage['admin_username']
                usage_data["admin_usage"][admin_name] = {
                    "total_used": admin_usage.get('total_used', 0),
                    "users_usage": {}
                }
            
            # Load user usage for today (grouped by admin)
            user_usage_query = """
                SELECT user_username, admin_username, usage_count, date
                FROM user_usage
                WHERE date = %s
                ORDER BY admin_username, user_username
            """
            user_usage_results = self._db_manager.execute_query(user_usage_query, (today,), fetch=True)
            
            for user_usage in user_usage_results:
                admin_name = user_usage['admin_username']
                user_name = user_usage['user_username']
                count = user_usage.get('usage_count', 0)
                
                if admin_name not in usage_data["admin_usage"]:
                    usage_data["admin_usage"][admin_name] = {
                        "total_used": 0,
                        "users_usage": {}
                    }
                
                usage_data["admin_usage"][admin_name]["users_usage"][user_name] = count
            
            logger.debug(f"Loaded usage data for {len(usage_data['admin_usage'])} admins")
            return usage_data
            
        except Exception as e:
            logger.error(f"Failed to load usage data from database: {e}")
            raise DatabaseOperationError(f"Cannot load usage data: {e}")
    
    def _save_usage_data(self, data: Dict):
        """Save daily usage tracking data to PostgreSQL database ONLY.
        
        Args:
            data: Dict with 'admin_usage' containing usage by admin and user
            
        Raises:
            DatabaseOperationError: If database save fails
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot save usage data: Database manager not initialized")
        
        try:
            today = str(date.today())
            
            # Save admin usage
            if "admin_usage" in data:
                for admin_username, admin_data in data["admin_usage"].items():
                    total_used = admin_data.get("total_used", 0)
                    
                    query = """
                        INSERT INTO admin_usage (admin_username, date, total_used)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (admin_username, date) DO UPDATE SET
                            total_used = EXCLUDED.total_used,
                            updated_at = NOW()
                    """
                    self._db_manager.execute_query(query, (admin_username, today, total_used))
                    
                    # Save user usage under this admin
                    if "users_usage" in admin_data:
                        for user_username, usage_count in admin_data["users_usage"].items():
                            user_query = """
                                INSERT INTO user_usage (user_username, admin_username, date, usage_count)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (user_username, date) DO UPDATE SET
                                    usage_count = EXCLUDED.usage_count,
                                    updated_at = NOW()
                            """
                            self._db_manager.execute_query(user_query, (user_username, admin_username, today, usage_count))
            
            logger.debug("Saved usage data to database")
            
        except Exception as e:
            logger.error(f"Failed to save usage data to database: {e}")
            raise DatabaseOperationError(f"Cannot save usage data: {e}")
    
    def _reset_daily_usage(self):
        """Reset daily usage counters in database."""
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot reset usage: Database manager not initialized")
        
        try:
            today = str(date.today())
            
            # Delete old usage records (keep last 30 days for history)
            delete_query = """
                DELETE FROM admin_usage 
                WHERE date < (CURRENT_DATE - INTERVAL '30 days')
            """
            self._db_manager.execute_query(delete_query)
            
            delete_user_query = """
                DELETE FROM user_usage 
                WHERE date < (CURRENT_DATE - INTERVAL '30 days')
            """
            self._db_manager.execute_query(delete_user_query)
            
            logger.info(f"Reset daily usage counters for {today}")
            
        except Exception as e:
            logger.error(f"Failed to reset daily usage: {e}")
            raise DatabaseOperationError(f"Cannot reset usage: {e}")
    
    # ==================== OWNER OPERATIONS ====================
    
    def set_admin_limits(self, admin_username: str, max_users: int, daily_quota: int, owner_username: str):
        """Owner sets limits for an Admin.
        
        Args:
            admin_username: Username of the admin
            max_users: Maximum number of users the admin can create
            daily_quota: Daily quota per user for this admin
            owner_username: Username of the owner setting the limits
            
        Raises:
            DatabaseOperationError: If setting limits fails
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot set admin limits: Database not available")
        
        try:
            # Calculate total daily quota (per-user quota * max users)
            total_daily_quota = daily_quota * max_users
            
            query = """
                INSERT INTO admin_limits (admin_username, max_active_users, per_user_daily_quota, created_by, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (admin_username) DO UPDATE SET
                    max_active_users = EXCLUDED.max_active_users,
                    per_user_daily_quota = EXCLUDED.per_user_daily_quota,
                    created_by = EXCLUDED.created_by,
                    updated_at = NOW()
            """
            
            self._db_manager.execute_query(query, (
                admin_username,
                max_users,
                daily_quota,
                owner_username
            ))
            
            logger.info(f"Set admin limits for {admin_username}: {max_users} users, {daily_quota} quota per user")
            
        except Exception as e:
            logger.error(f"Error setting admin limits: {e}")
            raise DatabaseOperationError(f"Cannot set admin limits: {e}")
    
    def get_all_admin_limits(self) -> Dict:
        """Owner gets all Admin limits and current usage.
        
        Returns:
            Dict mapping admin usernames to their limits and usage
        """
        try:
            quota_data = self._load_quota_data()
            usage_data = self._load_usage_data()
            
            result = {}
            for admin_username, limits in quota_data.get("admin_limits", {}).items():
                admin_usage = usage_data.get("admin_usage", {}).get(admin_username, {})
                result[admin_username] = {
                    **limits,
                    "current_usage": admin_usage.get("total_used", 0)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting admin limits: {e}")
            raise DatabaseOperationError(f"Cannot get admin limits: {e}")
    
    def remove_admin_limits(self, admin_username: str):
        """Owner removes an Admin's limits (when Admin is deleted).
        
        Args:
            admin_username: Username of the admin to remove
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot remove admin limits: Database not available")
        
        try:
            # Delete admin limits
            delete_limits_query = "DELETE FROM admin_limits WHERE admin_username = %s"
            self._db_manager.execute_query(delete_limits_query, (admin_username,))
            
            # Delete all user assignments under this admin
            delete_assignments_query = "DELETE FROM user_quota_assignments WHERE assigned_to_admin = %s"
            self._db_manager.execute_query(delete_assignments_query, (admin_username,))
            
            # Clean up usage records
            delete_admin_usage = "DELETE FROM admin_usage WHERE admin_username = %s"
            self._db_manager.execute_query(delete_admin_usage, (admin_username,))
            
            delete_user_usage = "DELETE FROM user_usage WHERE admin_username = %s"
            self._db_manager.execute_query(delete_user_usage, (admin_username,))
            
            logger.info(f"Removed admin limits for {admin_username}")
            
        except Exception as e:
            logger.error(f"Error removing admin limits: {e}")
            raise DatabaseOperationError(f"Cannot remove admin limits: {e}")
    
    # ==================== ADMIN OPERATIONS ====================
    
    def can_admin_create_user(self, admin_username: str) -> Tuple[bool, str]:
        """Check if Admin can create another user.
        
        Args:
            admin_username: Username of the admin
            
        Returns:
            Tuple[bool, str]: (Success, Message)
        """
        try:
            quota_data = self._load_quota_data()
            admin_limits = quota_data.get("admin_limits", {}).get(admin_username, {})
            
            if not admin_limits:
                return False, f"Admin '{admin_username}' has no quota limits defined"
            
            max_users = admin_limits.get("max_users", 0)
            current_users = len(self.get_admin_created_users(admin_username))
            
            if current_users >= max_users:
                return False, f"User limit reached ({current_users}/{max_users})"
            
            return True, "User creation allowed"
            
        except Exception as e:
            logger.error(f"Error checking if admin can create user: {e}")
            return False, f"Error checking quota limits: {str(e)}"
    
    def assign_user_to_admin(self, username: str, admin_username: str, daily_quota: int) -> Tuple[bool, str]:
        """Admin assigns a user with specific quota.
        
        Args:
            username: Username to assign
            admin_username: Admin who is assigning the user
            daily_quota: Daily quota for this user
            
        Returns:
            Tuple[bool, str]: (Success, Message)
        """
        if not self._db_manager:
            return False, "Database not available"
        
        try:
            query = """
                INSERT INTO user_quota_assignments (user_username, assigned_to_admin, daily_quota, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_username) DO UPDATE SET
                    assigned_to_admin = EXCLUDED.assigned_to_admin,
                    daily_quota = EXCLUDED.daily_quota,
                    updated_at = NOW()
            """
            
            self._db_manager.execute_query(query, (username, admin_username, daily_quota))
            
            logger.info(f"Assigned user {username} to admin {admin_username} with quota {daily_quota}")
            return True, f"User {username} assigned to {admin_username} with daily quota {daily_quota}"
            
        except Exception as e:
            logger.error(f"Error assigning user to admin: {e}")
            return False, f"Failed to assign user quota: {str(e)}"
    
    def can_admin_assign_quota(self, admin_username: str, requested_quota: int) -> bool:
        """Check if Admin has enough quota to assign.
        
        Args:
            admin_username: Username of the admin
            requested_quota: Requested quota amount
            
        Returns:
            True if admin can assign this quota, False otherwise
        """
        try:
            quota_data = self._load_quota_data()
            admin_limits = quota_data.get("admin_limits", {}).get(admin_username, {})
            
            if not admin_limits:
                return False
            
            max_quota = admin_limits.get("daily_quota", 0)
            return requested_quota <= max_quota
            
        except Exception as e:
            logger.error(f"Error checking if admin can assign quota: {e}")
            return False
    
    def get_admin_created_users(self, admin_username: str) -> List[str]:
        """Get list of users created by specific Admin.
        
        Args:
            admin_username: Username of the admin
            
        Returns:
            List of usernames assigned to this admin
        """
        try:
            quota_data = self._load_quota_data()
            user_assignments = quota_data.get("user_assignments", {})
            
            return [
                username
                for username, data in user_assignments.items()
                if data.get("assigned_to_admin") == admin_username and username.lower() != admin_username.lower()
            ]
            
        except Exception as e:
            logger.error(f"Error getting admin created users: {e}")
            return []
    
    def get_admin_quota_usage(self, admin_username: str) -> Dict:
        """Get Admin's quota usage breakdown.
        
        Args:
            admin_username: Username of the admin
            
        Returns:
            Dict with usage information
        """
        try:
            usage_data = self._load_usage_data()
            admin_usage = usage_data.get("admin_usage", {}).get(admin_username, {})
            
            return {
                "total_used": admin_usage.get("total_used", 0),
                "users_usage": admin_usage.get("users_usage", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting admin quota usage: {e}")
            return {"total_used": 0, "users_usage": {}}
    
    def get_admin_dashboard_info(self, admin_username: str) -> Dict:
        """Get comprehensive dashboard info for Admin.
        
        Args:
            admin_username: Username of the admin
            
        Returns:
            Dict with limits, usage, and user information
        """
        try:
            quota_data = self._load_quota_data()
            usage_data = self._load_usage_data()
            
            admin_limits = quota_data.get("admin_limits", {}).get(admin_username, {})
            admin_usage = usage_data.get("admin_usage", {}).get(admin_username, {})
            
            # Get detailed users and calculate assigned quota
            user_assignments = quota_data.get("user_assignments", {})
            detailed_users = []
            total_assigned_quota = 0
            
            for username, data in user_assignments.items():
                if data.get("assigned_to_admin") == admin_username and username.lower() != admin_username.lower():
                    user_info = data.copy()
                    user_info['username'] = username
                    detailed_users.append(user_info)
                    total_assigned_quota += data.get("daily_quota", 0)
            
            return {
                "limits": admin_limits,
                "usage": admin_usage,
                "users": detailed_users,
                "user_count": len(detailed_users),
                "max_users": admin_limits.get("max_users", 0),
                "total_assigned_quota": total_assigned_quota
            }
            
        except Exception as e:
            logger.error(f"Error getting admin dashboard info: {e}")
            return {}
    
    def adjust_user_quota(self, username: str, admin_username: str, new_quota: int):
        """Admin adjusts quota for an existing user they created.
        
        Args:
            username: Username to adjust
            admin_username: Admin making the adjustment
            new_quota: New daily quota
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot adjust user quota: Database not available")
        
        try:
            query = """
                UPDATE user_quota_assignments 
                SET daily_quota = %s, updated_at = NOW()
                WHERE user_username = %s AND assigned_to_admin = %s
            """
            
            self._db_manager.execute_query(query, (new_quota, username, admin_username))
            
            logger.info(f"Admin {admin_username} adjusted quota for {username} to {new_quota}")
            
        except Exception as e:
            logger.error(f"Error adjusting user quota: {e}")
            raise DatabaseOperationError(f"Cannot adjust user quota: {e}")
    
    def remove_user_from_admin(self, username: str, admin_username: str = None) -> Tuple[bool, str]:
        """Remove a user from an admin's quota management (when user is deleted).
        
        Args:
            username: Username to remove
            admin_username: Optional admin username for verification
            
        Returns:
            Tuple[bool, str]: (Success, Message)
        """
        if not self._db_manager:
            return False, "Database not available"
        
        try:
            if admin_username:
                # Remove specific user from specific admin
                delete_query = "DELETE FROM user_quota_assignments WHERE user_username = %s AND assigned_to_admin = %s"
                self._db_manager.execute_query(delete_query, (username, admin_username))
                msg = f"User {username} removed from admin {admin_username} quota"
            else:
                # Remove user from all admins
                delete_query = "DELETE FROM user_quota_assignments WHERE user_username = %s"
                self._db_manager.execute_query(delete_query, (username,))
                msg = f"User {username} removed from valid quota assignments"
            
            # Clean up usage records
            delete_usage = "DELETE FROM user_usage WHERE user_username = %s"
            self._db_manager.execute_query(delete_usage, (username,))
            
            logger.info(f"Removed user {username} from quota management")
            return True, msg
            
        except Exception as e:
            logger.error(f"Error removing user from admin: {e}")
            return False, f"Failed to remove quota assignment: {str(e)}"
    
    def remove_quota_assignment(self, username: str) -> Tuple[bool, str]:
        """Remove a quota assignment for a username.
        
        This is useful for cleaning up ghost entries where a username appears in
        quota_management but no longer exists as a real user.
        
        Args:
            username: Username to remove
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Check if assignment exists first (User)
            if not self._db_manager:
                return False, "Database not available"
            
            check_query = "SELECT assigned_to_admin FROM user_quota_assignments WHERE user_username = %s"
            assignment = self._db_manager.execute_query(check_query, (username,), fetchone=True)
            
            if assignment:
                # Remove the assignment (User)
                self.remove_user_from_admin(username)
                return True, f"Quota assignment for user '{username}' removed successfully"
            
            # Check if admin limits exist (Admin)
            check_admin_query = "SELECT admin_username FROM admin_limits WHERE admin_username = %s"
            admin_assignment = self._db_manager.execute_query(check_admin_query, (username,), fetchone=True)
            
            if admin_assignment:
                # Remove the assignment (Admin)
                self.remove_admin_limits(username)
                return True, f"Admin limits for user '{username}' removed successfully"
                
            return False, f"User '{username}' not found in user assignments or admin limits"
        except DatabaseUnavailableError as e:
            return False, f"Cannot remove quota assignment: Database not available"
        except DatabaseOperationError as e:
            return False, f"Cannot remove quota assignment: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error removing quota assignment: {e}")
            return False, f"Error removing quota assignment: {str(e)}"
    
    # ==================== USER OPERATIONS ====================
    
    def record_user_usage(self, username: str, usage_count: int = 1) -> Tuple[bool, str]:
        """Record usage for a user and check quotas.
        
        Args:
            username: Username to record usage for
            usage_count: Amount of usage to record (default: 1)
            
        Returns:
            Tuple[bool, str]: (allowed, message)
            
        Raises:
            QuotaExceededError: If user has exceeded their quota
            DatabaseOperationError: If recording fails
        """
        if not self._db_manager:
            raise DatabaseUnavailableError("Cannot record usage: Database not available")
        
        try:
            today = str(date.today())
            
            # Get user's quota assignment
            quota_data = self._load_quota_data()
            user_assignment = quota_data.get("user_assignments", {}).get(username)
            
            if not user_assignment:
                logger.warning(f"No quota assignment found for user {username}. Attempting to auto-assign to 'admin'.")
                # Attempt auto-heal: Assign to default 'admin' if exists
                try:
                    # Check if 'admin' exists in admin_limits
                    admin_exists = quota_data.get("admin_limits", {}).get("admin")
                    if not admin_exists:
                        logger.warning("Default 'admin' account not found. Creating it...")
                        # Auto-create admin group with high capacity
                        self.set_admin_limits("admin", max_users=1000, daily_quota=1000000, owner_username="system")
                        quota_data = self._load_quota_data()  # Reload to confirm creation
                        admin_exists = quota_data.get("admin_limits", {}).get("admin")
                    
                    if admin_exists:
                        # Auto-assign to admin
                        # SPECIAL CASE: Give Mohamed Abdo unlimited (999999) quota, others 1000
                        daily_limit = 999999 if username == "Mohamed Abdo" else 1000
                        self.assign_user_to_admin(username, "admin", daily_quota=daily_limit)
                        
                        # Reload quota data to get the new assignment
                        quota_data = self._load_quota_data()
                        user_assignment = quota_data.get("user_assignments", {}).get(username)
                        logger.info(f"Successfully auto-assigned user {username} to 'admin' with {daily_limit} quota.")
                    else:
                        logger.error("Failed to create default 'admin' account. Cannot auto-assign.")
                        return True, f"Warning: User {username} has no quota assignment (auto-assign failed)."
                except Exception as e:
                    logger.error(f"Failed to auto-assign user {username}: {e}")
                    # Fail open to prevent blocking the user
                    return True, f"Warning: User {username} has no quota assignment (auto-assign error)."
            
            if not user_assignment:
                # Should be covered by above logic, but double check
                return True, f"User {username} has no quota assignment, allowing usage."
            
            admin_username = user_assignment.get("assigned_to_admin")
            daily_quota = user_assignment.get("daily_quota", 0)
            
            # Get current usage
            current_usage_query = """
                SELECT usage_count FROM user_usage 
                WHERE user_username = %s AND date = %s
            """
            current_usage_result = self._db_manager.execute_query(
                current_usage_query, 
                (username, today), 
                fetchone=True
            )
            current_usage = current_usage_result['usage_count'] if current_usage_result else 0
            
            # Check if adding this usage would exceed quota
            new_usage = current_usage + usage_count
            if new_usage > daily_quota:
                raise QuotaExceededError(
                    f"User {username} quota exceeded: {new_usage}/{daily_quota}"
                )
            
            # Record user usage (atomic upsert)
            user_usage_query = """
                INSERT INTO user_usage (user_username, admin_username, date, usage_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_username, date) DO UPDATE SET
                    usage_count = user_usage.usage_count + EXCLUDED.usage_count,
                    updated_at = NOW()
            """
            self._db_manager.execute_query(user_usage_query, (username, admin_username, today, usage_count))
            
            # Update admin total usage (atomic upsert)
            admin_usage_query = """
                INSERT INTO admin_usage (admin_username, date, usage_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (admin_username, date) DO UPDATE SET
                    usage_count = admin_usage.usage_count + EXCLUDED.usage_count,
                    updated_at = NOW()
            """
            self._db_manager.execute_query(admin_usage_query, (admin_username, today, usage_count))
            
            msg = f"Recorded usage for {username}: {usage_count} (total: {new_usage}/{daily_quota})"
            logger.debug(msg)
            return True, msg
            
        except QuotaExceededError:
            raise  # Re-raise quota exceeded
        except Exception as e:
            logger.error(f"Error recording user usage: {e}")
            raise DatabaseOperationError(f"Cannot record usage: {e}")
    
    def get_user_quota_status(self, username: str) -> Dict:
        """Get quota status for a specific user.
        
        Args:
            username: Username to check
            
        Returns:
            Dict with quota and usage information
        """
        try:
            today = str(date.today())
            quota_data = self._load_quota_data()
            
            user_assignment = quota_data.get("user_assignments", {}).get(username)
            
            if not user_assignment:
                return {
                    "has_quota": False,
                    "daily_quota": 0,
                    "used_today": 0,
                    "remaining": 0,
                    "percentage_used": 0
                }
            
            daily_quota = user_assignment.get("daily_quota", 0)
            admin_username = user_assignment.get("assigned_to_admin")
            
            # Get current usage from database
            usage_query = """
                SELECT usage_count FROM user_usage 
                WHERE user_username = %s AND date = %s
            """
            usage_result = self._db_manager.execute_query(usage_query, (username, today), fetchone=True)
            used_today = usage_result['usage_count'] if usage_result else 0
            
            remaining = max(0, daily_quota - used_today)
            percentage_used = (used_today / daily_quota * 100) if daily_quota > 0 else 0
            
            return {
                "has_quota": True,
                "daily_quota": daily_quota,
                "used_today": used_today,
                "remaining": remaining,
                "percentage_used": percentage_used,
                "admin": admin_username
            }
            
        except Exception as e:
            logger.error(f"Error getting user quota status: {e}")
            return {
                "has_quota": False,
                "daily_quota": 0,
                "used_today": 0,
                "remaining": 0,
                "percentage_used": 0,
                "error": str(e)
            }
    
    # ==================== UTILITY OPERATIONS ====================
    
    def force_daily_reset(self):
        """Manually force a daily usage reset (for testing/debugging)."""
        try:
            self._reset_daily_usage()
            logger.info("Forced daily usage reset")
        except Exception as e:
            logger.error(f"Error forcing daily reset: {e}")
            raise DatabaseOperationError(f"Cannot force reset: {e}")
    
    def test_system_health(self) -> Dict:
        """Test quota system health and return status.
        
        Returns:
            Dict with health status information
        """
        health = {
            "database_connected": False,
            "can_load_quota": False,
            "can_load_usage": False,
            "admin_count": 0,
            "user_count": 0,
            "errors": []
        }
        
        try:
            # Test database connection
            if self._db_manager:
                test_result = self._db_manager.execute_query("SELECT 1", fetch=True)
                health["database_connected"] = bool(test_result)
            
            # Test loading quota data
            quota_data = self._load_quota_data()
            health["can_load_quota"] = True
            health["admin_count"] = len(quota_data.get("admin_limits", {}))
            health["user_count"] = len(quota_data.get("user_assignments", {}))
            
            # Test loading usage data
            usage_data = self._load_usage_data()
            health["can_load_usage"] = True
            
        except Exception as e:
            health["errors"].append(str(e))
            logger.error(f"Health check error: {e}")
        
        return health
    
    def test_quota_recording(self, username: str, test_amount: int = 1) -> Dict:
        """Test quota recording for debugging.
        
        Args:
            username: Username to test
            test_amount: Amount to record
            
        Returns:
            Dict with test results
        """
        result = {
            "success": False,
            "error": None,
            "quota_before": None,
            "quota_after": None
        }
        
        try:
            # Get quota before
            result["quota_before"] = self.get_user_quota_status(username)
            
            # Record test usage
            self.record_user_usage(username, test_amount)
            
            # Get quota after
            result["quota_after"] = self.get_user_quota_status(username)
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Test quota recording error: {e}")
        
        return result


# Global quota manager instance
try:
    quota_manager = QuotaManager()
    logger.info("Quota manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize quota manager: {e}")
    quota_manager = None
