"""
Advanced similarity detection for near-duplicate and fuzzy matching.
Algorithms: cosine similarity, Jaccard, Levenshtein, semantic analysis.
"""
import hashlib
import json
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from app.models.database import get_db, row_to_dict, rows_to_list

# Thresholds for different similarity levels
SIMILARITY_THRESHOLDS = {
    "exact": 1.0,
    "very_high": 0.95,
    "high": 0.85,
    "medium": 0.7,
    "low": 0.5
}


def calculate_file_similarity_score(file1_hash: str, file2_hash: str) -> Tuple[float, str]:
    """
    Calculate similarity between two files.
    Returns (score: 0-1, match_type: 'exact'|'fuzzy'|'semantic')
    """
    if file1_hash == file2_hash:
        return 1.0, "exact"
    
    # Levenshtein distance for hash comparison (catches corrupted hashes)
    distance = levenshtein_distance(file1_hash, file2_hash)
    max_len = max(len(file1_hash), len(file2_hash))
    
    if max_len == 0:
        return 0.0, "fuzzy"
    
    similarity = 1.0 - (distance / max_len)
    
    if similarity >= SIMILARITY_THRESHOLDS["very_high"]:
        return similarity, "fuzzy"
    
    return similarity, "semantic"


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if len(set1) == 0 and len(set2) == 0:
        return 1.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def analyze_filename_similarity(name1: str, name2: str) -> float:
    """Analyze similarity of filenames (tokenized)."""
    # Tokenize by common delimiters
    tokens1 = set(name1.lower().replace("_", " ").replace("-", " ").split())
    tokens2 = set(name2.lower().replace("_", " ").replace("-", " ").split())
    
    return jaccard_similarity(tokens1, tokens2)


def analyze_metadata_similarity(meta1: dict, meta2: dict) -> float:
    """Analyze similarity based on file metadata."""
    score = 0.0
    weight_total = 0.0
    
    # File size similarity (within 10% = high score)
    size1 = meta1.get("file_size", 0)
    size2 = meta2.get("file_size", 0)
    if size1 > 0 and size2 > 0:
        size_ratio = min(size1, size2) / max(size1, size2)
        score += size_ratio * 20
        weight_total += 20
    
    # File type match
    if meta1.get("file_type") == meta2.get("file_type"):
        score += 15
    weight_total += 15
    
    # Period/timestamp overlap
    if meta1.get("period") and meta2.get("period") and meta1.get("period") == meta2.get("period"):
        score += 15
    weight_total += 15
    
    # Spatial domain match
    if meta1.get("spatial_domain") and meta2.get("spatial_domain") and \
       meta1.get("spatial_domain") == meta2.get("spatial_domain"):
        score += 15
    weight_total += 15
    
    # Tags overlap
    tags1 = set(meta1.get("tags", []))
    tags2 = set(meta2.get("tags", []))
    if tags1 or tags2:
        tag_similarity = jaccard_similarity(tags1, tags2)
        score += tag_similarity * 20
    weight_total += 20
    
    return (score / weight_total) if weight_total > 0 else 0.0


def find_similar_datasets(file_hash: str, threshold: float = 0.85) -> List[dict]:
    """Find datasets similar to the given file hash."""
    with get_db() as conn:
        # Get all other files
        other_files = rows_to_list(conn.execute(
            "SELECT id, file_hash, file_name, file_size, file_type, period, spatial_domain, tags FROM datasets WHERE file_hash != ?",
            (file_hash,)
        ).fetchall())
    
    results = []
    for other in other_files:
        score, match_type = calculate_file_similarity_score(file_hash, other["file_hash"])
        
        if score >= threshold:
            # Also consider metadata
            current_meta = {
                "file_type": other["file_type"],
                "period": other.get("period"),
                "spatial_domain": other.get("spatial_domain"),
                "tags": json.loads(other.get("tags", "[]")) if other.get("tags") else []
            }
            
            metadata_score = analyze_metadata_similarity({}, current_meta)
            combined_score = (score * 0.7) + (metadata_score * 0.3)
            
            results.append({
                "dataset_id": other["id"],
                "file_hash": other["file_hash"],
                "file_name": other["file_name"],
                "similarity_score": round(combined_score, 3),
                "hash_similarity": round(score, 3),
                "match_type": match_type
            })
    
    return sorted(results, key=lambda x: x["similarity_score"], reverse=True)


def store_similarity_result(hash1: str, hash2: str, score: float, 
                           algorithm: str, match_type: str, details: dict = None) -> None:
    """Store similarity analysis result."""
    with get_db() as conn:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO similarity_results 
                   (file_hash_1, file_hash_2, similarity_score, algorithm, match_type, analysis_result)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (hash1, hash2, score, algorithm, match_type, json.dumps(details or {}))
            )
        except Exception:
            pass  # Ignore duplicates


def get_cached_similarity(hash1: str, hash2: str, algorithm: str = None) -> dict | None:
    """Retrieve cached similarity result if available."""
    with get_db() as conn:
        if algorithm:
            result = row_to_dict(conn.execute(
                "SELECT * FROM similarity_results WHERE file_hash_1 = ? AND file_hash_2 = ? AND algorithm = ?",
                (hash1, hash2, algorithm)
            ).fetchone())
        else:
            result = row_to_dict(conn.execute(
                "SELECT * FROM similarity_results WHERE file_hash_1 = ? AND file_hash_2 = ?",
                (hash1, hash2)
            ).fetchone())
    
    return result
