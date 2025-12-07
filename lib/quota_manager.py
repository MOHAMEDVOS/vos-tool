#!/usr/bin/env python3
"""
Hierarchical Quota Management System for VOS Application
Implements Owner -> Admin -> User quota control with real-time tracking
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class QuotaManager:
    """Manages hierarchical quota system: Owner -> Admin -> Users"""
    
    def __init__(self):
        self.quota_file = Path("dashboard_data/quota_management.json")
        self.usage_file = Path("dashboard_data/daily_usage.json")
        
        # Ensure directories exist
        try:
            self.quota_file.parent.mkdir(parents=True, exist_ok=True)
            self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating quota directories: {e}")
        
        # Initialize files if they don't exist
        try:
            if not self.quota_file.exists():
                self._initialize_quota_system()
            if not self.usage_file.exists():
                self._initialize_usage_tracking()
        except Exception as e:
            logger.error(f"Error initializing quota system: {e}")
    
    def _initialize_quota_system(self):
        """Initialize the quota management system"""
        initial_data = {
            "system_config": {
                "quota_reset_time": "00:00",  # Daily reset at midnight
                "default_admin_user_limit": 10,
                "default_admin_daily_quota": 5000
            },
            "admin_limits": {
                # "admin_username": {
                #     "max_users": 10,
                #     "daily_quota": 5000,
                #     "created_by": "Mohamed Abdo",
                #     "created_date": "2025-01-01"
                # }
            },
            "user_assignments": {
                # "user_username": {
                #     "assigned_to_admin": "admin_username",
                #     "daily_quota": 1000,
                #     "created_date": "2025-01-01"
                # }
            }
        }
        
        with open(self.quota_file, 'w') as f:
            json.dump(initial_data, f, indent=2)
    
    def _initialize_usage_tracking(self):
        """Initialize daily usage tracking"""
        initial_usage = {
            "last_reset_date": str(date.today()),
            "admin_usage": {
                # "admin_username": {
                #     "total_used": 0,
                #     "users_usage": {
                #         "user1": 150,
                #         "user2": 300
                #     }
                # }
            }
        }
        
        with open(self.usage_file, 'w') as f:
            json.dump(initial_usage, f, indent=2)
    
    def _load_quota_data(self) -> Dict:
        """Load quota configuration data"""
        try:
            with open(self.quota_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Error parsing quota data file: {e}")
            # Backup corrupted file
            try:
                backup_path = self.quota_file.with_suffix('.json.backup')
                self.quota_file.rename(backup_path)
                logger.info(f"Backed up corrupted quota file to {backup_path}")
            except Exception:
                pass
            self._initialize_quota_system()
            return self._load_quota_data()
        except (OSError, IOError) as e:
            logger.error(f"Error accessing quota data file: {e}")
            self._initialize_quota_system()
            return self._load_quota_data()
        except Exception as e:
            logger.error(f"Unexpected error loading quota data: {e}")
            self._initialize_quota_system()
            return self._load_quota_data()
    
    def _save_quota_data(self, data: Dict):
        """Save quota configuration data"""
        try:
            with open(self.quota_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving quota data: {e}")
    
    def _load_usage_data(self) -> Dict:
        """Load daily usage tracking data"""
        try:
            with open(self.usage_file, 'r', encoding='utf-8') as f:
                usage_data = json.load(f)
                
            # Check if we need to reset daily usage
            if usage_data.get("last_reset_date") != str(date.today()):
                usage_data = self._reset_daily_usage()
            else:
                # Validate and fix any negative values (from previous bugs)
                needs_save = False
                for admin_username, admin_data in usage_data.get("admin_usage", {}).items():
                    if admin_data.get("total_used", 0) < 0:
                        logger.warning(f"Fixed negative total_used for {admin_username}: {admin_data['total_used']} -> 0")
                        admin_data["total_used"] = 0
                        needs_save = True
                    
                    # Also check user usage values
                    for username, user_usage in admin_data.get("users_usage", {}).items():
                        if user_usage < 0:
                            logger.warning(f"Fixed negative usage for user {username}: {user_usage} -> 0")
                            admin_data["users_usage"][username] = 0
                            needs_save = True
                
                if needs_save:
                    self._save_usage_data(usage_data)
                
            return usage_data
        except Exception as e:
            logger.error(f"Error loading usage data: {e}")
            self._initialize_usage_tracking()
            return self._load_usage_data()
    
    def _save_usage_data(self, data: Dict):
        """Save daily usage tracking data"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")
    
    def _reset_daily_usage(self) -> Dict:
        """Reset daily usage counters"""
        reset_data = {
            "last_reset_date": str(date.today()),
            "admin_usage": {}
        }
        
        # Initialize admin usage for existing admins
        quota_data = self._load_quota_data()
        
        # Initialize all admins with their users
        for admin_username in quota_data.get("admin_limits", {}):
            reset_data["admin_usage"][admin_username] = {
                "total_used": 0,
                "users_usage": {}
            }
            
            # Initialize all users belonging to this admin with 0 usage
            for username, assignment in quota_data.get("user_assignments", {}).items():
                if assignment.get("assigned_to_admin") == admin_username:
                    reset_data["admin_usage"][admin_username]["users_usage"][username] = 0
        
        self._save_usage_data(reset_data)
        logger.info(f"Daily usage reset completed for {date.today()}")
        return reset_data
    
    # ===== OWNER FUNCTIONS =====
    
    def set_admin_limits(self, admin_username: str, max_users: int, daily_quota: int, owner_username: str) -> bool:
        """Owner sets limits for an Admin"""
        try:
            # Validate input parameters
            if max_users < 0 or daily_quota < 0:
                logger.error(f"Invalid limits: max_users={max_users}, daily_quota={daily_quota}")
                return False
            
            if not admin_username or not owner_username:
                logger.error("Admin username and owner username cannot be empty")
                return False
            
            quota_data = self._load_quota_data()
            
            quota_data["admin_limits"][admin_username] = {
                "max_users": max_users,
                "daily_quota": daily_quota,
                "created_by": owner_username,
                "created_date": str(date.today()),
                "last_modified": str(datetime.now())
            }
            
            self._save_quota_data(quota_data)
            
            # Initialize usage tracking for this admin
            usage_data = self._load_usage_data()
            if admin_username not in usage_data["admin_usage"]:
                usage_data["admin_usage"][admin_username] = {
                    "total_used": 0,
                    "users_usage": {}
                }
                self._save_usage_data(usage_data)
            
            return True
        except Exception as e:
            logger.error(f"Error setting admin limits: {e}")
            return False
    
    def get_all_admin_limits(self) -> Dict:
        """Owner gets all Admin limits and current usage"""
        quota_data = self._load_quota_data()
        usage_data = self._load_usage_data()
        
        result = {}
        for admin_username, limits in quota_data.get("admin_limits", {}).items():
            usage_info = usage_data["admin_usage"].get(admin_username, {"total_used": 0, "users_usage": {}})
            
            result[admin_username] = {
                "limits": limits,
                "current_usage": usage_info["total_used"],
                "remaining_quota": limits["daily_quota"] - usage_info["total_used"],
                "users_created": len(self.get_admin_created_users(admin_username)),
                "remaining_user_slots": limits["max_users"] - len(self.get_admin_created_users(admin_username))
            }
        
        return result
    
    def remove_admin_limits(self, admin_username: str) -> bool:
        """Owner removes an Admin's limits (when Admin is deleted)"""
        try:
            quota_data = self._load_quota_data()
            usage_data = self._load_usage_data()
            
            # Remove from quota data
            if admin_username in quota_data["admin_limits"]:
                del quota_data["admin_limits"][admin_username]
            
            # Remove users assigned to this admin
            users_to_remove = []
            for username, assignment in quota_data.get("user_assignments", {}).items():
                if assignment.get("assigned_to_admin") == admin_username:
                    users_to_remove.append(username)
            
            for username in users_to_remove:
                del quota_data["user_assignments"][username]
            
            # Remove from usage data
            if admin_username in usage_data["admin_usage"]:
                del usage_data["admin_usage"][admin_username]
            
            self._save_quota_data(quota_data)
            self._save_usage_data(usage_data)
            
            return True
        except Exception as e:
            logger.error(f"Error removing admin limits: {e}")
            return False
    
    # ===== ADMIN FUNCTIONS =====
    
    def can_admin_create_user(self, admin_username: str) -> Tuple[bool, str]:
        """Check if Admin can create another user"""
        quota_data = self._load_quota_data()
        
        if admin_username not in quota_data.get("admin_limits", {}):
            return False, "Admin limits not configured by Owner"
        
        admin_limits = quota_data["admin_limits"][admin_username]
        created_users = self.get_admin_created_users(admin_username)
        
        if len(created_users) >= admin_limits["max_users"]:
            return False, f"Maximum user limit reached ({admin_limits['max_users']})"
        
        return True, f"Can create {admin_limits['max_users'] - len(created_users)} more users"
    
    def assign_user_to_admin(self, username: str, admin_username: str, daily_quota: int) -> Tuple[bool, str]:
        """Admin assigns a user with specific quota"""
        # Check if admin can create this user
        can_create, message = self.can_admin_create_user(admin_username)
        if not can_create:
            return False, message
        
        # Check if quota assignment is valid
        if not self.can_admin_assign_quota(admin_username, daily_quota):
            return False, "Insufficient quota available for assignment"
        
        try:
            quota_data = self._load_quota_data()
            
            quota_data["user_assignments"][username] = {
                "assigned_to_admin": admin_username,
                "daily_quota": daily_quota,
                "created_date": str(date.today())
            }
            
            self._save_quota_data(quota_data)
            return True, "User assigned successfully"
        except Exception as e:
            logger.error(f"Error assigning user to admin: {e}")
            return False, "System error during assignment"
    
    def can_admin_assign_quota(self, admin_username: str, requested_quota: int) -> bool:
        """Check if Admin has enough quota to assign"""
        quota_data = self._load_quota_data()
        
        if admin_username not in quota_data.get("admin_limits", {}):
            return False
        
        admin_limits = quota_data["admin_limits"][admin_username]
        current_assignments = self.get_admin_quota_usage(admin_username)
        
        total_assigned = sum(user_data["daily_quota"] for user_data in current_assignments.values())
        
        return (total_assigned + requested_quota) <= admin_limits["daily_quota"]
    
    def get_admin_created_users(self, admin_username: str) -> List[str]:
        """Get list of users created by specific Admin"""
        quota_data = self._load_quota_data()
        
        created_users = []
        for username, assignment in quota_data.get("user_assignments", {}).items():
            if assignment.get("assigned_to_admin") == admin_username:
                created_users.append(username)
        
        return created_users
    
    def get_admin_quota_usage(self, admin_username: str) -> Dict:
        """Get Admin's quota usage breakdown"""
        quota_data = self._load_quota_data()
        
        quota_assignments = {}
        for username, assignment in quota_data.get("user_assignments", {}).items():
            if assignment.get("assigned_to_admin") == admin_username:
                quota_assignments[username] = assignment
        
        return quota_assignments
    
    def get_admin_dashboard_info(self, admin_username: str) -> Dict:
        """Get comprehensive dashboard info for Admin"""
        try:
            quota_data = self._load_quota_data()
            usage_data = self._load_usage_data()
            
            if admin_username not in quota_data.get("admin_limits", {}):
                return {"error": "Admin limits not configured"}
        except Exception as e:
            logger.error(f"Error loading quota data for {admin_username}: {e}")
            return {"error": f"Unable to load quota information: {str(e)}"}
        
        admin_limits = quota_data["admin_limits"][admin_username]
        created_users = self.get_admin_created_users(admin_username)
        quota_assignments = self.get_admin_quota_usage(admin_username)
        current_usage = usage_data["admin_usage"].get(admin_username, {"total_used": 0, "users_usage": {}})
        
        # Calculate total quota allocated to users
        total_assigned_quota = sum(assignment["daily_quota"] for assignment in quota_assignments.values())
        
        # Calculate total ACTUAL usage (admin personal + all users)
        admin_personal_usage = current_usage["total_used"]
        users_total_usage = sum(current_usage["users_usage"].values())
        total_usage = admin_personal_usage + users_total_usage
        
        # Single quota pool calculation
        daily_quota_pool = admin_limits["daily_quota"]
        
        # Remaining quota calculation:
        # Remaining = Total Pool - (Assigned to Users + Admin Personal Usage)
        # This shows how much quota is truly available (not assigned and not used by admin)
        remaining_quota = daily_quota_pool - total_assigned_quota - admin_personal_usage
        
        # Available for assignment = Total Pool - Already Assigned
        available_for_assignment = daily_quota_pool - total_assigned_quota
        
        return {
            "max_users": admin_limits["max_users"],
            "users_created": len(created_users),
            "remaining_user_slots": admin_limits["max_users"] - len(created_users),
            "daily_quota_pool": daily_quota_pool,  # Single quota pool
            "total_usage": total_usage,  # Combined admin + users usage
            "remaining_quota": remaining_quota,  # What's left to use
            "quota_assigned_to_users": total_assigned_quota,  # How much allocated to users
            "available_for_assignment": available_for_assignment,  # Available to assign to new users
            "admin_personal_usage": admin_personal_usage,  # Admin's personal usage
            "users_total_usage": users_total_usage,  # All users' combined usage
            "created_users_list": created_users,
            "quota_breakdown": quota_assignments,
            "users_usage": current_usage["users_usage"]
        }
    
    def adjust_user_quota(self, username: str, admin_username: str, new_quota: int) -> Tuple[bool, str]:
        """Admin adjusts quota for an existing user they created"""
        try:
            quota_data = self._load_quota_data()
            
            if username not in quota_data.get("user_assignments", {}):
                return False, "User not found in assignments"
            
            assignment = quota_data["user_assignments"][username]
            if assignment.get("assigned_to_admin") != admin_username:
                return False, "User not assigned to this admin"
            
            current_quota = assignment["daily_quota"]
            
            # If quota is being reduced, no additional checks needed
            # If quota is being increased, check if admin has available quota
            if new_quota > current_quota:
                quota_increase = new_quota - current_quota
                if not self.can_admin_assign_quota(admin_username, quota_increase):
                    return False, f"Insufficient quota available. Need {quota_increase} more quota units."
            
            # Update the quota assignment
            assignment["daily_quota"] = new_quota
            assignment["last_modified"] = str(datetime.now())
            
            self._save_quota_data(quota_data)
            return True, f"User quota updated from {current_quota} to {new_quota}"
            
        except Exception as e:
            logger.error(f"Error adjusting user quota: {e}")
            return False, "System error during quota adjustment"
    
    def remove_user_from_admin(self, username: str, admin_username: str) -> Tuple[bool, str]:
        """Remove a user from an admin's quota management (when user is deleted)"""
        try:
            quota_data = self._load_quota_data()
            usage_data = self._load_usage_data()
            
            # Check if user is assigned to this admin
            if username not in quota_data.get("user_assignments", {}):
                return False, "User not found in quota assignments"
            
            assignment = quota_data["user_assignments"][username]
            if assignment.get("assigned_to_admin") != admin_username:
                return False, "User not assigned to this admin"
            
            # Get user's assigned and used quota before deletion
            assigned_quota = assignment["daily_quota"]
            user_used_quota = 0
            
            # Transfer user's consumed quota to admin's personal usage
            # This preserves the used quota while allowing unused quota to be reclaimed
            if admin_username in usage_data["admin_usage"]:
                admin_usage = usage_data["admin_usage"][admin_username]
                if username in admin_usage["users_usage"]:
                    user_used_quota = admin_usage["users_usage"][username]
                    # Add user's consumed quota to admin's personal usage
                    admin_usage["total_used"] += user_used_quota
                    # Remove user from usage tracking
                    del admin_usage["users_usage"][username]
            
            # Remove from user assignments (this frees up the assigned quota)
            del quota_data["user_assignments"][username]
            
            # Calculate reclaimed quota
            unused_quota = assigned_quota - user_used_quota
            
            self._save_quota_data(quota_data)
            self._save_usage_data(usage_data)
            
            # Return detailed message about quota reclamation
            if user_used_quota > 0:
                return True, f"User removed. Used quota ({user_used_quota}) preserved, unused quota ({unused_quota}) reclaimed."
            else:
                return True, f"User removed. All assigned quota ({assigned_quota}) reclaimed."
            
        except Exception as e:
            logger.error(f"Error removing user from admin: {e}")
            return False, "System error during user removal"
    
    def remove_quota_assignment(self, username: str) -> Tuple[bool, str]:
        """Remove a quota assignment for a username without touching main user storage.

        This is useful for cleaning up ghost entries where a username appears in
        quota_management.json user_assignments but no longer exists as a real user.
        """
        try:
            quota_data = self._load_quota_data()
            user_assignments = quota_data.get("user_assignments", {})
            
            if username not in user_assignments:
                return False, "User not found in quota assignments"
            
            # Remove from quota assignments
            del user_assignments[username]
            quota_data["user_assignments"] = user_assignments
            self._save_quota_data(quota_data)
            
            # Also clean up any usage tracking for this username, if present
            usage_data = self._load_usage_data()
            changed_usage = False
            for admin_username, admin_data in usage_data.get("admin_usage", {}).items():
                users_usage = admin_data.get("users_usage", {})
                if username in users_usage:
                    del users_usage[username]
                    admin_data["users_usage"] = users_usage
                    changed_usage = True
            
            if changed_usage:
                self._save_usage_data(usage_data)
            
            return True, f"Quota assignment for user '{username}' removed"
        except Exception as e:
            logger.error(f"Error removing quota assignment for {username}: {e}")
            return False, "System error during quota assignment cleanup"
    
    def record_user_usage(self, username: str, usage_count: int) -> Tuple[bool, str]:
        """Record usage for a user and check quotas"""
        quota_data = self._load_quota_data()
        usage_data = self._load_usage_data()
        
        # Find which admin this user belongs to
        if username not in quota_data.get("user_assignments", {}):
            return True, "User not under quota management"  # Allow usage for non-managed users
        
        assignment = quota_data["user_assignments"][username]
        admin_username = assignment["assigned_to_admin"]
        user_daily_quota = assignment["daily_quota"]
        
        # Initialize usage tracking if needed
        if admin_username not in usage_data["admin_usage"]:
            usage_data["admin_usage"][admin_username] = {"total_used": 0, "users_usage": {}}
        
        if username not in usage_data["admin_usage"][admin_username]["users_usage"]:
            usage_data["admin_usage"][admin_username]["users_usage"][username] = 0
        
        # Check user quota
        current_user_usage = usage_data["admin_usage"][admin_username]["users_usage"][username]
        if current_user_usage + usage_count > user_daily_quota:
            return False, f"User daily quota exceeded ({user_daily_quota})"
        
        # Check admin total quota (admin personal + all users combined)
        if admin_username not in quota_data.get("admin_limits", {}):
            return False, "Admin limits not configured"
        
        admin_limits = quota_data["admin_limits"][admin_username]
        admin_personal_usage = usage_data["admin_usage"][admin_username]["total_used"]
        users_total_usage = sum(usage_data["admin_usage"][admin_username]["users_usage"].values())
        combined_usage = admin_personal_usage + users_total_usage
        
        if combined_usage + usage_count > admin_limits["daily_quota"]:
            return False, f"Admin total quota exceeded ({admin_limits['daily_quota']})"
        
        # Record the usage - ONLY increment user's usage, NOT admin's total_used
        # admin's total_used is for admin's personal usage only
        usage_data["admin_usage"][admin_username]["users_usage"][username] += usage_count
        
        self._save_usage_data(usage_data)
        
        return True, f"Usage recorded: {usage_count} units"
    
    def get_user_quota_status(self, username: str) -> Dict:
        """Get quota status for a specific user"""
        quota_data = self._load_quota_data()
        usage_data = self._load_usage_data()
        
        if username not in quota_data.get("user_assignments", {}):
            return {"managed": False, "message": "User not under quota management"}
        
        assignment = quota_data["user_assignments"][username]
        admin_username = assignment["assigned_to_admin"]
        user_daily_quota = assignment["daily_quota"]
        
        current_usage = 0
        if admin_username in usage_data["admin_usage"]:
            current_usage = usage_data["admin_usage"][admin_username]["users_usage"].get(username, 0)
        
        return {
            "managed": True,
            "daily_quota": user_daily_quota,
            "current_usage": current_usage,
            "remaining": max(0, user_daily_quota - current_usage),
            "percentage_used": (current_usage / user_daily_quota * 100) if user_daily_quota > 0 else 0,
            "admin": admin_username
        }
    
    def force_daily_reset(self) -> Tuple[bool, str]:
        """Manually force a daily usage reset (for testing/debugging)"""
        try:
            reset_data = self._reset_daily_usage()
            return True, f"Daily usage reset completed. Reset date: {reset_data.get('last_reset_date')}"
        except Exception as e:
            logger.error(f"Error forcing daily reset: {e}")
            return False, f"Reset failed: {str(e)}"
    
    def test_system_health(self) -> Dict:
        """Test quota system health and return status"""
        try:
            # Test file access
            quota_data = self._load_quota_data()
            usage_data = self._load_usage_data()
            
            # Check if reset is needed
            needs_reset = usage_data.get("last_reset_date") != str(date.today())
            
            return {
                "status": "healthy",
                "quota_file_exists": self.quota_file.exists(),
                "usage_file_exists": self.usage_file.exists(),
                "admin_count": len(quota_data.get("admin_limits", {})),
                "user_assignments": len(quota_data.get("user_assignments", {})),
                "last_reset_date": usage_data.get("last_reset_date"),
                "current_date": str(date.today()),
                "needs_reset": needs_reset,
                "reset_status": "Reset needed - will occur on next usage check" if needs_reset else "Up to date"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def test_quota_recording(self, username: str, test_amount: int = 1) -> Dict:
        """Test quota recording for debugging"""
        try:
            # Get status before
            before_status = self.get_user_quota_status(username)
            
            # Try to record usage
            can_use, message = self.record_user_usage(username, test_amount)
            
            # Get status after
            after_status = self.get_user_quota_status(username)
            
            return {
                "success": True,
                "can_use": can_use,
                "message": message,
                "before_usage": before_status.get("current_usage", 0),
                "after_usage": after_status.get("current_usage", 0),
                "usage_increased": after_status.get("current_usage", 0) > before_status.get("current_usage", 0)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global quota manager instance
try:
    quota_manager = QuotaManager()
    logger.info("Quota manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize quota manager: {e}")
    quota_manager = None
