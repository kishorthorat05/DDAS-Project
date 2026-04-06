"""
Dataset version control system.
Tracks: versions, changes, rollback capability, version history.
"""
from typing import List, Dict, Optional
from datetime import datetime

from app.models.database import get_db, row_to_dict, rows_to_list

def create_dataset_version(dataset_id: str, file_hash: str, file_size: int,
                           created_by_user_id: str, changes_summary: str = None,
                           compressed_size: int = None) -> Optional[Dict]:
    """Create a new version of a dataset."""
    with get_db() as conn:
        # Get current latest version
        current_version = row_to_dict(conn.execute(
            """SELECT MAX(version_number) as max_version FROM dataset_versions
               WHERE dataset_id = ?""",
            (dataset_id,)
        ).fetchone())
        
        next_version = (current_version.get("max_version") or 0) + 1
        
        try:
            conn.execute(
                """INSERT INTO dataset_versions 
                   (dataset_id, version_number, file_hash, file_size, file_size_compressed,
                    changes_summary, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (dataset_id, next_version, file_hash, file_size, compressed_size,
                 changes_summary, created_by_user_id)
            )
            
            # Update dataset to mark it as not latest
            conn.execute(
                "UPDATE datasets SET is_latest_version = 0 WHERE id = ? AND version < ?",
                (dataset_id, next_version)
            )
            
            # Update dataset version number
            conn.execute(
                "UPDATE datasets SET version = ? WHERE id = ?",
                (next_version, dataset_id)
            )
            
            return {
                "dataset_id": dataset_id,
                "version_number": next_version,
                "file_hash": file_hash,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": created_by_user_id
            }
        except Exception:
            return None


def get_dataset_versions(dataset_id: str) -> List[Dict]:
    """Get all versions of a dataset."""
    with get_db() as conn:
        versions = rows_to_list(conn.execute(
            """SELECT id, dataset_id, version_number, file_hash, file_size,
                      file_size_compressed, changes_summary, created_by,
                      created_at
               FROM dataset_versions
               WHERE dataset_id = ?
               ORDER BY version_number DESC""",
            (dataset_id,)
        ).fetchall())
    
    return versions


def get_version_details(version_id: str) -> Optional[Dict]:
    """Get details of a specific version."""
    with get_db() as conn:
        version = row_to_dict(conn.execute(
            """SELECT dv.*, u.username as created_by_user
               FROM dataset_versions dv
               LEFT JOIN users u ON dv.created_by = u.id
               WHERE dv.id = ?""",
            (version_id,)
        ).fetchone())
    
    return version


def rollback_to_version(dataset_id: str, target_version: int, rolled_back_by_user_id: str) -> bool:
    """Rollback dataset to a previous version."""
    with get_db() as conn:
        try:
            # Get target version details
            target = row_to_dict(conn.execute(
                """SELECT * FROM dataset_versions
                   WHERE dataset_id = ? AND version_number = ?""",
                (dataset_id, target_version)
            ).fetchone())
            
            if not target:
                return False
            
            # Create rollback entry (as a new version)
            create_dataset_version(
                dataset_id,
                target["file_hash"],
                target["file_size"],
                rolled_back_by_user_id,
                f"Rollback to version {target_version}",
                target.get("file_size_compressed")
            )
            
            return True
        except Exception:
            return False


def compare_versions(version1_id: str, version2_id: str) -> Dict:
    """Compare two dataset versions."""
    with get_db() as conn:
        v1 = row_to_dict(conn.execute(
            "SELECT * FROM dataset_versions WHERE id = ?",
            (version1_id,)
        ).fetchone())
        
        v2 = row_to_dict(conn.execute(
            "SELECT * FROM dataset_versions WHERE id = ?",
            (version2_id,)
        ).fetchone())
    
    if not v1 or not v2:
        return {}
    
    comparison = {
        "version_1": {
            "version_number": v1["version_number"],
            "file_hash": v1["file_hash"],
            "file_size_mb": round(v1["file_size"] / (1024**2), 2),
            "created_at": v1["created_at"]
        },
        "version_2": {
            "version_number": v2["version_number"],
            "file_hash": v2["file_hash"],
            "file_size_mb": round(v2["file_size"] / (1024**2), 2),
            "created_at": v2["created_at"]
        },
        "differences": {
            "hash_match": v1["file_hash"] == v2["file_hash"],
            "size_difference_bytes": v2["file_size"] - v1["file_size"],
            "size_difference_percent": ((v2["file_size"] - v1["file_size"]) / v1["file_size"] * 100) if v1["file_size"] > 0 else 0,
            "compressed_size_difference_bytes": (v2.get("file_size_compressed") or 0) - (v1.get("file_size_compressed") or 0)
        }
    }
    
    return comparison


def get_version_history_timeline(dataset_id: str) -> List[Dict]:
    """Get version history in timeline format."""
    with get_db() as conn:
        versions = rows_to_list(conn.execute(
            """SELECT dv.*, u.username as created_by_user
               FROM dataset_versions dv
               LEFT JOIN users u ON dv.created_by = u.id
               WHERE dv.dataset_id = ?
               ORDER BY dv.created_at ASC""",
            (dataset_id,)
        ).fetchall())
    
    timeline = []
    for v in versions:
        timeline.append({
            "timestamp": v["created_at"],
            "version_number": v["version_number"],
            "file_size_mb": round(v["file_size"] / (1024**2), 2) if v["file_size"] else 0,
            "file_hash": v["file_hash"],
            "changes": v["changes_summary"],
            "created_by": v["created_by_user"],
            "compressed_size_mb": round(v["file_size_compressed"] / (1024**2), 2) if v["file_size_compressed"] else None
        })
    
    return timeline


def get_version_stats(org_id: str = None) -> Dict:
    """Get version control statistics."""
    with get_db() as conn:
        if org_id:
            total_versions = conn.execute(
                """SELECT COUNT(*) FROM dataset_versions dv
                   JOIN datasets d ON dv.dataset_id = d.id
                   WHERE d.organization_id = ?""",
                (org_id,)
            ).fetchone()[0]
            
            avg_versions = conn.execute(
                """SELECT AVG(version_count) FROM (
                   SELECT COUNT(*) as version_count FROM dataset_versions dv
                   JOIN datasets d ON dv.dataset_id = d.id
                   WHERE d.organization_id = ?
                   GROUP BY dv.dataset_id
                )""",
                (org_id,)
            ).fetchone()[0] or 0
            
            datasets_with_versions = conn.execute(
                """SELECT COUNT(DISTINCT dv.dataset_id) FROM dataset_versions dv
                   JOIN datasets d ON dv.dataset_id = d.id
                   WHERE d.organization_id = ?""",
                (org_id,)
            ).fetchone()[0]
        else:
            total_versions = conn.execute(
                "SELECT COUNT(*) FROM dataset_versions"
            ).fetchone()[0]
            
            avg_versions = conn.execute(
                """SELECT AVG(version_count) FROM (
                   SELECT COUNT(*) as version_count FROM dataset_versions
                   GROUP BY dataset_id
                )"""
            ).fetchone()[0] or 0
            
            datasets_with_versions = conn.execute(
                "SELECT COUNT(DISTINCT dataset_id) FROM dataset_versions"
            ).fetchone()[0]
    
    return {
        "total_versions": total_versions,
        "avg_versions_per_dataset": round(avg_versions, 2),
        "datasets_with_versions": datasets_with_versions,
        "rollback_capability": "Full version history maintained"
    }


def auto_cleanup_old_versions(dataset_id: str, keep_versions: int = 10) -> int:
    """Auto-cleanup old versions keeping only the latest N versions."""
    with get_db() as conn:
        # Get versions to delete (keep latest N)
        to_delete = conn.execute(
            """SELECT id FROM dataset_versions
               WHERE dataset_id = ?
               ORDER BY version_number DESC
               LIMIT -1 OFFSET ?""",
            (dataset_id, keep_versions)
        ).fetchall()
        
        deleted_count = 0
        for row in to_delete:
            try:
                conn.execute(
                    "DELETE FROM dataset_versions WHERE id = ?",
                    (row[0],)
                )
                deleted_count += 1
            except Exception:
                pass
    
    return deleted_count
