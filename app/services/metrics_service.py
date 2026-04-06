"""
Performance metrics and analytics dashboard.
Tracks: duplicate detection rate, storage saved, bandwidth saved, system performance.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List
from app.models.database import get_db, row_to_dict, rows_to_list

def calculate_daily_metrics(org_id: str = None) -> None:
    """Calculate and store daily performance metrics."""
    with get_db() as conn:
        # Get today's date
        today = datetime.utcnow().date().isoformat()
        
        # Determine scope
        if org_id:
            conditions = "AND d.organization_id = ?"
            params = [org_id]
        else:
            conditions = ""
            params = []
        
        # Count uploads
        total_uploads = conn.execute(
            f"SELECT COUNT(*) FROM download_history WHERE DATE(attempt_timestamp) = ? {conditions}",
            [today] + params
        ).fetchone()[0]
        
        # Count duplicates found
        duplicates_found = conn.execute(
            f"SELECT COUNT(*) FROM download_history WHERE DATE(attempt_timestamp) = ? AND status = 'duplicate_detected' {conditions}",
            [today] + params
        ).fetchone()[0]
        
        # Calculate duplicate rate
        duplicate_rate = (duplicates_found / total_uploads * 100) if total_uploads > 0 else 0
        
        # Calculate storage saved (via deduplication)
        storage_saved = conn.execute(
            f"""SELECT SUM(dh.bandwidth_saved) FROM download_history dh
               JOIN datasets d ON dh.dataset_id = d.id
               WHERE DATE(dh.attempt_timestamp) = ? AND dh.status = 'duplicate_detected' {conditions}""",
            [today] + params
        ).fetchone()[0] or 0
        
        # Calculate bandwidth saved (via reuse and compression)
        bandwidth_saved = conn.execute(
            f"""SELECT COALESCE(SUM(bandwidth_saved), 0) FROM download_history
               WHERE DATE(attempt_timestamp) = ? AND is_reuse = 1 {conditions}""",
            [today] + params
        ).fetchone()[0]
        
        # Average file size
        avg_file_size = conn.execute(
            f"""SELECT AVG(file_size) FROM datasets
               WHERE DATE(created_at) = ? {conditions}""",
            [today] + params
        ).fetchone()[0] or 0
        
        # Total datasets
        total_datasets = conn.execute(
            f"SELECT COUNT(*) FROM datasets WHERE organization_id = ?" if org_id else "SELECT COUNT(*) FROM datasets"
        ).fetchone()[0]
        
        # Unique users
        unique_users = conn.execute(
            f"""SELECT COUNT(DISTINCT user_id) FROM download_history
               WHERE DATE(attempt_timestamp) = ? {conditions}""",
            [today] + params
        ).fetchone()[0]
        
        # Reuse percentage
        reused_count = conn.execute(
            f"""SELECT COUNT(*) FROM download_history
               WHERE DATE(attempt_timestamp) = ? AND is_reuse = 1 {conditions}""",
            [today] + params
        ).fetchone()[0]
        
        reuse_percentage = (reused_count / total_uploads * 100) if total_uploads > 0 else 0
        
        # Store metrics
        conn.execute(
            """INSERT OR REPLACE INTO performance_metrics
               (organization_id, metric_date, total_uploads, total_duplicates_found,
                duplicate_rate_percent, storage_saved_bytes, bandwidth_saved_bytes,
                average_file_size, total_datasets, unique_users, reuse_percentage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (org_id, today, total_uploads, duplicates_found, duplicate_rate,
             storage_saved, bandwidth_saved, int(avg_file_size),
             total_datasets, unique_users, reuse_percentage)
        )


def get_metrics_summary(org_id: str = None, days: int = 30) -> Dict:
    """Get aggregated metrics summary for a period."""
    with get_db() as conn:
        start_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        
        if org_id:
            query = """
                SELECT 
                    SUM(total_uploads) as total_uploads,
                    SUM(total_duplicates_found) as total_duplicates,
                    AVG(duplicate_rate_percent) as avg_duplicate_rate,
                    SUM(storage_saved_bytes) as total_storage_saved,
                    SUM(bandwidth_saved_bytes) as total_bandwidth_saved,
                    AVG(average_file_size) as avg_file_size,
                    MAX(total_datasets) as total_datasets,
                    SUM(unique_users) as total_unique_users,
                    AVG(reuse_percentage) as avg_reuse_percentage
                FROM performance_metrics
                WHERE organization_id = ? AND metric_date >= ?
            """
            result = row_to_dict(conn.execute(query, (org_id, start_date)).fetchone())
        else:
            query = """
                SELECT 
                    SUM(total_uploads) as total_uploads,
                    SUM(total_duplicates_found) as total_duplicates,
                    AVG(duplicate_rate_percent) as avg_duplicate_rate,
                    SUM(storage_saved_bytes) as total_storage_saved,
                    SUM(bandwidth_saved_bytes) as total_bandwidth_saved,
                    AVG(average_file_size) as avg_file_size,
                    MAX(total_datasets) as total_datasets,
                    SUM(unique_users) as total_unique_users,
                    AVG(reuse_percentage) as avg_reuse_percentage
                FROM performance_metrics
                WHERE metric_date >= ?
            """
            result = row_to_dict(conn.execute(query, (start_date,)).fetchone())
    
    # Format results
    if not result:
        return {}
    
    return {
        "period_days": days,
        "total_uploads": result.get("total_uploads") or 0,
        "total_duplicates_detected": result.get("total_duplicates") or 0,
        "average_duplicate_rate_percent": round(result.get("avg_duplicate_rate") or 0, 2),
        "total_storage_saved_gb": round((result.get("total_storage_saved") or 0) / (1024**3), 2),
        "total_bandwidth_saved_gb": round((result.get("total_bandwidth_saved") or 0) / (1024**3), 2),
        "average_file_size_mb": round((result.get("avg_file_size") or 0) / (1024**2), 2),
        "total_datasets": result.get("total_datasets") or 0,
        "unique_users": result.get("total_unique_users") or 0,
        "average_reuse_percentage": round(result.get("avg_reuse_percentage") or 0, 2)
    }


def get_metrics_timeline(org_id: str = None, days: int = 30) -> List[Dict]:
    """Get daily metrics timeline for dashboard charting."""
    with get_db() as conn:
        start_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        
        if org_id:
            query = """
                SELECT metric_date, total_uploads, total_duplicates_found,
                       duplicate_rate_percent, storage_saved_bytes, 
                       bandwidth_saved_bytes, reuse_percentage
                FROM performance_metrics
                WHERE organization_id = ? AND metric_date >= ?
                ORDER BY metric_date ASC
            """
            results = rows_to_list(conn.execute(query, (org_id, start_date)).fetchall())
        else:
            query = """
                SELECT metric_date, total_uploads, total_duplicates_found,
                       duplicate_rate_percent, storage_saved_bytes,
                       bandwidth_saved_bytes, reuse_percentage
                FROM performance_metrics
                WHERE metric_date >= ?
                ORDER BY metric_date ASC
            """
            results = rows_to_list(conn.execute(query, (start_date,)).fetchall())
    
    # Transform for charting
    timeline = []
    for row in results:
        timeline.append({
            "date": row["metric_date"],
            "uploads": row["total_uploads"],
            "duplicates": row["total_duplicates_found"],
            "duplicate_rate_percent": round(row["duplicate_rate_percent"] or 0, 2),
            "storage_saved_gb": round((row["storage_saved_bytes"] or 0) / (1024**3), 3),
            "bandwidth_saved_gb": round((row["bandwidth_saved_bytes"] or 0) / (1024**3), 3),
            "reuse_percentage": round(row["reuse_percentage"] or 0, 2)
        })
    
    return timeline


def get_top_datasets(org_id: str = None, limit: int = 10) -> List[Dict]:
    """Get most frequently reused datasets."""
    with get_db() as conn:
        if org_id:
            query = """
                SELECT id, file_name, file_size, reuse_count, quality_score,
                       file_type, period, spatial_domain
                FROM datasets
                WHERE organization_id = ?
                ORDER BY reuse_count DESC
                LIMIT ?
            """
            results = rows_to_list(conn.execute(query, (org_id, limit)).fetchall())
        else:
            query = """
                SELECT id, file_name, file_size, reuse_count, quality_score,
                       file_type, period, spatial_domain
                FROM datasets
                ORDER BY reuse_count DESC
                LIMIT ?
            """
            results = rows_to_list(conn.execute(query, (limit,)).fetchall())
    
    datasets = []
    for ds in results:
        datasets.append({
            "dataset_id": ds["id"],
            "file_name": ds["file_name"],
            "file_size_mb": round(ds["file_size"] / (1024**2), 2),
            "reuse_count": ds["reuse_count"],
            "quality_score": round(ds["quality_score"] or 0, 2),
            "file_type": ds["file_type"],
            "period": ds["period"],
            "spatial_domain": ds["spatial_domain"]
        })
    
    return datasets


def get_user_activity_stats(org_id: str, user_id: str = None, days: int = 30) -> Dict:
    """Get user activity statistics."""
    with get_db() as conn:
        start_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        
        if user_id:
            query = """
                SELECT activity_type, COUNT(*) as count
                FROM user_activity
                WHERE user_id = ? AND organization_id = ? AND DATE(created_at) >= ?
                GROUP BY activity_type
            """
            results = conn.execute(query, (user_id, org_id, start_date)).fetchall()
        else:
            query = """
                SELECT activity_type, COUNT(*) as count
                FROM user_activity
                WHERE organization_id = ? AND DATE(created_at) >= ?
                GROUP BY activity_type
            """
            results = conn.execute(query, (org_id, start_date)).fetchall()
        
        stats = {}
        for row in results:
            stats[row[0]] = row[1]
    
    return stats


def export_metrics_report(org_id: str = None, format_type: str = "json") -> str:
    """Export metrics as a report."""
    summary = get_metrics_summary(org_id)
    timeline = get_metrics_timeline(org_id)
    top_datasets = get_top_datasets(org_id)
    
    report = {
        "exported_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "timeline": timeline,
        "top_datasets": top_datasets
    }
    
    if format_type == "json":
        return json.dumps(report, indent=2)
    elif format_type == "csv":
        # Convert to CSV format
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)
        return output.getvalue()
    
    return str(report)
