"""
Analytics service providing comprehensive metrics, dashboards, and real-time data.
Tracks performance, user behavior, storage optimization, and system health.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List

from app.models.database import get_db, rows_to_list


def get_dashboard_stats() -> Dict:
    """
    Get comprehensive dashboard statistics.
    All metrics for the main dashboard display.
    """
    with get_db() as conn:
        # Total datasets
        total_datasets = conn.execute("SELECT COUNT(*) as count FROM datasets").fetchone()["count"]
        
        # Duplicates found (via alerts of type 'duplicate')
        duplicates_count = conn.execute(
            "SELECT COUNT(*) as count FROM alerts WHERE alert_type = 'duplicate'"
        ).fetchone()["count"]
        
        # Total users
        total_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1").fetchone()["count"]
        
        # Unread alerts
        unread_alerts = conn.execute(
            "SELECT COUNT(*) as count FROM alerts WHERE is_read = 0"
        ).fetchone()["count"]
        
        # Total storage
        storage_bytes = conn.execute(
            "SELECT SUM(file_size) as total FROM datasets"
        ).fetchone()["total"] or 0
        
        # Estimated bandwidth saved (total size of duplicate files)
        duplicates_size = conn.execute("""
            SELECT SUM(d.file_size) as total FROM datasets d
            WHERE EXISTS (
                SELECT 1 FROM alerts a 
                WHERE a.file_hash = d.file_hash AND a.alert_type = 'duplicate'
            )
        """).fetchone()["total"] or 0
        
        # Recently added files (last 7 days)
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent_files = conn.execute(
            "SELECT COUNT(*) as count FROM datasets WHERE created_at > ?",
            (week_ago,)
        ).fetchone()["count"]
        
        # Most active users (last 30 days)
        month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        active_users = conn.execute("""
            SELECT COUNT(DISTINCT user_name) as count 
            FROM download_history 
            WHERE attempt_timestamp > ?
        """, (month_ago,)).fetchone()["count"]
    
    return {
        "total_datasets": total_datasets,
        "duplicates_detected": duplicates_count,
        "duplication_rate": (duplicates_count / max(total_datasets, 1)) * 100,
        "total_users": total_users,
        "active_users_30d": active_users,
        "unread_alerts": unread_alerts,
        "total_storage_gb": storage_bytes / (1024 ** 3),
        "bandwidth_saved_gb": duplicates_size / (1024 ** 3),
        "storage_efficiency": ((duplicates_size / max(storage_bytes, 1)) * 100) if storage_bytes > 0 else 0,
        "new_files_7d": recent_files,
    }


def get_timeline_data(days: int = 30) -> Dict:
    """
    Get timeline data for charts: daily file uploads, duplicates, storage growth.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    with get_db() as conn:
        # Daily upload counts
        daily_uploads = conn.execute("""
            SELECT DATE(download_timestamp) as date, COUNT(*) as count
            FROM datasets
            WHERE download_timestamp > ?
            GROUP BY DATE(download_timestamp)
            ORDER BY date ASC
        """, (cutoff,)).fetchall()
        
        # Daily duplicate detections
        daily_duplicates = conn.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM alerts
            WHERE alert_type = 'duplicate' AND created_at > ?
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """, (cutoff,)).fetchall()
        
        # Cumulative storage growth
        daily_storage = conn.execute("""
            SELECT DATE(download_timestamp) as date, SUM(file_size) as bytes
            FROM datasets
            WHERE download_timestamp > ?
            GROUP BY DATE(download_timestamp)
            ORDER BY date ASC
        """, (cutoff,)).fetchall()
    
    return {
        "daily_uploads": [{"date": r[0], "count": r[1]} for r in daily_uploads],
        "daily_duplicates": [{"date": r[0], "count": r[1]} for r in daily_duplicates],
        "daily_storage": [{"date": r[0], "bytes": r[1] or 0} for r in daily_storage],
    }


def get_file_type_distribution() -> List[Dict]:
    """
    Get distribution of file types in the repository.
    """
    with get_db() as conn:
        results = conn.execute("""
            SELECT file_type, COUNT(*) as count, SUM(file_size) as total_bytes
            FROM datasets
            GROUP BY file_type
            ORDER BY count DESC
            LIMIT 20
        """).fetchall()
    
    return [
        {
            "file_type": r[0] or "unknown",
            "count": r[1],
            "total_size_mb": (r[2] or 0) / (1024 ** 2),
        }
        for r in results
    ]


def get_user_activity(limit: int = 50) -> List[Dict]:
    """
    Get user activity metrics: uploads, scans, downloads.
    """
    with get_db() as conn:
        results = conn.execute("""
            SELECT 
                user_name,
                COUNT(*) as total_actions,
                SUM(CASE WHEN action = 'web_upload' THEN 1 ELSE 0 END) as uploads,
                SUM(CASE WHEN action = 'auto_scan' THEN 1 ELSE 0 END) as scans,
                MAX(created_at) as last_activity
            FROM history
            GROUP BY user_name
            ORDER BY total_actions DESC
            LIMIT ?
        """, (limit,)).fetchall()
    
    return [
        {
            "user_name": r[0],
            "total_actions": r[1],
            "uploads": r[2] or 0,
            "scans": r[3] or 0,
            "last_activity": r[4],
        }
        for r in results
    ]


def get_top_duplicates(limit: int = 20) -> List[Dict]:
    """
    Get the most frequently duplicated files.
    """
    with get_db() as conn:
        results = conn.execute("""
            SELECT 
                file_hash,
                file_name,
                file_size,
                COUNT(*) as occurrence_count,
                SUM(file_size) as total_wasted_space
            FROM datasets
            GROUP BY file_hash
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT ?
        """, (limit,)).fetchall()
    
    return [
        {
            "file_hash": r[0],
            "file_name": r[1],
            "file_size_mb": (r[2] or 0) / (1024 ** 2),
            "occurrences": r[3],
            "wasted_space_mb": ((r[4] or 0) * (r[3] - 1)) / (1024 ** 2),
        }
        for r in results
    ]


def get_system_health() -> Dict:
    """
    Get overall system health metrics.
    """
    with get_db() as conn:
        # Check database integrity
        try:
            conn.execute("PRAGMA integrity_check").fetchone()
            db_health = "healthy"
        except:
            db_health = "error"
        
        # Count pending alerts
        pending = conn.execute(
            "SELECT COUNT(*) as count FROM alerts WHERE is_read = 0"
        ).fetchone()["count"]
        
        # Recent errors
        errors = conn.execute("""
            SELECT COUNT(*) as count FROM scan_logs 
            WHERE error IS NOT NULL 
            AND created_at > datetime('now', '-24 hours')
        """).fetchone()["count"]
    
    return {
        "database_status": db_health,
        "pending_alerts": pending,
        "errors_24h": errors,
        "timestamp": datetime.utcnow().isoformat(),
    }
