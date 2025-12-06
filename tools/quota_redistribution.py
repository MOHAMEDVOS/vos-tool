#!/usr/bin/env python3
"""
Quota Redistribution System
Allows Admins to reallocate quota between their created users
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class QuotaRedistribution:
    """Handles quota redistribution between users under the same Admin"""
    
    def __init__(self, quota_manager):
        self.quota_manager = quota_manager
    
    def get_redistribution_options(self, admin_username: str) -> Dict:
        """
        Get current quota allocation and redistribution options for an Admin.
        
        Args:
            admin_username: Admin username
            
        Returns:
            Dict with current allocations and redistribution possibilities
        """
        try:
            # Get admin info
            admin_info = self.quota_manager.get_admin_dashboard_info(admin_username)
            if "error" in admin_info:
                return {"error": admin_info["error"]}
            
            # Get created users and their quota status
            created_users = self.quota_manager.get_admin_created_users(admin_username)
            user_details = []
            
            total_assigned = 0
            for username in created_users:
                quota_status = self.quota_manager.get_user_quota_status(username)
                if quota_status.get("managed"):
                    user_details.append({
                        "username": username,
                        "current_quota": quota_status["daily_quota"],
                        "current_usage": quota_status["current_usage"],
                        "remaining": quota_status["remaining"],
                        "usage_percentage": quota_status["percentage_used"]
                    })
                    total_assigned += quota_status["daily_quota"]
            
            return {
                "admin_total_quota": admin_info["daily_quota_pool"],
                "total_assigned": total_assigned,
                "available_quota": admin_info["available_for_assignment"],
                "users": user_details,
                "can_redistribute": len(user_details) > 1
            }
            
        except Exception as e:
            logger.error(f"Error getting redistribution options: {e}")
            return {"error": "Failed to load redistribution options"}
    
    def calculate_redistribution_impact(self, admin_username: str, new_allocations: Dict[str, int]) -> Dict:
        """
        Calculate the impact of proposed quota redistribution.
        
        Args:
            admin_username: Admin username
            new_allocations: Dict of {username: new_quota_amount}
            
        Returns:
            Dict with validation results and impact analysis
        """
        try:
            current_options = self.get_redistribution_options(admin_username)
            if "error" in current_options:
                return current_options
            
            admin_total = current_options["admin_total_quota"]
            total_new_allocation = sum(new_allocations.values())
            
            # Validation
            if total_new_allocation > admin_total:
                return {
                    "valid": False,
                    "error": f"Total allocation ({total_new_allocation}) exceeds admin quota ({admin_total})"
                }
            
            # Calculate changes
            changes = []
            for user_data in current_options["users"]:
                username = user_data["username"]
                current_quota = user_data["current_quota"]
                new_quota = new_allocations.get(username, current_quota)
                
                if new_quota != current_quota:
                    # Check if user's current usage exceeds new quota
                    current_usage = user_data["current_usage"]
                    if current_usage > new_quota:
                        return {
                            "valid": False,
                            "error": f"User {username} has already used {current_usage}, cannot reduce quota to {new_quota}"
                        }
                    
                    changes.append({
                        "username": username,
                        "old_quota": current_quota,
                        "new_quota": new_quota,
                        "change": new_quota - current_quota,
                        "current_usage": current_usage,
                        "new_remaining": new_quota - current_usage
                    })
            
            return {
                "valid": True,
                "total_new_allocation": total_new_allocation,
                "remaining_quota": admin_total - total_new_allocation,
                "changes": changes,
                "affected_users": len(changes)
            }
            
        except Exception as e:
            logger.error(f"Error calculating redistribution impact: {e}")
            return {"valid": False, "error": "Failed to calculate impact"}
    
    def apply_redistribution(self, admin_username: str, new_allocations: Dict[str, int]) -> Tuple[bool, str]:
        """
        Apply quota redistribution for an Admin's users.
        
        Args:
            admin_username: Admin username
            new_allocations: Dict of {username: new_quota_amount}
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Validate the redistribution first
            impact = self.calculate_redistribution_impact(admin_username, new_allocations)
            if not impact.get("valid", False):
                return False, impact.get("error", "Invalid redistribution")
            
            # Load quota data
            quota_data = self.quota_manager._load_quota_data()
            
            # Apply changes
            changes_made = []
            for username, new_quota in new_allocations.items():
                if username in quota_data.get("user_assignments", {}):
                    old_quota = quota_data["user_assignments"][username]["daily_quota"]
                    if old_quota != new_quota:
                        quota_data["user_assignments"][username]["daily_quota"] = new_quota
                        changes_made.append(f"{username}: {old_quota} → {new_quota}")
            
            # Save changes
            self.quota_manager._save_quota_data(quota_data)
            
            if changes_made:
                return True, f"Redistribution successful: {', '.join(changes_made)}"
            else:
                return True, "No changes needed"
                
        except Exception as e:
            logger.error(f"Error applying redistribution: {e}")
            return False, "Failed to apply redistribution"
    
    def suggest_optimal_redistribution(self, admin_username: str) -> Dict:
        """
        Suggest optimal quota redistribution based on usage patterns.
        
        Args:
            admin_username: Admin username
            
        Returns:
            Dict with suggested allocations
        """
        try:
            options = self.get_redistribution_options(admin_username)
            if "error" in options or not options.get("can_redistribute"):
                return {"error": "Cannot generate suggestions"}
            
            users = options["users"]
            total_quota = options["admin_total_quota"]
            
            # Calculate usage-based suggestions
            total_usage = sum(user["current_usage"] for user in users)
            suggestions = {}
            
            for user in users:
                username = user["username"]
                current_usage = user["current_usage"]
                usage_ratio = current_usage / total_usage if total_usage > 0 else 1/len(users)
                
                # Suggest quota based on usage + 50% buffer
                suggested_quota = max(100, int(current_usage * 1.5))
                suggestions[username] = suggested_quota
            
            # Adjust if total exceeds admin quota
            total_suggested = sum(suggestions.values())
            if total_suggested > total_quota:
                # Scale down proportionally
                scale_factor = total_quota / total_suggested
                for username in suggestions:
                    suggestions[username] = max(100, int(suggestions[username] * scale_factor))
            
            # Check if redistribution would be beneficial
            current_total_assigned = sum(user["current_quota"] for user in users)
            suggested_total = sum(suggestions.values())
            
            if abs(suggested_total - current_total_assigned) < 100:
                return {
                    "suggestions": suggestions,
                    "reasoning": "Current allocation is already optimal - no significant changes needed",
                    "total_suggested": suggested_total,
                    "remaining": total_quota - suggested_total,
                    "minimal_change": True
                }
            
            return {
                "suggestions": suggestions,
                "reasoning": "Based on current usage + 50% buffer for optimal resource allocation",
                "total_suggested": suggested_total,
                "remaining": total_quota - suggested_total,
                "minimal_change": False
            }
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {"error": "Failed to generate suggestions"}

# Global redistribution manager
def get_redistribution_manager(quota_manager):
    """Get redistribution manager instance"""
    return QuotaRedistribution(quota_manager)
