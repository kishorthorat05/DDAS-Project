"""
Collaboration and team sharing features.
Manages: teams, resource sharing, permissions, collaborative workflows.
"""
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.models.database import get_db, row_to_dict, rows_to_list

def create_team_invite(org_id: str, user_email: str, role_id: str) -> Optional[Dict]:
    """Create an invitation to join a team."""
    with get_db() as conn:
        # Check if user already in org
        existing = row_to_dict(conn.execute(
            """SELECT u.id FROM users u
               WHERE u.email = ? AND u.organization_id = ?""",
            (user_email, org_id)
        ).fetchone())
        
        if existing:
            return None  # Already a member
        
        # Store invitation (simplified - in production use email service)
        invite_code = f"invite_{org_id}_{user_email.split('@')[0]}"[:50]
        
        conn.execute(
            """INSERT INTO team_members (organization_id, user_id, role_id, is_active)
               SELECT ?, id, ?, 0
               FROM users WHERE email = ?""",
            (org_id, role_id, user_email)
        )
        
        return {
            "invite_code": invite_code,
            "email": user_email,
            "organization_id": org_id
        }


def share_dataset(dataset_id: str, shared_by_user_id: str, shared_with_user_id: str,
                 permission: str = "view", expiry_days: int = None) -> bool:
    """Share a dataset with another user."""
    with get_db() as conn:
        try:
            expiry = None
            if expiry_days:
                expiry = (datetime.utcnow() + timedelta(days=expiry_days)).isoformat()
            
            conn.execute(
                """INSERT INTO shared_datasets 
                   (dataset_id, shared_by, shared_with, permission, expiry_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (dataset_id, shared_by_user_id, shared_with_user_id, permission, expiry)
            )
            return True
        except Exception:
            return False


def get_shared_with_me(user_id: str) -> List[Dict]:
    """Get datasets shared with me."""
    with get_db() as conn:
        shared = rows_to_list(conn.execute(
            """SELECT sd.id, sd.dataset_id, d.file_name, d.file_size, d.file_type,
                      sd.shared_by, u.username as shared_by_user, sd.permission,
                      sd.created_at, sd.expiry_date
               FROM shared_datasets sd
               JOIN datasets d ON sd.dataset_id = d.id
               JOIN users u ON sd.shared_by = u.id
               WHERE sd.shared_with = ? AND sd.is_revoked = 0
               AND (sd.expiry_date IS NULL OR sd.expiry_date > datetime('now'))
               ORDER BY sd.created_at DESC""",
            (user_id,)
        ).fetchall())
    
    return shared


def get_shared_by_me(user_id: str) -> List[Dict]:
    """Get datasets I've shared."""
    with get_db() as conn:
        shared = rows_to_list(conn.execute(
            """SELECT sd.id, sd.dataset_id, d.file_name, sd.shared_with,
                      u.username as shared_with_user, sd.permission, sd.created_at
               FROM shared_datasets sd
               JOIN datasets d ON sd.dataset_id = d.id
               JOIN users u ON sd.shared_with = u.id
               WHERE sd.shared_by = ? AND sd.is_revoked = 0
               ORDER BY sd.created_at DESC""",
            (user_id,)
        ).fetchall())
    
    return shared


def revoke_sharing(sharing_id: str) -> bool:
    """Revoke a dataset sharing."""
    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE shared_datasets SET is_revoked = 1 WHERE id = ?",
                (sharing_id,)
            )
            return True
        except Exception:
            return False


def add_team_member(org_id: str, user_id: str, role_id: str = None) -> bool:
    """Add a member to a team/organization."""
    with get_db() as conn:
        try:
            conn.execute(
                """INSERT INTO team_members (organization_id, user_id, role_id)
                   VALUES (?, ?, ?)""",
                (org_id, user_id, role_id)
            )
            # Also update user's organization
            conn.execute(
                "UPDATE users SET organization_id = ? WHERE id = ?",
                (org_id, user_id)
            )
            return True
        except Exception:
            return False


def remove_team_member(org_id: str, user_id: str) -> bool:
    """Remove a member from a team."""
    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE team_members SET is_active = 0 WHERE organization_id = ? AND user_id = ?",
                (org_id, user_id)
            )
            return True
        except Exception:
            return False


def get_team_members(org_id: str) -> List[Dict]:
    """Get all active members of a team."""
    with get_db() as conn:
        members = rows_to_list(conn.execute(
            """SELECT u.id, u.username, u.email, tm.role_id, r.name as role_name,
                      tm.joined_at, tm.is_active
               FROM team_members tm
               JOIN users u ON tm.user_id = u.id
               LEFT JOIN roles r ON tm.role_id = r.id
               WHERE tm.organization_id = ? AND tm.is_active = 1
               ORDER BY tm.joined_at DESC""",
            (org_id,)
        ).fetchall())
    
    return members


def get_organization_info(org_id: str) -> Optional[Dict]:
    """Get organization details."""
    with get_db() as conn:
        org = row_to_dict(conn.execute(
            """SELECT id, name, description, plan_tier, max_storage_gb, max_users,
                      (SELECT COUNT(*) FROM team_members WHERE organization_id = ? AND is_active = 1) as active_members,
                      (SELECT COUNT(*) FROM datasets WHERE organization_id = ?) as total_datasets
               FROM organizations
               WHERE id = ?""",
            (org_id, org_id, org_id)
        ).fetchone())
    
    return org


def create_organization(name: str, owner_id: str, description: str = None) -> Optional[Dict]:
    """Create a new organization."""
    with get_db() as conn:
        try:
            org_id = f"org_{name[:20]}_{owner_id[:8]}"[:40]
            
            conn.execute(
                """INSERT INTO organizations (id, name, description, owner_id, plan_tier)
                   VALUES (?, ?, ?, ?, ?)""",
                (org_id, name, description, owner_id, "free")
            )
            
            # Add owner as member
            conn.execute(
                """INSERT INTO team_members (organization_id, user_id)
                   SELECT ?, id FROM users WHERE id = ?""",
                (org_id, owner_id)
            )
            
            return {
                "id": org_id,
                "name": name,
                "description": description,
                "owner_id": owner_id
            }
        except Exception:
            return None


def get_collaboration_stats(org_id: str) -> Dict:
    """Get collaboration statistics for an organization."""
    with get_db() as conn:
        stats = {}
        
        # Total shared datasets
        total_shared = conn.execute(
            """SELECT COUNT(*) FROM shared_datasets sd
               JOIN datasets d ON sd.dataset_id = d.id
               WHERE d.organization_id = ?""",
            (org_id,)
        ).fetchone()[0]
        
        # Total active sharings
        active_sharings = conn.execute(
            """SELECT COUNT(*) FROM shared_datasets sd
               JOIN datasets d ON sd.dataset_id = d.id
               WHERE d.organization_id = ? AND sd.is_revoked = 0
               AND (sd.expiry_date IS NULL OR sd.expiry_date > datetime('now'))""",
            (org_id,)
        ).fetchone()[0]
        
        # Team members
        team_size = conn.execute(
            """SELECT COUNT(*) FROM team_members
               WHERE organization_id = ? AND is_active = 1""",
            (org_id,)
        ).fetchone()[0]
        
        # Most shared datasets
        most_shared = rows_to_list(conn.execute(
            """SELECT d.id, d.file_name, COUNT(sd.id) as share_count
               FROM datasets d
               LEFT JOIN shared_datasets sd ON d.id = sd.dataset_id AND sd.is_revoked = 0
               WHERE d.organization_id = ?
               GROUP BY d.id
               ORDER BY share_count DESC
               LIMIT 5""",
            (org_id,)
        ).fetchall())
        
        stats["total_shared_datasets"] = total_shared
        stats["active_sharings"] = active_sharings
        stats["team_size"] = team_size
        stats["most_shared_datasets"] = most_shared
    
    return stats
