"""
DatasetService — all database operations for datasets, history, alerts, scan_logs.
Returns plain dicts; no ORM objects leaked to the API layer.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.database import get_db, row_to_dict, rows_to_list


# ─────────────────────────── Dataset CRUD ────────────────────────────────────

class DatasetService:

    @staticmethod
    def get_all(limit: int = 200, offset: int = 0) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM datasets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def get_by_id(dataset_id: str) -> dict | None:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        return row_to_dict(row)

    @staticmethod
    def get_by_hash(file_hash: str) -> dict | None:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM datasets WHERE file_hash = ?", (file_hash,)
            ).fetchone()
        return row_to_dict(row)

    @staticmethod
    def exists(file_hash: str) -> bool:
        with get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM datasets WHERE file_hash = ? LIMIT 1", (file_hash,)
            ).fetchone()
        return row is not None

    @staticmethod
    def create(
        file_hash: str,
        file_name: str,
        file_size: int,
        file_path: str,
        file_type: str = "",
        user_name: str = "System",
        period: str | None = None,
        spatial_domain: str | None = None,
        attributes: dict | None = None,
        description: str | None = None,
    ) -> dict:
        attrs_json = json.dumps(attributes) if attributes else None
        with get_db() as conn:
            conn.execute(
                """INSERT INTO datasets
                   (file_hash, file_name, file_size, file_path, file_type,
                    user_name, period, spatial_domain, attributes, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_hash, file_name, file_size, file_path, file_type,
                 user_name, period, spatial_domain, attrs_json, description),
            )
            row = conn.execute(
                "SELECT * FROM datasets WHERE file_hash = ?", (file_hash,)
            ).fetchone()
        return row_to_dict(row)  # type: ignore[return-value]

    @staticmethod
    def search(query: str, limit: int = 100) -> list[dict]:
        pattern = f"%{query}%"
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM datasets
                   WHERE file_name LIKE ?
                      OR spatial_domain LIKE ?
                      OR period LIKE ?
                      OR description LIKE ?
                      OR file_type LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (pattern, pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def search_by_name(file_name: str, limit: int = 100) -> list[dict]:
        """Search files by name only."""
        pattern = f"%{file_name}%"
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM datasets
                   WHERE file_name LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def search_by_location(file_path: str, limit: int = 100) -> list[dict]:
        """Search files by location/path."""
        pattern = f"%{file_path}%"
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM datasets
                   WHERE file_path LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def filter_by_type(file_type: str, limit: int = 100) -> list[dict]:
        """Filter files by type/extension."""
        # Ensure file_type starts with a dot or add it
        if not file_type.startswith("."):
            file_type = f".{file_type}"
        pattern = f"%{file_type}%"
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM datasets
                   WHERE file_type LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def filter_by_size_range(min_size: int = 0, max_size: int = None, limit: int = 100) -> list[dict]:
        """Filter files by size range (in bytes)."""
        if max_size is None:
            max_size = float('inf')
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM datasets
                   WHERE file_size >= ? AND file_size <= ?
                   ORDER BY file_size DESC, created_at DESC
                   LIMIT ?""",
                (min_size, max_size if max_size != float('inf') else 9999999999, limit),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def filter_by_date_range(start_date: str = None, end_date: str = None, limit: int = 100) -> list[dict]:
        """Filter files by creation date range (ISO format: YYYY-MM-DD)."""
        with get_db() as conn:
            if start_date and end_date:
                rows = conn.execute(
                    """SELECT * FROM datasets
                       WHERE created_at >= ? AND created_at < ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (f"{start_date} 00:00:00", f"{end_date} 23:59:59", limit),
                ).fetchall()
            elif start_date:
                rows = conn.execute(
                    """SELECT * FROM datasets
                       WHERE created_at >= ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (f"{start_date} 00:00:00", limit),
                ).fetchall()
            elif end_date:
                rows = conn.execute(
                    """SELECT * FROM datasets
                       WHERE created_at <= ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (f"{end_date} 23:59:59", limit),
                ).fetchall()
            else:
                rows = []
        return rows_to_list(rows)

    @staticmethod
    def advanced_search(
        query: str = None,
        file_name: str = None,
        file_path: str = None,
        file_type: str = None,
        min_size: int = None,
        max_size: int = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> list[dict]:
        """Advanced search with multiple filters combined."""
        conditions = []
        params = []

        if query:
            pattern = f"%{query}%"
            conditions.append(
                "(file_name LIKE ? OR spatial_domain LIKE ? OR period LIKE ? OR description LIKE ? OR file_type LIKE ?)"
            )
            params.extend([pattern, pattern, pattern, pattern, pattern])

        if file_name:
            pattern = f"%{file_name}%"
            conditions.append("file_name LIKE ?")
            params.append(pattern)

        if file_path:
            pattern = f"%{file_path}%"
            conditions.append("file_path LIKE ?")
            params.append(pattern)

        if file_type:
            if not file_type.startswith("."):
                file_type = f".{file_type}"
            pattern = f"%{file_type}%"
            conditions.append("file_type LIKE ?")
            params.append(pattern)

        if min_size is not None:
            conditions.append("file_size >= ?")
            params.append(min_size)

        if max_size is not None:
            conditions.append("file_size <= ?")
            params.append(max_size)

        if start_date:
            conditions.append("created_at >= ?")
            params.append(f"{start_date} 00:00:00")

        if end_date:
            conditions.append("created_at <= ?")
            params.append(f"{end_date} 23:59:59")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""SELECT * FROM datasets
                  WHERE {where_clause}
                  ORDER BY created_at DESC
                  LIMIT ?"""
        params.append(limit)

        with get_db() as conn:
            rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def stats() -> dict[str, Any]:
        with get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
            total_size = conn.execute(
                "SELECT COALESCE(SUM(file_size), 0) FROM datasets"
            ).fetchone()[0]
            dup_count = conn.execute(
                "SELECT COUNT(*) FROM download_history WHERE status = 'duplicate_detected'"
            ).fetchone()[0]
            unique_domains = conn.execute(
                "SELECT COUNT(DISTINCT spatial_domain) FROM datasets WHERE spatial_domain IS NOT NULL AND spatial_domain != ''"
            ).fetchone()[0]
            file_types = conn.execute(
                """SELECT file_type, COUNT(*) as cnt FROM datasets
                   WHERE file_type IS NOT NULL AND file_type != ''
                   GROUP BY file_type ORDER BY cnt DESC LIMIT 10"""
            ).fetchall()
        return {
            "total_datasets": total,
            "total_size_bytes": total_size,
            "duplicate_prevention_count": dup_count,
            "unique_spatial_domains": unique_domains,
            "file_type_breakdown": rows_to_list(file_types),
        }


# ─────────────────────────── Download History ────────────────────────────────

class HistoryService:

    @staticmethod
    def log(
        dataset_id: str | None,
        user_name: str = "System",
        file_name: str = "",
        file_hash: str = "",
        action: str = "download_attempt",
        status: str = "success",
        ip_address: str = "",
        notes: str = "",
    ) -> None:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO download_history
                   (dataset_id, user_name, file_name, file_hash, action, status, ip_address, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (dataset_id, user_name, file_name, file_hash,
                 action, status, ip_address, notes),
            )

    @staticmethod
    def get_for_dataset(dataset_id: str, limit: int = 50) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM download_history
                   WHERE dataset_id = ?
                   ORDER BY attempt_timestamp DESC LIMIT ?""",
                (dataset_id, limit),
            ).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def get_recent(limit: int = 100) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM download_history ORDER BY attempt_timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows_to_list(rows)


# ─────────────────────────── Alerts ──────────────────────────────────────────

class AlertService:

    @staticmethod
    def create(
        title: str,
        message: str,
        alert_type: str = "duplicate",
        severity: str = "warning",
        file_name: str = "",
        file_hash: str = "",
        file_path: str = "",
        existing_dataset_id: str | None = None,
    ) -> dict:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO alerts
                   (alert_type, severity, title, message,
                    file_name, file_hash, file_path, existing_dataset_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (alert_type, severity, title, message,
                 file_name, file_hash, file_path, existing_dataset_id),
            )
            row = conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return row_to_dict(row)  # type: ignore[return-value]

    @staticmethod
    def get_all(unread_only: bool = False, limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM alerts"
        params: list[Any] = []
        if unread_only:
            sql += " WHERE is_read = 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with get_db() as conn:
            rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)

    @staticmethod
    def mark_read(alert_id: str) -> None:
        with get_db() as conn:
            conn.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))

    @staticmethod
    def mark_all_read() -> None:
        with get_db() as conn:
            conn.execute("UPDATE alerts SET is_read = 1")

    @staticmethod
    def unread_count() -> int:
        with get_db() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE is_read = 0"
            ).fetchone()[0]


# ─────────────────────────── Scan Logs ───────────────────────────────────────

class ScanLogService:

    @staticmethod
    def log(
        file_path: str,
        file_name: str = "",
        file_size: int = 0,
        file_hash: str = "",
        is_duplicate: bool = False,
        error: str = "",
    ) -> None:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO scan_logs
                   (file_path, file_name, file_size, file_hash, is_duplicate, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (file_path, file_name, file_size, file_hash,
                 1 if is_duplicate else 0, error or None),
            )

    @staticmethod
    def get_recent(limit: int = 100) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM scan_logs ORDER BY scanned_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return rows_to_list(rows)


# ───────────────────── Duplicate Detection & Management ──────────────────────

class DuplicateService:
    """
    Comprehensive duplicate detection and display service.
    Groups files by hash and displays all duplicate locations.
    """

    @staticmethod
    def get_duplicates_by_hash(file_hash: str) -> dict[str, Any]:
        """
        Get all files with the same hash (duplicates).
        Returns a structured duplicate group with metadata.
        """
        with get_db() as conn:
            # Get all files with this hash
            rows = conn.execute(
                """SELECT id, file_name, file_path, file_size, file_type, 
                          user_name, created_at, updated_at
                   FROM datasets
                   WHERE file_hash = ?
                   ORDER BY created_at ASC""",
                (file_hash,),
            ).fetchall()
        
        files = rows_to_list(rows)
        if not files:
            return None
        
        # Calculate storage saved
        if len(files) > 1:
            original_size = files[0].get("file_size", 0)
            storage_saved = original_size * (len(files) - 1)
        else:
            storage_saved = 0
        
        return {
            "file_hash": file_hash,
            "total_copies": len(files),
            "original_file": files[0] if files else None,
            "duplicate_locations": files[1:] if len(files) > 1 else [],
            "all_files": files,
            "total_storage_used": sum(f.get("file_size", 0) for f in files),
            "storage_saved_if_deduplicated": storage_saved,
        }

    @staticmethod
    def get_all_duplicates(limit: int = 100) -> list[dict]:
        """
        Get all duplicate groups in the system.
        Returns list of duplicate groups with all their locations.
        """
        with get_db() as conn:
            # Find all hashes with more than 1 file
            rows = conn.execute(
                """SELECT file_hash, COUNT(*) as copies
                   FROM datasets
                   GROUP BY file_hash
                   HAVING COUNT(*) > 1
                   ORDER BY copies DESC, file_hash
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        
        duplicate_hashes = rows_to_list(rows)
        
        results = []
        for dup_info in duplicate_hashes:
            file_hash = dup_info["file_hash"]
            dup_group = DuplicateService.get_duplicates_by_hash(file_hash)
            if dup_group:
                results.append(dup_group)
        
        return results

    @staticmethod
    def get_duplicates_for_file(dataset_id: str) -> dict[str, Any]:
        """
        Get all duplicates for a specific file by dataset ID.
        """
        with get_db() as conn:
            # Get the file's hash
            row = conn.execute(
                "SELECT file_hash FROM datasets WHERE id = ?", (dataset_id,)
            ).fetchone()
        
        if not row:
            return {"error": "File not found"}
        
        file_hash = row[0]
        return DuplicateService.get_duplicates_by_hash(file_hash)

    @staticmethod
    def find_duplicates_by_name(file_name: str) -> list[dict]:
        """
        Search for files with the same name (potential duplicates).
        """
        pattern = f"%{file_name}%"
        with get_db() as conn:
            rows = conn.execute(
                """SELECT file_hash, file_name, COUNT(*) as copies
                   FROM datasets
                   WHERE file_name LIKE ?
                   GROUP BY file_hash
                   ORDER BY copies DESC""",
                (pattern,),
            ).fetchall()
        
        name_matches = rows_to_list(rows)
        
        results = []
        for match in name_matches:
            if match["copies"] > 1:
                dup_group = DuplicateService.get_duplicates_by_hash(match["file_hash"])
                if dup_group:
                    results.append(dup_group)
        
        return results

    @staticmethod
    def get_duplicate_statistics() -> dict[str, Any]:
        """
        Get comprehensive duplicate statistics.
        """
        with get_db() as conn:
            total_files = conn.execute(
                "SELECT COUNT(*) FROM datasets"
            ).fetchone()[0]
            
            duplicate_files = conn.execute(
                """SELECT COUNT(*) FROM datasets d
                   WHERE file_hash IN (
                       SELECT file_hash FROM datasets 
                       GROUP BY file_hash HAVING COUNT(*) > 1
                   )"""
            ).fetchone()[0]
            
            unique_hashes = conn.execute(
                "SELECT COUNT(DISTINCT file_hash) FROM datasets"
            ).fetchone()[0]
            
            duplicate_groups = conn.execute(
                """SELECT COUNT(*) FROM (
                   SELECT file_hash FROM datasets
                   GROUP BY file_hash HAVING COUNT(*) > 1
                )"""
            ).fetchone()[0]
            
            total_size = conn.execute(
                "SELECT COALESCE(SUM(file_size), 0) FROM datasets"
            ).fetchone()[0]
            
            wasted_storage = conn.execute(
                """SELECT COALESCE(SUM(file_size * (copies - 1)), 0)
                   FROM (
                       SELECT file_size, COUNT(*) as copies
                       FROM datasets
                       GROUP BY file_hash
                       HAVING COUNT(*) > 1
                   )"""
            ).fetchone()[0]
        
        return {
            "total_files": total_files,
            "unique_files": unique_hashes,
            "duplicate_files": duplicate_files,
            "duplicate_groups": duplicate_groups,
            "duplicate_percentage": (duplicate_files / total_files * 100) if total_files > 0 else 0,
            "total_storage_bytes": total_size,
            "wasted_storage_bytes": wasted_storage,
            "wasted_storage_percentage": (wasted_storage / total_size * 100) if total_size > 0 else 0,
            "potential_savings_gb": round(wasted_storage / (1024**3), 2),
        }

    @staticmethod
    def scan_directory_for_duplicates(directory: str, recursive: bool = True, extensions: list = None) -> dict[str, Any]:
        """
        Scan a directory for files, compute hashes, and detect duplicates.
        Returns detailed duplicate groups with file locations.
        
        Args:
            directory: Path to scan
            recursive: Whether to scan subdirectories
            extensions: File extensions to include (None = all files)
        
        Returns:
            Dictionary with scan results including duplicate groups
        """
        from pathlib import Path
        import hashlib
        
        result = {
            "directory": directory,
            "scanned_files": 0,
            "duplicate_groups": [],
            "unique_files": 0,
            "errors": [],
            "total_size_bytes": 0,
            "duplicate_size_bytes": 0,
        }
        
        # Validate directory
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            result["errors"].append(f"Invalid directory: {directory}")
            return result
        
        # Hash map: hash -> list of files
        hash_map = {}
        
        def hash_file(filepath: Path) -> str | None:
            """Compute SHA256 hash of file."""
            try:
                sha256 = hashlib.sha256()
                with open(filepath, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        sha256.update(chunk)
                return sha256.hexdigest()
            except Exception as e:
                result["errors"].append(f"Error hashing {filepath}: {str(e)}")
                return None
        
        # Scan files
        try:
            if recursive:
                file_iter = dir_path.rglob('*')
            else:
                file_iter = dir_path.glob('*')
            
            for filepath in file_iter:
                if filepath.is_file():
                    # Skip hidden/system files
                    if filepath.name.startswith('.'):
                        continue
                    
                    # Filter by extension if specified
                    if extensions and filepath.suffix.lower() not in [e.lower() if e.startswith('.') else '.' + e for e in extensions]:
                        continue
                    
                    # Compute hash
                    file_hash = hash_file(filepath)
                    if not file_hash:
                        continue
                    
                    file_size = filepath.stat().st_size
                    result["total_size_bytes"] += file_size
                    
                    # Track file by hash
                    if file_hash not in hash_map:
                        hash_map[file_hash] = []
                    
                    hash_map[file_hash].append({
                        "file_name": filepath.name,
                        "file_location": str(filepath),
                        "file_size": file_size,
                        "file_type": filepath.suffix.lower(),
                        "created_at": filepath.stat().st_ctime,  # Creation time
                    })
                    
                    result["scanned_files"] += 1
        except Exception as e:
            result["errors"].append(f"Scan error: {str(e)}")
        
        # Group duplicates
        for file_hash, files in hash_map.items():
            if len(files) > 1:
                # This is a duplicate group
                total_size = sum(f["file_size"] for f in files)
                result["duplicate_size_bytes"] += total_size
                
                dup_group = {
                    "file_hash": file_hash,
                    "total_copies": len(files),
                    "file_locations": files,
                    "total_storage_used": total_size,
                    "storage_wasted": total_size - files[0]["file_size"],  # Original + waste
                }
                result["duplicate_groups"].append(dup_group)
            else:
                result["unique_files"] += 1
        
        # Sort by storage wasted
        result["duplicate_groups"].sort(key=lambda x: x["storage_wasted"], reverse=True)
        
        result["total_duplicates"] = len(result["duplicate_groups"])
        result["total_duplicate_files"] = sum(len(g["file_locations"]) for g in result["duplicate_groups"])
        
        return result

    @staticmethod
    def search_duplicates_by_filename(filename: str, search_paths: list = None) -> dict[str, Any]:
        """
        Search for all instances of a filename across system paths.
        Returns a deduplicated list of all found files with details.
        
        Args:
            filename: The filename to search for (e.g., "photo.jpg" or "*.jpg")
            search_paths: List of paths to search. If None, searches default locations.
        
        Returns:
            Dictionary with search results including duplicate details
        """
        from pathlib import Path
        import hashlib
        
        result = {
            "search_query": filename,
            "files_found": [],
            "duplicate_groups": [],
            "total_files": 0,
            "total_duplicates": 0,
            "total_size_bytes": 0,
            "errors": [],
        }
        
        # Default system search paths
        if not search_paths:
            search_paths = []
            # Windows common paths
            home = Path.home()
            search_paths = [
                home / "Downloads",
                home / "Documents",
                home / "Desktop",
                home / "Pictures",
                home / "Videos",
                home / "AppData" / "Local" / "Temp",
            ]
            # Add Linux/Mac paths if applicable
            if Path("/home").exists():
                search_paths.append(Path("/home"))
            if Path("/Users").exists():
                search_paths.append(Path("/Users"))
        else:
            search_paths = [Path(p) for p in search_paths]
        
        # Hash map for duplicate detection
        hash_map = {}
        found_files = {}  # filename_hash -> file details
        
        def hash_file(filepath: Path) -> str | None:
            """Compute SHA256 hash of file."""
            try:
                sha256 = hashlib.sha256()
                with open(filepath, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        sha256.update(chunk)
                return sha256.hexdigest()
            except Exception as e:
                result["errors"].append(f"Error hashing {filepath}: {str(e)}")
                return None
        
        # Search each path
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            try:
                # Search for matching filenames
                for filepath in search_path.rglob(filename):
                    if not filepath.is_file():
                        continue
                    
                    try:
                        # Get file details
                        file_hash = hash_file(filepath)
                        if not file_hash:
                            continue
                        
                        file_size = filepath.stat().st_size
                        file_type = filepath.suffix.lower() if filepath.suffix else ".unknown"
                        created_time = filepath.stat().st_ctime
                        
                        result["total_size_bytes"] += file_size
                        
                        file_detail = {
                            "file_name": filepath.name,
                            "file_type": file_type,
                            "file_size": file_size,
                            "file_location": str(filepath),
                            "file_hash": file_hash,
                            "created_at": created_time,
                            "status": "duplicate" if file_hash in hash_map else "unique",
                        }
                        
                        # Add to results
                        result["files_found"].append(file_detail)
                        result["total_files"] += 1
                        
                        # Track for duplicate detection
                        if file_hash not in hash_map:
                            hash_map[file_hash] = []
                        hash_map[file_hash].append(file_detail)
                        
                    except Exception as e:
                        result["errors"].append(f"Error processing {filepath}: {str(e)}")
            except Exception as e:
                result["errors"].append(f"Error searching {search_path}: {str(e)}")
        
        # Group duplicates
        for file_hash, files in hash_map.items():
            if len(files) > 1:
                # Update status to duplicate
                for f in files:
                    f["status"] = "duplicate"
                
                total_size = sum(f["file_size"] for f in files)
                result["total_duplicates"] += len(files)
                
                dup_group = {
                    "file_hash": file_hash,
                    "total_copies": len(files),
                    "file_name": files[0]["file_name"],
                    "file_type": files[0]["file_type"],
                    "files": files,
                    "total_storage_used": total_size,
                    "storage_wasted": total_size - files[0]["file_size"],
                }
                result["duplicate_groups"].append(dup_group)
        
        # Sort by storage wasted
        result["duplicate_groups"].sort(key=lambda x: x["storage_wasted"], reverse=True)
        
        return result

