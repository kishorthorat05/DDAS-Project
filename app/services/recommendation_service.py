"""
Recommendation engine for data reuse, suggestions, and smart recommendations.
Analyzes user behavior, file metadata, and similar datasets.
"""
import json
from typing import List, Dict
from datetime import datetime, timedelta

from app.models.database import get_db, row_to_dict, rows_to_list
from app.services import similarity_service

RECOMMENDATION_TYPES = {
    "duplicate": "File is an exact duplicate - can be reused instead of re-downloading",
    "similar": "Found similar files that might be relevant",
    "relevant_metadata": "Files with matching metadata (period, domain, etc.)",
    "trending": "Frequently accessed datasets similar to your requirement",
    "time_series": "Previous versions or related time-series data",
    "completion": "Files that complement your current dataset"
}


def generate_recommendations(user_id: str, org_id: str, file_hash: str,
                             file_name: str, file_type: str,
                             metadata: dict = None) -> List[Dict]:
    """
    Generate personalized recommendations for data reuse.
    Returns list of recommended datasets with reasoning.
    """
    recommendations = []
    
    with get_db() as conn:
        # 1. Check for exact/near duplicates
        similar_datasets = similarity_service.find_similar_datasets(file_hash, threshold=0.85)
        for sim in similar_datasets[:5]:  # Top 5
            rec_type = "duplicate" if sim["similarity_score"] > 0.99 else "similar"
            recommendations.append({
                "dataset_id": sim["dataset_id"],
                "recommendation_type": rec_type,
                "reason": RECOMMENDATION_TYPES.get(rec_type, ""),
                "confidence_score": sim["similarity_score"],
                "details": sim
            })
        
        # 2. Check for metadata matches
        if metadata:
            matching = rows_to_list(conn.execute(
                """SELECT id, file_name, file_hash, period, spatial_domain, tags 
                   FROM datasets
                   WHERE file_hash != ?
                   AND (period = ? OR spatial_domain = ?)
                   LIMIT 10""",
                (file_hash, metadata.get("period"), metadata.get("spatial_domain"))
            ).fetchall())
            
            for match in matching:
                # Check if not already recommended
                if not any(r["dataset_id"] == match["id"] for r in recommendations):
                    recommendations.append({
                        "dataset_id": match["id"],
                        "recommendation_type": "relevant_metadata",
                        "reason": RECOMMENDATION_TYPES["relevant_metadata"],
                        "confidence_score": 0.75,
                        "details": {
                            "file_name": match["file_name"],
                            "period": match["period"],
                            "spatial_domain": match["spatial_domain"]
                        }
                    })
        
        # 3. Trending datasets (frequently reused)
        trending = rows_to_list(conn.execute(
            """SELECT id, file_name, reuse_count, file_type 
               FROM datasets
               WHERE file_hash != ?
               AND reuse_count > 0
               AND file_type = ?
               ORDER BY reuse_count DESC
               LIMIT 5""",
            (file_hash, file_type)
        ).fetchall())
        
        for trend in trending:
            if not any(r["dataset_id"] == trend["id"] for r in recommendations):
                recommendations.append({
                    "dataset_id": trend["id"],
                    "recommendation_type": "trending",
                    "reason": f"Frequently reused ({trend['reuse_count']} times)",
                    "confidence_score": min(0.8, trend["reuse_count"] * 0.1),
                    "details": {
                        "file_name": trend["file_name"],
                        "reuse_count": trend["reuse_count"]
                    }
                })
    
    return recommendations


def get_personalized_recommendations(user_id: str, org_id: str, limit: int = 10) -> List[Dict]:
    """
    Get personalized recommendations for a user based on their history and preferences.
    """
    recommendations = []
    
    with get_db() as conn:
        # Get user's download history
        user_history = rows_to_list(conn.execute(
            """SELECT DISTINCT dataset_id, file_type FROM download_history
               WHERE user_id = ?
               ORDER BY attempt_timestamp DESC
               LIMIT 20""",
            (user_id,)
        ).fetchall())
        
        # For each file they've downloaded, get similar files
        for hist in user_history:
            if hist["dataset_id"]:
                dataset = row_to_dict(conn.execute(
                    "SELECT file_hash, file_name, file_type FROM datasets WHERE id = ?",
                    (hist["dataset_id"],)
                ).fetchone())
                
                if dataset:
                    similar = similarity_service.find_similar_datasets(
                        dataset["file_hash"], threshold=0.8
                    )
                    
                    for sim in similar[:3]:
                        if len(recommendations) < limit:
                            recommendations.append({
                                "dataset_id": sim["dataset_id"],
                                "recommendation_type": "similar",
                                "reason": "Similar to datasets you've used before",
                                "confidence_score": sim["similarity_score"] * 0.9,
                                "based_on": {
                                    "previous_file": dataset["file_name"],
                                    "similarity_score": sim["similarity_score"]
                                }
                            })
    
    return recommendations[:limit]


def store_recommendation(user_id: str, dataset_id: str, rec_type: str,
                        reason: str, confidence: float) -> None:
    """Store a recommendation in the database."""
    with get_db() as conn:
        try:
            conn.execute(
                """INSERT INTO reuse_recommendations 
                   (user_id, dataset_id, recommendation_type, reason, confidence_score)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, dataset_id, rec_type, reason, confidence)
            )
        except Exception:
            pass


def get_recommendation_stats(user_id: str = None, org_id: str = None) -> Dict:
    """Get statistics on recommendations."""
    with get_db() as conn:
        if user_id:
            query = """
                SELECT recommendation_type, COUNT(*) as count,
                       SUM(is_accepted) as accepted,
                       AVG(confidence_score) as avg_confidence
                FROM reuse_recommendations
                WHERE user_id = ?
                GROUP BY recommendation_type
            """
            results = conn.execute(query, (user_id,)).fetchall()
        else:
            query = """
                SELECT recommendation_type, COUNT(*) as count,
                       SUM(is_accepted) as accepted,
                       AVG(confidence_score) as avg_confidence
                FROM reuse_recommendations
                WHERE organization_id IN (
                    SELECT u.organization_id FROM users u WHERE u.organization_id = ?
                )
                GROUP BY recommendation_type
            """
            results = conn.execute(query, (org_id,)).fetchall() if org_id else []
        
        stats = {}
        total_recs = 0
        total_accepted = 0
        
        for row in results:
            rec_type = row[0]
            count = row[1] or 0
            accepted = row[2] or 0
            avg_conf = row[3] or 0
            
            stats[rec_type] = {
                "total": count,
                "accepted": accepted,
                "acceptance_rate": (accepted / count * 100) if count > 0 else 0,
                "avg_confidence": round(avg_conf, 3)
            }
            total_recs += count
            total_accepted += accepted
        
        stats["overall"] = {
            "total_recommendations": total_recs,
            "total_accepted": total_accepted,
            "overall_acceptance_rate": (total_accepted / total_recs * 100) if total_recs > 0 else 0
        }
    
    return stats


def mark_recommendation_accepted(recommendation_id: str) -> None:
    """Mark a recommendation as accepted/acted upon."""
    with get_db() as conn:
        conn.execute(
            "UPDATE reuse_recommendations SET is_accepted = 1 WHERE id = ?",
            (recommendation_id,)
        )


def mark_recommendation_rejected(recommendation_id: str) -> None:
    """Mark a recommendation as rejected."""
    with get_db() as conn:
        conn.execute(
            "UPDATE reuse_recommendations SET is_rejected = 1 WHERE id = ?",
            (recommendation_id,)
        )
