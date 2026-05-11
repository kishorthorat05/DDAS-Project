"""
User Profile Service - Manages user profiles and role-specific data.
"""
import json
from typing import Any

from app.models.database import (
    get_db, row_to_dict, rows_to_list,
    get_user_profile, update_user_profile, get_user_with_profile,
    get_all_user_profiles, get_profiles_by_role
)


class ProfileService:
    """Service for managing user profiles and role-specific data."""
    
    # Default role permissions
    ROLE_PERMISSIONS = {
        "guest": ["view_dashboard", "view_analytics"],
        "registered": [
            "view_dashboard", "view_analytics", "view_datasets", 
            "download", "upload", "create_alerts", "ai_chat", "export_data", "run_scanner"
        ],
        "admin": ["*"]  # All permissions
    }
    
    # Role descriptions
    ROLE_DESCRIPTIONS = {
        "guest": "Guest - Public access to dashboard and analytics",
        "registered": "Registered User - Can upload datasets and use AI chat",
        "admin": "Administrator - Full access to all features and settings"
    }
    
    @staticmethod
    def get_role_profile(role: str) -> dict:
        """Get the default profile configuration for a role."""
        return {
            "role": role,
            "description": ProfileService.ROLE_DESCRIPTIONS.get(role, "User"),
            "permissions": ProfileService.ROLE_PERMISSIONS.get(role, ProfileService.ROLE_PERMISSIONS["registered"]),
            "default_preferences": {
                "guest": {"limit": 10, "sort_order": "desc", "auto_refresh": False},
                "registered": {"limit": 100, "sort_order": "desc", "auto_refresh": True, "page_size": 20},
                "admin": {"limit": 9999, "sort_order": "desc", "auto_refresh": True, "page_size": 100, "alerts": True, "analytics": True}
            }.get(role, {"limit": 50, "sort_order": "desc"})
        }
    
    @staticmethod
    def get_user_profile_data(user_id: str) -> dict | None:
        """Get complete user profile with role information."""
        profile = get_user_with_profile(user_id)
        if not profile:
            return None
        
        # Enrich profile with role metadata
        role = profile.get("role", "registered")
        profile_data = profile.get("profile", {})
        
        if profile_data and "permissions" in profile_data:
            try:
                profile_data["permissions"] = json.loads(profile_data["permissions"])
            except (json.JSONDecodeError, TypeError):
                profile_data["permissions"] = ProfileService.ROLE_PERMISSIONS.get(role, [])
        
        if profile_data and "preferences" in profile_data:
            try:
                profile_data["preferences"] = json.loads(profile_data["preferences"])
            except (json.JSONDecodeError, TypeError):
                profile_data["preferences"] = ProfileService.get_role_profile(role)["default_preferences"]
        
        # Add role metadata
        profile["role_metadata"] = ProfileService.get_role_profile(role)
        
        return profile
    
    @staticmethod
    def update_user_profile(user_id: str, **kwargs) -> dict | None:
        """Update user profile fields."""
        # Handle JSON fields
        if "permissions" in kwargs and isinstance(kwargs["permissions"], list):
            kwargs["permissions"] = json.dumps(kwargs["permissions"])
        
        if "preferences" in kwargs and isinstance(kwargs["preferences"], dict):
            kwargs["preferences"] = json.dumps(kwargs["preferences"])
        
        result = update_user_profile(user_id, **kwargs)
        
        if result and "permissions" in result:
            try:
                result["permissions"] = json.loads(result["permissions"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        if result and "preferences" in result:
            try:
                result["preferences"] = json.loads(result["preferences"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        return result
    
    @staticmethod
    def get_profiles_by_role(role: str, limit: int = 100) -> list[dict]:
        """Get all profiles for a specific role."""
        profiles = get_profiles_by_role(role, limit)
        
        # Parse JSON fields
        for profile in profiles:
            if "permissions" in profile:
                try:
                    profile["permissions"] = json.loads(profile["permissions"])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if "preferences" in profile:
                try:
                    profile["preferences"] = json.loads(profile["preferences"])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        return profiles
    
    @staticmethod
    def get_all_profiles(limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all user profiles paginated."""
        profiles = get_all_user_profiles(limit, offset)
        
        # Parse JSON fields
        for profile in profiles:
            if "permissions" in profile:
                try:
                    profile["permissions"] = json.loads(profile["permissions"])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if "preferences" in profile:
                try:
                    profile["preferences"] = json.loads(profile["preferences"])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        return profiles
    
    @staticmethod
    def has_permission(user_id: str, permission: str) -> bool:
        """Check if user has a specific permission."""
        user = get_user_with_profile(user_id)
        if not user:
            return False
        profile = user.get("profile") or {}
        
        try:
            permissions = json.loads(profile.get("permissions", "[]"))
        except (json.JSONDecodeError, TypeError):
            permissions = []
        role_permissions = ProfileService.ROLE_PERMISSIONS.get(user.get("role", "registered"), [])
        permissions = list(set(permissions) | set(role_permissions))
        
        # Admin has all permissions
        if "*" in permissions:
            return True
        
        return permission in permissions
    
    @staticmethod
    def get_user_permissions(user_id: str) -> list[str]:
        """Get all permissions for a user."""
        user = get_user_with_profile(user_id)
        if not user:
            return []
        profile = user.get("profile") or {}
        
        try:
            permissions = json.loads(profile.get("permissions", "[]"))
        except (json.JSONDecodeError, TypeError):
            permissions = []
        
        role_permissions = ProfileService.ROLE_PERMISSIONS.get(user.get("role", "registered"), [])
        return list(set(permissions) | set(role_permissions))
    
    @staticmethod
    def get_user_preferences(user_id: str) -> dict:
        """Get user preferences."""
        profile = get_user_profile(user_id)
        if not profile:
            return {}
        
        try:
            preferences = json.loads(profile.get("preferences", "{}"))
        except (json.JSONDecodeError, TypeError):
            preferences = {}
        
        return preferences
    
    @staticmethod
    def update_user_preferences(user_id: str, **prefs) -> dict | None:
        """Update user preferences (partial update)."""
        current_prefs = ProfileService.get_user_preferences(user_id)
        current_prefs.update(prefs)
        
        return ProfileService.update_user_profile(user_id, preferences=current_prefs)
    
    @staticmethod
    def increment_user_stat(user_id: str, stat_name: str, amount: int = 1) -> None:
        """Increment a user profile statistic."""
        valid_stats = ["total_uploads", "total_downloads", "datasets_created", "duplicates_found"]
        
        if stat_name not in valid_stats:
            return
        
        with get_db() as conn:
            conn.execute(
                f"UPDATE user_profiles SET {stat_name} = {stat_name} + ? WHERE user_id = ?",
                (amount, user_id)
            )
    
    @staticmethod
    def get_user_stats(user_id: str) -> dict:
        """Get user statistics."""
        profile = get_user_profile(user_id)
        if not profile:
            return {}
        
        return {
            "total_uploads": profile.get("total_uploads", 0),
            "total_downloads": profile.get("total_downloads", 0),
            "datasets_created": profile.get("datasets_created", 0),
            "duplicates_found": profile.get("duplicates_found", 0)
        }
    
    @staticmethod
    def update_last_active(user_id: str) -> None:
        """Update user's last active timestamp."""
        from datetime import datetime
        update_user_profile(user_id, last_active=datetime.utcnow().isoformat() + "Z")
    
    @staticmethod
    def get_role_summary() -> dict:
        """Get summary of all roles and their permissions."""
        summary = {}
        for role in ["guest", "registered", "admin"]:
            summary[role] = ProfileService.get_role_profile(role)
        
        return summary
