"""
Bandwidth optimization through compression and delta-sync.
Methods: gzip, bzip2, zstandard compression, delta sync for updates.
"""
import gzip
import bz2
import json
from pathlib import Path
from typing import Tuple
import zlib

from app.models.database import get_db, row_to_dict

COMPRESSION_METHODS = {
    "gzip": {"level": 6, "extension": ".gz"},
    "bzip2": {"level": 6, "extension": ".bz2"},
    "zstd": {"level": 6, "extension": ".zst"},
    "deflate": {"level": 6, "extension": ".deflate"}
}


def get_compression_ratio(original_size: int, compressed_size: int) -> float:
    """Calculate compression ratio (original / compressed)."""
    return original_size / compressed_size if compressed_size > 0 else 0


def compress_gzip(data: bytes, level: int = 6) -> bytes:
    """Compress data using gzip."""
    return gzip.compress(data, compresslevel=level)


def decompress_gzip(data: bytes) -> bytes:
    """Decompress gzip data."""
    return gzip.decompress(data)


def compress_bzip2(data: bytes, level: int = 6) -> bytes:
    """Compress data using bzip2."""
    return bz2.compress(data, compresslevel=level)


def decompress_bzip2(data: bytes) -> bytes:
    """Decompress bzip2 data."""
    return bz2.decompress(data)


def compress_deflate(data: bytes, level: int = 6) -> bytes:
    """Compress data using deflate."""
    return zlib.compress(data, level)


def decompress_deflate(data: bytes) -> bytes:
    """Decompress deflate data."""
    return zlib.decompress(data)


def compress_file(file_path: Path, method: str = "gzip") -> Tuple[Path, float]:
    """
    Compress a file and return compressed path and compression ratio.
    
    Returns: (compressed_file_path, compression_ratio)
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if method not in COMPRESSION_METHODS:
        method = "gzip"
    
    original_size = file_path.stat().st_size
    
    # Read original file
    with open(file_path, "rb") as f:
        data = f.read()
    
    # Compress
    if method == "gzip":
        compressed = compress_gzip(data, COMPRESSION_METHODS[method]["level"])
    elif method == "bzip2":
        compressed = compress_bzip2(data, COMPRESSION_METHODS[method]["level"])
    elif method == "deflate":
        compressed = compress_deflate(data, COMPRESSION_METHODS[method]["level"])
    else:
        compressed = data
    
    # Save compressed file
    compressed_path = file_path.parent / f"{file_path.name}{COMPRESSION_METHODS[method]['extension']}"
    with open(compressed_path, "wb") as f:
        f.write(compressed)
    
    compressed_size = compressed_path.stat().st_size
    ratio = get_compression_ratio(original_size, compressed_size)
    
    return compressed_path, ratio


def calculate_delta(old_data: bytes, new_data: bytes) -> bytes:
    """
    Create a delta (diff) between old and new data.
    For updates, only transmit the changes instead of full file.
    """
    # Simple approach: Find common prefix and suffix
    import difflib
    
    old_lines = old_data.decode(errors='ignore').splitlines(keepends=True)
    new_lines = new_data.decode(errors='ignore').splitlines(keepends=True)
    
    # Get diff
    differ = difflib.unified_diff(old_lines, new_lines, lineterm='')
    delta = ''.join(differ)
    
    return delta.encode()


def estimate_bandwidth_savings(original_size: int, compression_ratio: float) -> int:
    """Estimate bandwidth saved (in bytes) by compression."""
    if compression_ratio <= 1.0:
        return 0
    
    compressed_size = original_size / compression_ratio
    return int(original_size - compressed_size)


def record_bandwidth_optimization(dataset_id: str, method: str, 
                                  original_size: int, optimized_size: int,
                                  details: dict = None) -> None:
    """Record bandwidth optimization in database."""
    with get_db() as conn:
        ratio = original_size / optimized_size if optimized_size > 0 else 1.0
        conn.execute(
            """INSERT INTO bandwidth_optimization 
               (dataset_id, optimization_method, original_size, optimized_size, compression_ratio, method_details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dataset_id, method, original_size, optimized_size, ratio, json.dumps(details or {}))
        )


def get_bandwidth_stats(org_id: str = None, days: int = 30) -> dict:
    """Get bandwidth optimization statistics."""
    with get_db() as conn:
        if org_id:
            query = """
                SELECT 
                    COUNT(*) as total_optimizations,
                    SUM(original_size) as total_original,
                    SUM(optimized_size) as total_optimized,
                    AVG(compression_ratio) as avg_compression_ratio,
                    optimization_method
                FROM bandwidth_optimization bo
                JOIN datasets d ON bo.dataset_id = d.id
                WHERE d.organization_id = ?
                AND bo.applied_at > datetime('now', '-' || ? || ' days')
                GROUP BY optimization_method
            """
            results = conn.execute(query, (org_id, days)).fetchall()
        else:
            query = """
                SELECT 
                    COUNT(*) as total_optimizations,
                    SUM(original_size) as total_original,
                    SUM(optimized_size) as total_optimized,
                    AVG(compression_ratio) as avg_compression_ratio,
                    optimization_method
                FROM bandwidth_optimization
                WHERE applied_at > datetime('now', '-' || ? || ' days')
                GROUP BY optimization_method
            """
            results = conn.execute(query, (days,)).fetchall()
        
        stats = {}
        total_saved = 0
        for row in results:
            method = row[4]
            original = row[1] or 0
            optimized = row[2] or 0
            saved = original - optimized
            total_saved += saved
            
            stats[method] = {
                "count": row[0],
                "original_bytes": original,
                "optimized_bytes": optimized,
                "bytes_saved": saved,
                "avg_compression_ratio": round(row[3], 2) if row[3] else 1.0
            }
        
        stats["total"] = {
            "total_bytes_saved": total_saved,
            "percentage_saved": (total_saved / sum(s.get("original_bytes", 0) for s in stats.values()) * 100) 
                                if any(s.get("original_bytes") for s in stats.values()) else 0
        }
    
    return stats


def recommend_compression_method(original_size: int, file_type: str) -> str:
    """Recommend best compression method based on file type and size."""
    # Small files: minimal compression overhead, gzip is fine
    if original_size < 1024 * 1024:  # < 1 MB
        return "gzip"
    
    # Large text files: bzip2 better compression
    if file_type in ["csv", "json", "xml", "txt"]:
        return "bzip2"
    
    # Binary files: gzip fast, good ratio
    if file_type in ["pdf", "zip", "tar"]:
        return "gzip"
    
    # Images/Media: usually pre-compressed, gzip won't help much
    if file_type in ["jpg", "png", "mp4", "mp3"]:
        return "none"
    
    # Default
    return "gzip"
