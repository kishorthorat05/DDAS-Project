"""
Export service for creating zip archives of scanned directories and reports.
Handles duplicate detection results export and batch downloads.
"""
import os
import shutil
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from app.models.database import get_db, rows_to_list
from config.settings import get_config

Config = get_config()


def create_scan_report(scan_results: Dict) -> Dict:
    """
    Create a comprehensive scan report from scan results.
    Returns dict with summary and detailed findings.
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_files_scanned": scan_results.get("scanned", 0),
            "duplicates_found": scan_results.get("duplicates", 0),
            "errors": scan_results.get("errors", 0),
            "directory_scanned": scan_results.get("directory", ""),
            "duplication_rate": (
                (scan_results.get("duplicates", 0) / max(scan_results.get("scanned", 1), 1)) * 100
            )
        },
        "details": scan_results
    }


def create_zip_export(scan_results: Dict, include_metadata: bool = True) -> str:
    """
    Create a ZIP export of scan results, duplicates list, and metadata.
    Returns path to created zip file.
    """
    export_dir = Config.UPLOAD_FOLDER / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    zip_path = export_dir / f"scan_export_{timestamp}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add scan report
        report = create_scan_report(scan_results)
        zf.writestr("SCAN_REPORT.json", json.dumps(report, indent=2))
        
        # Add duplicates list
        if include_metadata:
            duplicates_list = get_duplicates_summary()
            zf.writestr("DUPLICATES_SUMMARY.json", json.dumps(duplicates_list, indent=2))
        
        # Add README with instructions
        readme = """# DDAS Scan Export

This export contains scan results and duplicate detection data.

## Contents
- SCAN_REPORT.json: Summary of the scan including total files, duplicates found, and error count
- DUPLICATES_SUMMARY.json: List of duplicate file groups detected in the system

## Data Download Duplication Alert System (DDAS)
For more information, visit the DDAS dashboard.
"""
        zf.writestr("README.md", readme)
    
    return str(zip_path)


def get_duplicates_summary() -> List[Dict]:
    """
    Get a summary of all duplicate file groups in the system.
    Returns list of duplicate groups with metadata.
    """
    with get_db() as conn:
        # Get all datasets that have been flagged as duplicates via alerts
        rows = conn.execute("""
            SELECT DISTINCT d.id, d.file_hash, d.file_name, d.file_size, 
                   d.download_timestamp, d.user_name, d.file_type,
                   CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as is_duplicate
            FROM datasets d
            LEFT JOIN alerts a ON d.file_hash = a.file_hash AND a.alert_type = 'duplicate'
            WHERE a.id IS NOT NULL
            ORDER BY d.download_timestamp DESC
            LIMIT 1000
        """).fetchall()
        
        return rows_to_list(rows)


def export_filtered_datasets(filter_criteria: Dict) -> str:
    """
    Export datasets matching filter criteria (by date, user, file type, etc).
    Returns path to created zip file.
    """
    export_dir = Config.UPLOAD_FOLDER / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    zip_path = export_dir / f"datasets_export_{timestamp}.zip"
    
    query = "SELECT * FROM datasets WHERE 1=1"
    params = []
    
    # Build query based on filter_criteria
    if filter_criteria.get("start_date"):
        query += " AND download_timestamp >= ?"
        params.append(filter_criteria["start_date"])
    if filter_criteria.get("end_date"):
        query += " AND download_timestamp <= ?"
        params.append(filter_criteria["end_date"])
    if filter_criteria.get("file_type"):
        query += " AND file_type = ?"
        params.append(filter_criteria["file_type"])
    if filter_criteria.get("user_name"):
        query += " AND user_name = ?"
        params.append(filter_criteria["user_name"])
    # Note: is_duplicate filter is based on alerts available
    if filter_criteria.get("is_duplicate") is not None:
        if int(filter_criteria["is_duplicate"]) == 1:
            query += " AND file_hash IN (SELECT DISTINCT file_hash FROM alerts WHERE alert_type = 'duplicate')"
        else:
            query += " AND file_hash NOT IN (SELECT DISTINCT file_hash FROM alerts WHERE alert_type = 'duplicate')"
    
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        datasets = rows_to_list(rows)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add datasets metadata
        zf.writestr("datasets_metadata.json", json.dumps(datasets, indent=2, default=str))
        
        # Add README
        readme = f"""# Filtered Datasets Export

Export Date: {datetime.utcnow().isoformat()}
Total Datasets: {len(datasets)}

## Filter Criteria Used
{json.dumps(filter_criteria, indent=2)}

## Columns
- id: Dataset ID
- file_hash: SHA-256 hash
- file_name: Original filename
- file_size: Size in bytes
- download_timestamp: When file was registered
- file_type: File extension
- user_name: User who uploaded/registered it
"""
        zf.writestr("README.md", readme)
    
    return str(zip_path)


def cleanup_old_exports(days: int = 7) -> int:
    """
    Remove export zip files older than specified days.
    Returns count of deleted files.
    """
    export_dir = Config.UPLOAD_FOLDER / "exports"
    if not export_dir.exists():
        return 0
    
    cutoff_time = datetime.utcnow().timestamp() - (days * 24 * 3600)
    deleted_count = 0
    
    for file_path in export_dir.glob("*.zip"):
        if file_path.stat().st_mtime < cutoff_time:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception:
                pass
    
    return deleted_count
