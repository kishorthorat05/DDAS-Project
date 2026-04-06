"""
Role-based access control and permission management.
Handles: user roles, team permissions, resource access.
"""
import json
from typing import Dict, List, Set

from app.models.database import get_db, row_to_dict, rows_to_list

# Default roles with permissions
DEFAULT_ROLES = {
    "admin": [
        "upload", "download", "delete", "edit", "share", "manage_team",
        "manage_roles", "manage_org", "view_analytics", "manage_integrations"
    ],
    "owner": [
        "upload", "download", "delete", "edit", "share", "manage_team",
        "view_analytics"
    ],
    "operator": [
        "upload", "download", "edit", "share", "view_analytics"
    ],
    "viewer": [
        "download", "view_analytics"
    ],
    "auditor": [
        "download", "view_analytics", "audit_logs"
    ]
}


def init_default_roles() -> None:
    """Initialize default roles if they don't exist."""
    with get_db() as conn:
        for role_name, permissions in DEFAULT_ROLES.items():
            existing = conn.execute(
                "SELECT id FROM roles WHERE name = ?", (role_name,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO roles (name, permissions, is_system) VALUES (?, ?, ?)",
                    (role_name, json.dumps(permissions), 1)
                )


def get_user_permissions(user_id: str) -> Set[str]:
    """Get all permissions for a user based on their role."""
    with get_db() as conn:
        user = row_to_dict(conn.execute(
            "SELECT u.role_id, u.role FROM users WHERE id = ?", (user_id,)
        ).fetchone())
        
        if not user:
            return set()
        
        # Try role_id first (newer system), then backward compat with role
        role_id = user.get("role_id")
        if role_id:
            role = row_to_dict(conn.execute(
                "SELECT permissions FROM roles WHERE id = ?", (role_id,)
            ).fetchone())
            if role:
                return set(json.loads(role["permissions"]))
        
        # Backward compat
        role_name = user.get("role", "viewer")
        return set(DEFAULT_ROLES.get(role_name, []))


def has_permission(user_id: str, permission: str) -> bool:
    """Check if user has a specific permission."""
    permissions = get_user_permissions(user_id)
    return permission in permissions


def get_organization_users(org_id: str, role_id: str = None) -> List[dict]:
    """Get all users in an organization, optionally filtered by role."""
    with get_db() as conn:
        if role_id:
            users = rows_to_list(conn.execute(
                "SELECT u.id, u.username, u.email, u.role FROM users WHERE organization_id = ? AND role_id = ?",
                (org_id, role_id)
            ).fetchall())
        else:
            users = rows_to_list(conn.execute(
                "SELECT u.id, u.username, u.email, u.role FROM users WHERE organization_id = ?",
                (org_id,)
            ).fetchall())
    return users


def assign_role(user_id: str, role_id: str) -> bool:
    """Assign a role to a user."""
    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE users SET role_id = ? WHERE id = ?",
                (role_id, user_id)
            )
            return True
        except Exception:
            return False


def can_access_resource(user_id: str, resource_type: str, resource_id: str) -> bool:
    """Check if user can access a specific resource."""
    with get_db() as conn:
        if resource_type == "dataset":
            # Check if user owns it or it's shared with them
            dataset = row_to_dict(conn.execute(
                "SELECT user_id, organization_id FROM datasets WHERE id = ?",
                (resource_id,)
            ).fetchone())
            
            if not dataset:
                return False
            
            # Owner always has access
            if dataset["user_id"] == user_id:
                return True
            
            # Check if shared
            shared = row_to_dict(conn.execute(
                "SELECT id FROM shared_datasets WHERE dataset_id = ? AND shared_with = ? AND is_revoked = 0",
                (resource_id, user_id)
            ).fetchone())
            
            if shared:
                return True
            
            # Check if in same organization and has permission
            user = row_to_dict(conn.execute(
                "SELECT organization_id FROM users WHERE id = ?", (user_id,)
            ).fetchone())
            
            return user and user["organization_id"] == dataset.get("organization_id")
    
    return False


def log_access_attempt(user_id: str, org_id: str, activity_type: str, 
                        resource_type: str = None, resource_id: str = None,
                        details: dict = None) -> None:
    """Log user activity for audit trail."""
    import socket
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_activity 
               (user_id, organization_id, activity_type, resource_type, resource_id, 
                details, ip_address) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, org_id, activity_type, resource_type, resource_id,
             json.dumps(details or {}), socket.gethostbyname(socket.gethostname()))
        )
