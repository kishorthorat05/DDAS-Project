"""
API blueprints for DDAS.
All endpoints return JSON. Auth via JWT Bearer token.
"""
import os
import uuid
from datetime import datetime
from pathlib import Path

import requests
from flask import Blueprint, g, jsonify, request, send_from_directory

from app.services.ai_service import (
    chat as ai_chat,
    execute_chat_action,
    get_file_insights,
    is_api_configured,
)
from app.services.dataset_service import (
    AlertService, DatasetService, HistoryService, ScanLogService, DuplicateService
)
from app.services.monitor_service import manual_scan, monitor_status, start_monitor, stop_monitor
from app.services.export_service import create_zip_export, export_filtered_datasets, cleanup_old_exports
from app.services.analytics_service import (
    get_dashboard_stats, get_timeline_data, get_file_type_distribution,
    get_user_activity, get_top_duplicates, get_system_health
)
from app.utils.security import (
    hash_file, hash_bytes,
    is_allowed_extension, is_safe_url,
    jwt_required, rate_limit, require_auth, require_role,
    sanitize_filename, sanitize_search_query, sanitize_str,
    hash_password, verify_password, create_access_token, create_refresh_token,
)
from app.models.database import get_db, row_to_dict
from config.settings import get_config


def _config():
    return get_config()

# ─────────────────────────── Blueprints ──────────────────────────────────────

auth_bp   = Blueprint("auth",    __name__, url_prefix="/api/auth")
data_bp   = Blueprint("data",    __name__, url_prefix="/api")
upload_bp = Blueprint("upload",  __name__, url_prefix="/api")
alert_bp  = Blueprint("alerts",  __name__, url_prefix="/api")
monitor_bp= Blueprint("monitor", __name__, url_prefix="/api")
ai_bp     = Blueprint("ai",      __name__, url_prefix="/api/ai")
analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")
export_bp = Blueprint("export",  __name__, url_prefix="/api/export")
duplicates_bp = Blueprint("duplicates", __name__, url_prefix="/api/duplicates")

# ─────────────────────────── Helpers ─────────────────────────────────────────

def _ok(data: dict | list | None = None, **kwargs) -> tuple:
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload), 200


def _created(data: dict | None = None, **kwargs) -> tuple:
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload), 201


def _err(message: str, code: int = 400, error_code: str = "") -> tuple:
    return jsonify({"success": False, "error": message, "code": error_code or "ERROR"}), code


def _get_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


# ═════════════════════════════════════════════════════════════════════════════
# AUTH
# ═════════════════════════════════════════════════════════════════════════════

@auth_bp.post("/register")
@rate_limit(max_requests=5, window_seconds=3600)
def register():
    body = request.get_json(silent=True) or {}
    username = sanitize_str(body.get("username", ""), 50)
    password = body.get("password", "")
    email = sanitize_str(body.get("email", ""), 200)

    if not username or len(username) < 3:
        return _err("Username must be at least 3 characters.")
    if len(password) < 8:
        return _err("Password must be at least 8 characters.")

    pw_hash = hash_password(password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email or None, pw_hash),
            )
            user = row_to_dict(conn.execute(
                "SELECT id, username, email, role FROM users WHERE username = ?", (username,)
            ).fetchone())
    except Exception:
        return _err("Username already exists.", 409, "CONFLICT")

    token = create_access_token({"sub": user["id"], "username": user["username"], "role": user["role"]})
    return _created({"user": user, "access_token": token})


@auth_bp.post("/login")
@rate_limit(max_requests=10, window_seconds=300)
def login():
    body = request.get_json(silent=True) or {}
    username = sanitize_str(body.get("username", ""), 50)
    password = body.get("password", "")

    with get_db() as conn:
        user = row_to_dict(conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
        ).fetchone())

    if not user or not verify_password(password, user["password_hash"]):
        return _err("Invalid credentials.", 401, "INVALID_CREDENTIALS")

    token = create_access_token({"sub": user["id"], "username": user["username"], "role": user["role"]})
    refresh = create_refresh_token(user["id"])
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return _ok({"user": safe_user, "access_token": token, "refresh_token": refresh})


@auth_bp.get("/me")
@require_auth
def me():
    uid = g.current_user.get("sub")
    with get_db() as conn:
        user = row_to_dict(conn.execute(
            "SELECT id, username, email, role, created_at FROM users WHERE id = ?", (uid,)
        ).fetchone())
    if not user:
        return _err("User not found.", 404)
    return _ok(user)


# ═════════════════════════════════════════════════════════════════════════════
# DATASETS
# ═════════════════════════════════════════════════════════════════════════════

@data_bp.get("/datasets")
@require_auth
def get_datasets():
    limit  = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))
    return _ok(DatasetService.get_all(limit, offset))


@data_bp.get("/datasets/search")
@require_auth
def search_datasets():
    q = sanitize_search_query(request.args.get("q", ""))
    if not q:
        return _ok(DatasetService.get_all(limit=100))
    return _ok(DatasetService.search(q))


@data_bp.get("/datasets/search/name")
@require_auth
def search_by_name():
    """Search files by name only."""
    file_name = sanitize_search_query(request.args.get("name", ""))
    limit = int(request.args.get("limit", 100))
    if not file_name:
        return _err("Search name parameter is required.", 400)
    return _ok(DatasetService.search_by_name(file_name, limit=limit))


@data_bp.get("/datasets/search/location")
@require_auth
def search_by_location():
    """Search files by location/path."""
    file_path = sanitize_search_query(request.args.get("path", ""))
    limit = int(request.args.get("limit", 100))
    if not file_path:
        return _err("Search path parameter is required.", 400)
    return _ok(DatasetService.search_by_location(file_path, limit=limit))


@data_bp.get("/datasets/filter/type")
@require_auth
def filter_by_type():
    """Filter files by type/extension."""
    file_type = sanitize_search_query(request.args.get("type", ""))
    limit = int(request.args.get("limit", 100))
    if not file_type:
        return _err("File type parameter is required.", 400)
    return _ok(DatasetService.filter_by_type(file_type, limit=limit))


@data_bp.get("/datasets/filter/size")
@require_auth
def filter_by_size():
    """Filter files by size range (in bytes)."""
    try:
        min_size = int(request.args.get("min", 0))
        max_size_str = request.args.get("max")
        max_size = int(max_size_str) if max_size_str else None
        limit = int(request.args.get("limit", 100))
    except ValueError:
        return _err("Size parameters must be integers.", 400)
    
    if min_size < 0 or (max_size is not None and max_size < 0):
        return _err("Size values must be non-negative.", 400)
    if max_size is not None and min_size > max_size:
        return _err("Min size cannot be greater than max size.", 400)
    
    return _ok(DatasetService.filter_by_size_range(min_size, max_size, limit=limit))


@data_bp.get("/datasets/filter/date")
@require_auth
def filter_by_date():
    """Filter files by creation date range (ISO format: YYYY-MM-DD)."""
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    limit = int(request.args.get("limit", 100))
    
    if not start_date and not end_date:
        return _err("At least one of 'start' or 'end' date is required.", 400)
    
    return _ok(DatasetService.filter_by_date_range(start_date, end_date, limit=limit))


@data_bp.post("/datasets/advanced-search")
@require_auth
def advanced_search():
    """Advanced search with multiple filters combined."""
    body = request.get_json(silent=True) or {}
    
    query = body.get("query")
    file_name = body.get("file_name")
    file_path = body.get("file_path")
    file_type = body.get("file_type")
    min_size = body.get("min_size")
    max_size = body.get("max_size")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    limit = int(body.get("limit", 100))
    
    # At least one filter should be provided
    if not any([query, file_name, file_path, file_type, min_size is not None, max_size is not None, start_date, end_date]):
        return _err("At least one search/filter parameter is required.", 400)
    
    results = DatasetService.advanced_search(
        query=query,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        min_size=min_size,
        max_size=max_size,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    return _ok(results, message=f"Found {len(results)} matching files.")


@data_bp.get("/datasets/stats")
@require_auth
def dataset_stats():
    return _ok(DatasetService.stats())


@data_bp.get("/datasets/<dataset_id>")
@require_auth
def get_dataset(dataset_id: str):
    ds = DatasetService.get_by_id(dataset_id)
    if not ds:
        return _err("Dataset not found.", 404, "NOT_FOUND")
    history = HistoryService.get_for_dataset(dataset_id)
    return _ok({"dataset": ds, "history": history})


@data_bp.post("/check-duplicate")
@require_auth
@rate_limit(max_requests=100, window_seconds=60)
def check_duplicate():
    body = request.get_json(silent=True) or {}
    file_hash = sanitize_str(body.get("file_hash", ""), 128)
    if not file_hash:
        return _err("file_hash is required.")
    existing = DatasetService.get_by_hash(file_hash)
    if existing:
        return _ok({"exists": True, "dataset": existing})
    return _ok({"exists": False})


# ═════════════════════════════════════════════════════════════════════════════
# UPLOAD
# ═════════════════════════════════════════════════════════════════════════════

@upload_bp.post("/upload/file")
@require_auth
@rate_limit(max_requests=20, window_seconds=3600)
def upload_file():
    if "file" not in request.files:
        return _err("No file provided.")

    file = request.files["file"]
    if not file.filename:
        return _err("Empty filename.")

    filename = sanitize_filename(file.filename)
    if not is_allowed_extension(filename):
        return _err(f"File type not allowed: {Path(filename).suffix}")

    user_name  = sanitize_str(request.form.get("user_name", "Anonymous"), 100)
    description= sanitize_str(request.form.get("description", ""), 500)
    period     = sanitize_str(request.form.get("period", ""), 100)
    spatial_domain = sanitize_str(request.form.get("spatial_domain", ""), 200)

    # Save to upload dir
    upload_folder = _config().UPLOAD_FOLDER
    upload_folder.mkdir(parents=True, exist_ok=True)
    dest = upload_folder / filename
    # Avoid overwriting — append uuid if exists
    if dest.exists():
        stem = dest.stem
        dest = upload_folder / f"{stem}_{uuid.uuid4().hex[:8]}{dest.suffix}"

    file.save(str(dest))
    file_hash = hash_file(dest)
    file_size = dest.stat().st_size
    file_type = dest.suffix.lower()

    existing = DatasetService.get_by_hash(file_hash)
    if existing:
        HistoryService.log(
            dataset_id=existing["id"],
            user_name=user_name,
            file_name=filename,
            file_hash=file_hash,
            action="web_upload",
            status="duplicate_detected",
            ip_address=_get_ip(),
        )
        AlertService.create(
            title=f"Duplicate upload: {filename}",
            message=f"Uploaded file matches '{existing['file_name']}' already in repository.",
            file_name=filename,
            file_hash=file_hash,
            file_path=str(dest),
            existing_dataset_id=existing["id"],
        )
        dest.unlink(missing_ok=True)  # don't keep the dupe on disk
        return _ok({
            "is_duplicate": True,
            "existing_file": existing["file_name"],
            "dataset": existing,
        }, message="Duplicate detected — file already in repository.")

    ds = DatasetService.create(
        file_hash=file_hash, file_name=filename, file_size=file_size,
        file_path=str(dest), file_type=file_type, user_name=user_name,
        period=period or None, spatial_domain=spatial_domain or None,
        description=description or None,
    )
    HistoryService.log(
        dataset_id=ds["id"], user_name=user_name, file_name=filename,
        file_hash=file_hash, action="web_upload", status="success", ip_address=_get_ip(),
    )

    insights = get_file_insights(filename, file_size, file_type, description)
    return _created({"is_duplicate": False, "dataset": ds, "ai_insights": insights},
                    message="File uploaded successfully.")


@upload_bp.post("/upload/url")
@require_auth
@rate_limit(max_requests=10, window_seconds=3600)
def upload_from_url():
    body = request.get_json(silent=True) or {}
    url  = sanitize_str(body.get("url", ""), 2000)
    user_name   = sanitize_str(body.get("user_name", "Anonymous"), 100)
    description = sanitize_str(body.get("description", ""), 500)

    if not url:
        return _err("URL is required.")
    if not is_safe_url(url):
        return _err("Invalid or unsafe URL. Private/loopback addresses are not allowed.", 400, "UNSAFE_URL")

    try:
        resp = requests.get(url, timeout=30, stream=True,
                            headers={"User-Agent": "DDAS/2.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        return _err(f"Failed to download file: {exc}", 400, "DOWNLOAD_FAILED")

    # Derive filename
    from urllib.parse import urlparse
    url_path = urlparse(url).path
    filename = sanitize_filename(os.path.basename(url_path) or f"download_{uuid.uuid4().hex[:8]}")
    if not is_allowed_extension(filename):
        filename = filename + ".bin"

    upload_folder = _config().UPLOAD_FOLDER
    upload_folder.mkdir(parents=True, exist_ok=True)
    dest = upload_folder / filename
    if dest.exists():
        dest = upload_folder / f"{dest.stem}_{uuid.uuid4().hex[:8]}{dest.suffix}"

    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)

    file_hash = hash_file(dest)
    file_size = dest.stat().st_size
    file_type = dest.suffix.lower()

    existing = DatasetService.get_by_hash(file_hash)
    if existing:
        dest.unlink(missing_ok=True)
        return _ok({"is_duplicate": True, "existing_file": existing["file_name"], "dataset": existing},
                   message="Duplicate — file already in repository.")

    ds = DatasetService.create(
        file_hash=file_hash, file_name=filename, file_size=file_size,
        file_path=str(dest), file_type=file_type, user_name=user_name,
        description=description or None,
    )
    insights = get_file_insights(filename, file_size, file_type, description)
    return _created({"is_duplicate": False, "dataset": ds, "ai_insights": insights},
                    message="File downloaded and registered.")


# ═════════════════════════════════════════════════════════════════════════════
# ALERTS
# ═════════════════════════════════════════════════════════════════════════════

@alert_bp.get("/alerts")
@require_auth
def get_alerts():
    unread_only = request.args.get("unread") == "1"
    limit = min(int(request.args.get("limit", 100)), 500)
    alerts = AlertService.get_all(unread_only=unread_only, limit=limit)
    count = AlertService.unread_count()
    return _ok({"alerts": alerts, "unread_count": count})


@alert_bp.patch("/alerts/<alert_id>/read")
@require_auth
def mark_alert_read(alert_id: str):
    AlertService.mark_read(alert_id)
    return _ok(message="Alert marked as read.")


@alert_bp.post("/alerts/read-all")
@require_auth
def mark_all_alerts_read():
    AlertService.mark_all_read()
    return _ok(message="All alerts marked as read.")


# ═════════════════════════════════════════════════════════════════════════════
# MONITOR
# ═════════════════════════════════════════════════════════════════════════════

@monitor_bp.post("/monitor/scan")
@require_auth
@rate_limit(max_requests=5, window_seconds=60)
def trigger_scan():
    """Scan the monitored directory or a specified directory for duplicates."""
    body = request.get_json(silent=True) or {}
    directory = sanitize_str(body.get("directory", ""), 500)
    
    # If directory is specified, validate and scan it
    if directory:
        dir_path = Path(directory)
        if not dir_path.exists():
            return _err(f"Directory not found: {directory}", 404)
        if not dir_path.is_dir():
            return _err(f"Path is not a directory: {directory}", 400)
    
    try:
        # Perform scan
        result = manual_scan(directory or None)
        
        # Create export if scanning custom directory
        export_zip = None
        if directory:
            export_zip = create_zip_export(result, include_metadata=True)
        
        # Log the scan if it was successful
        if result.get("scanned", 0) > 0:
            HistoryService.log(
                dataset_id=None,
                user_name=g.get("current_user", {}).get("username", "System"),
                file_name=f"Manual scan: {directory or 'monitored dir'}",
                file_hash="",
                action="manual_scan",
                status="completed",
                notes=f"Scanned {result.get('scanned', 0)} files, found {result.get('duplicates', 0)} duplicates",
            )
        
        response_data = {
            "scanned": result.get("scanned", 0),
            "duplicates": result.get("duplicates", 0),
            "errors": result.get("errors", 0),
            "directory": result.get("directory", ""),
        }
        
        if export_zip:
            response_data["export_zip"] = Path(export_zip).name
            response_data["summary"] = {
                "total_files": result.get("scanned", 0),
                "duplicates_found": result.get("duplicates", 0),
                "errors": result.get("errors", 0),
            }
        
        return _ok(response_data, message=f"Scan complete: {result.get('scanned', 0)} files scanned, {result.get('duplicates', 0)} duplicates found")
    except PermissionError:
        return _err("Permission denied accessing directory.", 403)
    except Exception as exc:
        return _err(f"Scan failed: {exc}", 500)


@monitor_bp.get("/monitor/status")
@require_auth
def get_monitor_status():
    return _ok(monitor_status())


@monitor_bp.post("/monitor/start")
@require_role("admin", "operator")
def start_monitor_route():
    started = start_monitor()
    return _ok({"started": started})


@monitor_bp.post("/monitor/stop")
@require_role("admin")
def stop_monitor_route():
    stop_monitor()
    return _ok({"stopped": True})


@monitor_bp.get("/scan-logs")
@require_auth
def get_scan_logs():
    limit = min(int(request.args.get("limit", 100)), 500)
    return _ok(ScanLogService.get_recent(limit))


@monitor_bp.get("/history")
@require_auth
def get_history():
    limit = min(int(request.args.get("limit", 100)), 500)
    return _ok(HistoryService.get_recent(limit))


# ═════════════════════════════════════════════════════════════════════════════
# AI
# ═════════════════════════════════════════════════════════════════════════════

# In-memory session store (swap for Redis in production)
_chat_sessions: dict[str, list[dict]] = {}
_MAX_HISTORY = 20


@ai_bp.post("/chat")
@require_auth
@rate_limit(max_requests=60, window_seconds=3600)
def chat_endpoint():
    body = request.get_json(silent=True) or {}
    message = sanitize_str(body.get("message", ""), 2000)
    session_id = sanitize_str(body.get("session_id", "default"), 64)
    context = sanitize_str(body.get("context", ""), 1000)

    if not message:
        return _err("message is required.")

    history = _chat_sessions.get(session_id, [])
    current_user = g.get("current_user", {}) or {}
    reply = execute_chat_action(
        message,
        user_role=str(current_user.get("role", "")),
        username=str(current_user.get("username", "")),
    )
    if reply is None:
        reply = ai_chat(message, history, context)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    _chat_sessions[session_id] = history[-_MAX_HISTORY:]

    return _ok({"reply": reply, "session_id": session_id})


@ai_bp.post("/chat/clear")
@require_auth
def clear_chat():
    body = request.get_json(silent=True) or {}
    session_id = sanitize_str(body.get("session_id", "default"), 64)
    _chat_sessions.pop(session_id, None)
    return _ok(message="Chat history cleared.")


@ai_bp.get("/status")
def ai_status():
    import os
    return _ok({
        "api_configured": is_api_configured(),
        "model": os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"),
        "provider": "Google Generative AI (Gemini)",
    })


# ═════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════

@analytics_bp.get("/dashboard")
@require_auth
def get_dashboard():
    """Get comprehensive dashboard statistics."""
    stats = get_dashboard_stats()
    return _ok(stats)


@analytics_bp.get("/timeline")
@require_auth
def get_timeline():
    """Get timeline data for charts (daily uploads, duplicates, storage)."""
    days = min(int(request.args.get("days", 30)), 365)
    data = get_timeline_data(days)
    return _ok(data)


@analytics_bp.get("/file-types")
@require_auth
def get_file_types():
    """Get distribution of file types in repository."""
    distribution = get_file_type_distribution()
    return _ok(distribution)


@analytics_bp.get("/user-activity")
@require_auth
@require_role("admin", "operator")
def get_user_activity_endpoint():
    """Get user activity metrics."""
    limit = min(int(request.args.get("limit", 50)), 500)
    activity = get_user_activity(limit)
    return _ok(activity)


@analytics_bp.get("/top-duplicates")
@require_auth
def get_top_duplicates_endpoint():
    """Get the most frequently duplicated files."""
    limit = min(int(request.args.get("limit", 20)), 100)
    duplicates = get_top_duplicates(limit)
    return _ok(duplicates)


@analytics_bp.get("/system-health")
@require_auth
@require_role("admin")
def get_system_health_endpoint():
    """Get system health metrics."""
    health = get_system_health()
    return _ok(health)


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═════════════════════════════════════════════════════════════════════════════

@export_bp.post("/scan-results")
@require_auth
@rate_limit(max_requests=10, window_seconds=3600)
def export_scan_results():
    """
    Create and export zip file of scan results.
    Requires completed scan data.
    """
    body = request.get_json(silent=True) or {}
    scan_results = body.get("scan_results", {})
    
    if not scan_results:
        return _err("scan_results required.", 400)
    
    try:
        zip_path = create_zip_export(scan_results, include_metadata=True)
        return _ok({
            "zip_file": Path(zip_path).name,
            "path": zip_path,
            "timestamp": datetime.now().isoformat(),
        }, message="Scan export created successfully.")
    except Exception as exc:
        return _err(f"Export failed: {exc}", 500)


@export_bp.post("/datasets")
@require_auth
@rate_limit(max_requests=5, window_seconds=3600)
def export_datasets():
    """
    Export filtered datasets to zip file.
    Supports filtering by date, file type, user, or duplicate status.
    """
    body = request.get_json(silent=True) or {}
    filter_criteria = body.get("filters", {})
    
    try:
        zip_path = export_filtered_datasets(filter_criteria)
        return _ok({
            "zip_file": Path(zip_path).name,
            "path": zip_path,
            "filters_applied": filter_criteria,
            "timestamp": datetime.now().isoformat(),
        }, message="Datasets export created successfully.")
    except Exception as exc:
        return _err(f"Export failed: {exc}", 500)


@export_bp.post("/cleanup")
@require_auth
@require_role("admin")
def cleanup_exports():
    """Remove old export files (older than 7 days)."""
    days = int(request.args.get("days", 7))
    deleted_count = cleanup_old_exports(days)
    return _ok({
        "deleted_count": deleted_count,
        "days_retained": days,
    }, message=f"Cleaned up {deleted_count} old export files.")


@export_bp.get("/list")
@require_auth
def list_exports():
    """List available export files."""
    export_dir = _config().UPLOAD_FOLDER / "exports"
    if not export_dir.exists():
        return _ok([])
    
    exports = []
    for file_path in sorted(export_dir.glob("*.zip"), reverse=True)[:50]:
        exports.append({
            "filename": file_path.name,
            "size_mb": file_path.stat().st_size / (1024 ** 2),
            "created_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        })
    
    return _ok(exports)


@export_bp.get("/download")
@require_auth
def download_export():
    """Download an export file."""
    filename = sanitize_filename(request.args.get("file", ""))
    if not filename:
        return _err("file parameter required", 400)
    
    export_dir = _config().UPLOAD_FOLDER / "exports"
    file_path = export_dir / filename
    
    # Security: ensure file is in export directory
    if not file_path.exists() or not str(file_path).startswith(str(export_dir)):
        return _err("File not found", 404)
    
    try:
        return send_from_directory(str(export_dir), filename, as_attachment=True)
    except Exception as exc:
        return _err(f"Download failed: {exc}", 500)


# ═════════════════════════════════════════════════════════════════════════════

@monitor_bp.get("/scan-progress")
@require_auth
def get_scan_progress():
    """
    Get current scan progress (for real-time updates).
    This is a placeholder - implement with WebSocket for true real-time.
    """
    # In production, use WebSocket or Server-Sent Events for real-time
    recent_scans = ScanLogService.get_recent(10)
    return _ok({
        "recent_scans": recent_scans,
        "last_updated": datetime.utcnow().isoformat(),
    })


# ═════════════════════════════════════════════════════════════════════════════
# DUPLICATES (Duplicate Detection & Display)
# ═════════════════════════════════════════════════════════════════════════════

@duplicates_bp.get("/all")
@require_auth
def get_all_duplicates():
    """
    Get all duplicate groups in the system.
    Returns list of duplicate groups with all file locations.
    """
    limit = min(int(request.args.get("limit", 100)), 500)
    duplicates = DuplicateService.get_all_duplicates(limit=limit)
    return _ok({
        "duplicates": duplicates,
        "total_groups": len(duplicates),
    }, message=f"Found {len(duplicates)} duplicate groups")


@duplicates_bp.get("/by-hash/<file_hash>")
@require_auth
def get_duplicates_by_hash(file_hash: str):
    """
    Get all files with the same hash (duplicates).
    Displays original file and all duplicate locations.
    """
    file_hash = sanitize_str(file_hash, 128)
    dup_group = DuplicateService.get_duplicates_by_hash(file_hash)
    
    if not dup_group:
        return _err(f"No files found with hash: {file_hash}", 404)
    
    return _ok(dup_group, message=f"Found {dup_group['total_copies']} copies of this file")


@duplicates_bp.get("/for-file/<dataset_id>")
@require_auth
def get_duplicates_for_file(dataset_id: str):
    """
    Get all duplicates for a specific file by dataset ID.
    Shows original and all duplicate locations.
    """
    dup_group = DuplicateService.get_duplicates_for_file(dataset_id)
    
    if "error" in dup_group:
        return _err(dup_group["error"], 404)
    if not dup_group:
        return _ok({"message": "No duplicates found for this file", "copies": 1})
    
    return _ok(dup_group)


@duplicates_bp.get("/by-name")
@require_auth
def find_duplicates_by_name():
    """
    Search for files with the same name (potential duplicates).
    """
    file_name = sanitize_search_query(request.args.get("name", ""))
    
    if not file_name:
        return _err("name parameter is required", 400)
    
    duplicates = DuplicateService.find_duplicates_by_name(file_name)
    return _ok({
        "search_term": file_name,
        "duplicates": duplicates,
        "total_groups": len(duplicates),
    }, message=f"Found {len(duplicates)} duplicate groups with name containing '{file_name}'")


@duplicates_bp.get("/statistics")
@require_auth
def get_duplicate_statistics():
    """
    Get comprehensive duplicate statistics for the system.
    Shows total duplicates, wasted storage, and percentages.
    """
    stats = DuplicateService.get_duplicate_statistics()
    return _ok(stats)


@duplicates_bp.post("/mark-for-deduplication")
@require_auth
def mark_for_deduplication():
    """
    Mark a duplicate group for deduplication.
    Keeps original, marks others for deletion or archives.
    """
    body = request.get_json(silent=True) or {}
    file_hash = sanitize_str(body.get("file_hash", ""), 128)
    action = sanitize_str(body.get("action", "convert_to_link"), 50)  # delete | archive | convert_to_link
    
    if not file_hash:
        return _err("file_hash is required", 400)
    
    valid_actions = ["delete", "archive", "convert_to_link"]
    if action not in valid_actions:
        return _err(f"Invalid action. Must be one of: {', '.join(valid_actions)}", 400)
    
    dup_group = DuplicateService.get_duplicates_by_hash(file_hash)
    if not dup_group or len(dup_group.get("all_files", [])) <= 1:
        return _err("No duplicates found for this hash", 404)
    
    # Log the deduplication action
    HistoryService.log(
        dataset_id=None,
        user_name=g.get("current_user", {}).get("username", "System"),
        file_name=f"Deduplication: {file_hash}",
        file_hash=file_hash,
        action="deduplication_marked",
        status="pending",
        notes=f"Action: {action}, Duplicates: {len(dup_group['duplicate_locations'])}, Storage saved: {dup_group['storage_saved_if_deduplicated']} bytes",
    )
    
    return _ok({
        "marked": True,
        "file_hash": file_hash,
        "action": action,
        "copies": len(dup_group["all_files"]),
        "storage_saved": dup_group["storage_saved_if_deduplicated"],
        "storage_saved_gb": round(dup_group["storage_saved_if_deduplicated"] / (1024**3), 2),
    }, message=f"Marked {len(dup_group['duplicate_locations'])} duplicates for {action}")


@duplicates_bp.post("/scan-directory")
@require_auth
def scan_directory_for_duplicates():
    """
    Scan a directory on the file system for duplicates.
    Computes file hashes and returns duplicate groups with locations.
    """
    body = request.get_json(silent=True) or {}
    directory = sanitize_str(body.get("directory", ""), 512)
    recursive = body.get("recursive", True)
    extensions = body.get("extensions", None)
    
    if not directory:
        return _err("directory is required", 400)
    
    try:
        result = DuplicateService.scan_directory_for_duplicates(
            directory=directory,
            recursive=recursive,
            extensions=extensions
        )
        
        # Log the scan
        HistoryService.log(
            dataset_id=None,
            user_name=g.get("current_user", {}).get("username", "System"),
            file_name=f"Directory scan: {directory}",
            file_hash="",
            action="directory_scan",
            status="completed",
            notes=f"Scanned {result['scanned_files']} files, found {result['total_duplicates']} duplicate groups",
        )
        
        return _ok(result)
    except Exception as e:
        return _err(f"Scan failed: {str(e)}", 500)


@duplicates_bp.post("/search-by-filename")
@require_auth
def search_duplicates_by_filename():
    """
    Search for all instances of a filename across system paths.
    Returns all found files with duplicate status and details.
    """
    body = request.get_json(silent=True) or {}
    filename = sanitize_str(body.get("filename", ""), 256)
    search_paths = body.get("search_paths", None)
    
    if not filename:
        return _err("filename is required", 400)
    
    try:
        result = DuplicateService.search_duplicates_by_filename(
            filename=filename,
            search_paths=search_paths
        )
        
        # Log the search
        HistoryService.log(
            dataset_id=None,
            user_name=g.get("current_user", {}).get("username", "System"),
            file_name=f"Search duplicates: {filename}",
            file_hash="",
            action="filename_search",
            status="completed",
            notes=f"Found {result['total_files']} files, {result['total_duplicates']} duplicates in {len(result['duplicate_groups'])} groups",
        )
        
        return _ok(result)
    except Exception as e:
        return _err(f"Search failed: {str(e)}", 500)
