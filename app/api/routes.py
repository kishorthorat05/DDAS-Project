"""
API blueprints for DDAS.
All endpoints return JSON. Auth via JWT Bearer token.
"""
import os
import random
import sqlite3
import time
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
from app.services.profile_service import ProfileService
from app.utils.security import (
    hash_file, hash_bytes,
    is_allowed_extension, is_safe_url,
    jwt_required, rate_limit, require_auth, require_role,
    require_permission,
    sanitize_filename, sanitize_search_query, sanitize_str,
    hash_password, verify_password, create_access_token, create_refresh_token,
)
from app.models.database import (
    get_db, row_to_dict, create_user_profile, get_user_with_profile,
    get_user_profile as db_get_user_profile,
)
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
profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

_OTP_TTL_SECONDS = 300
_otp_store: dict[tuple[str, str], dict] = {}

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


def _normalize_phone(phone: str) -> str:
    return sanitize_str(phone or "", 32).replace(" ", "").replace("-", "")


def _profile_avatar_folder() -> Path:
    folder = _config().UPLOAD_FOLDER.parent / "profile_avatars"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _is_allowed_avatar(filename: str) -> bool:
    extension = Path(filename).suffix.lower().lstrip(".")
    return extension in {"jpg", "jpeg", "png", "gif", "webp"}


def _issue_otp(user_id: str, purpose: str, phone: str) -> str:
    otp = f"{random.randint(100000, 999999)}"
    _otp_store[(user_id, purpose)] = {
        "otp": otp,
        "phone": phone,
        "expires_at": time.time() + _OTP_TTL_SECONDS,
    }
    return otp


def _verify_otp(user_id: str, purpose: str, otp: str) -> tuple[bool, str]:
    record = _otp_store.get((user_id, purpose))
    if not record:
        return False, "OTP was not requested."
    if time.time() > record["expires_at"]:
        _otp_store.pop((user_id, purpose), None)
        return False, "OTP expired. Request a new OTP."
    if sanitize_str(otp or "", 12) != record["otp"]:
        return False, "Invalid OTP."

    _otp_store.pop((user_id, purpose), None)
    return True, ""


# ═════════════════════════════════════════════════════════════════════════════
# AUTH
# ═════════════════════════════════════════════════════════════════════════════

@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    username = sanitize_str(body.get("username", ""), 50)
    password = body.get("password", "")
    email = sanitize_str(body.get("email", ""), 200)
    full_name = sanitize_str(body.get("full_name", ""), 100)
    requested_role = sanitize_str(body.get("role", "registered"), 30).lower()
    allowed_self_service_roles = {"registered", "admin"}

    if not username or len(username) < 3:
        return _err("Username must be at least 3 characters.")
    if len(password) < 8:
        return _err("Password must be at least 8 characters.")
    if requested_role not in allowed_self_service_roles:
        return _err("Invalid role for self registration.", 400, "INVALID_ROLE")

    pw_hash = hash_password(password)
    try:
        with get_db() as conn:
            if requested_role == "admin":
                admin_count = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role IN ('admin', 'administrator') AND is_active = 1"
                ).fetchone()[0]
                if admin_count:
                    requested_role = "registered"

            conn.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email or None, pw_hash, requested_role),
            )
            user = row_to_dict(conn.execute(
                "SELECT id, username, email, role FROM users WHERE username = ?", (username,)
            ).fetchone())

        # Create user profile with role-derived permissions and preferences.
        create_user_profile(user["id"], role=user["role"], full_name=full_name or username, email=email)
    except sqlite3.IntegrityError as exc:
        if "users.email" in str(exc):
            return _err("Email already exists. Use another email or leave it blank.", 409, "CONFLICT")
        return _err("Username already exists. Choose another username.", 409, "CONFLICT")
    except Exception:
        return _err("Registration failed. Please try again.", 500, "REGISTER_FAILED")

    token = create_access_token({"sub": user["id"], "username": user["username"], "role": user["role"]})
    profile = ProfileService.get_user_profile_data(user["id"]) or user
    return _created({"user": profile, "access_token": token})


@auth_bp.post("/login")
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

    normalized_role = "admin" if user.get("role") in {"admin", "administrator"} else "registered"
    if user.get("role") != normalized_role:
        with get_db() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (normalized_role, user["id"]))
        user["role"] = normalized_role
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login = strftime('%Y-%m-%dT%H:%M:%fZ','now'), login_count = COALESCE(login_count, 0) + 1 WHERE id = ?",
            (user["id"],),
        )

    if not db_get_user_profile(user["id"]):
        create_user_profile(user["id"], role=user.get("role", "registered"), full_name=user["username"], email=user.get("email") or "")
    else:
        default_preferences = ProfileService.get_role_profile(user["role"])["default_preferences"]
        current_preferences = ProfileService.get_user_preferences(user["id"])
        ProfileService.update_user_profile(
            user["id"],
            permissions=ProfileService.ROLE_PERMISSIONS[user["role"]],
            preferences={**default_preferences, **current_preferences},
        )

    token = create_access_token({"sub": user["id"], "username": user["username"], "role": user["role"]})
    refresh = create_refresh_token(user["id"])
    safe_user = ProfileService.get_user_profile_data(user["id"]) or {k: v for k, v in user.items() if k != "password_hash"}
    return _ok({"user": safe_user, "access_token": token, "refresh_token": refresh})


@auth_bp.post("/request-otp")
@require_auth
def request_otp():
    body = request.get_json(silent=True) or {}
    purpose = sanitize_str(body.get("purpose", ""), 40)
    phone_number = _normalize_phone(body.get("phone_number", ""))
    uid = g.current_user.get("sub")

    if purpose not in {"change_password", "mobile_2fa"}:
        return _err("Invalid OTP purpose.", 400, "INVALID_OTP_PURPOSE")
    if not phone_number:
        profile = db_get_user_profile(uid) or {}
        phone_number = _normalize_phone(profile.get("phone_number", ""))
    if not phone_number:
        return _err("Mobile number is required to send OTP.", 400, "PHONE_REQUIRED")

    otp = _issue_otp(uid, purpose, phone_number)
    return _ok(
        {
            "sent": True,
            "phone_number": phone_number,
            "expires_in": _OTP_TTL_SECONDS,
            "dev_otp": otp,
        },
        message="OTP generated for mobile verification.",
    )


@auth_bp.post("/change-password")
@require_auth
def change_password():
    body = request.get_json(silent=True) or {}
    current_password = body.get("current_password", "")
    new_password = body.get("new_password", "")
    otp = body.get("otp", "")
    uid = g.current_user.get("sub")

    if len(new_password) < 8:
        return _err("New password must be at least 8 characters.", 400, "WEAK_PASSWORD")

    otp_ok, otp_error = _verify_otp(uid, "change_password", otp)
    if not otp_ok:
        return _err(otp_error, 400, "INVALID_OTP")

    with get_db() as conn:
        user = row_to_dict(conn.execute(
            "SELECT id, password_hash FROM users WHERE id = ? AND is_active = 1", (uid,)
        ).fetchone())
        if not user or not verify_password(current_password, user["password_hash"]):
            return _err("Current password is incorrect.", 401, "INVALID_PASSWORD")
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (hash_password(new_password), uid),
        )

    return _ok({"changed": True}, message="Password changed successfully.")


@auth_bp.post("/guest")
def guest_login():
    """Return the guest role profile used by the unauthenticated UI."""
    return _ok({
        "user": {
            "id": "guest",
            "username": "Guest",
            "email": None,
            "role": "guest",
            "profile": {
                "full_name": "Guest User",
                "permissions": ProfileService.ROLE_PERMISSIONS["guest"],
                "preferences": ProfileService.get_role_profile("guest")["default_preferences"],
                "profile_status": "active",
            },
            "role_metadata": ProfileService.get_role_profile("guest"),
        },
        "access_token": "",
    })


@auth_bp.get("/me")
@require_auth
def me():
    uid = g.current_user.get("sub")
    # Get user with profile data
    user_with_profile = get_user_with_profile(uid)
    if not user_with_profile:
        return _err("User not found.", 404)

    # Update last active
    ProfileService.update_last_active(uid)

    return _ok(user_with_profile)


# ═════════════════════════════════════════════════════════════════════════════
# DATASETS
# ═════════════════════════════════════════════════════════════════════════════

@data_bp.get("/datasets")
@jwt_required
def get_datasets():
    limit  = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))
    return _ok(DatasetService.get_all(limit, offset))


@data_bp.get("/datasets/search")
@jwt_required
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
@jwt_required
def dataset_stats():
    return _ok(DatasetService.stats())


@data_bp.get("/datasets/<dataset_id>")
@require_auth
def get_dataset(dataset_id: str):
    ds = DatasetService.get_by_id(dataset_id)
    if not ds:
        return _err("Dataset not found.", 404, "NOT_FOUND")
    current_user = g.get("current_user", {}) or {}
    include_all = request.args.get("scope") == "all" and current_user.get("role") == "admin"
    history = HistoryService.get_for_dataset(
        dataset_id,
        user_id=None if include_all else current_user.get("sub"),
    )
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
@require_permission("upload")
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

    current_user = g.get("current_user", {}) or {}
    user_id = current_user.get("sub")
    user_name  = sanitize_str(request.form.get("user_name", current_user.get("username", "Anonymous")), 100)
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
            user_id=user_id,
            user_name=user_name,
            file_name=filename,
            file_hash=file_hash,
            action="web_upload",
            status="duplicate_detected",
            ip_address=_get_ip(),
        )
        ScanLogService.log(
            file_path=str(dest),
            file_name=filename,
            file_size=dest.stat().st_size if dest.exists() else 0,
            file_hash=file_hash,
            is_duplicate=True,
            user_id=user_id,
            user_name=user_name,
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
        user_id=user_id,
        period=period or None, spatial_domain=spatial_domain or None,
        description=description or None,
    )
    HistoryService.log(
        dataset_id=ds["id"], user_id=user_id, user_name=user_name, file_name=filename,
        file_hash=file_hash, action="web_upload", status="success", ip_address=_get_ip(),
    )
    ScanLogService.log(
        file_path=str(dest),
        file_name=filename,
        file_size=file_size,
        file_hash=file_hash,
        is_duplicate=False,
        user_id=user_id,
        user_name=user_name,
    )

    insights = get_file_insights(filename, file_size, file_type, description)
    return _created({"is_duplicate": False, "dataset": ds, "ai_insights": insights},
                    message="File uploaded successfully.")


@upload_bp.post("/upload/url")
@require_permission("upload")
@rate_limit(max_requests=10, window_seconds=3600)
def upload_from_url():
    body = request.get_json(silent=True) or {}
    url  = sanitize_str(body.get("url", ""), 2000)
    current_user = g.get("current_user", {}) or {}
    user_id = current_user.get("sub")
    user_name   = sanitize_str(body.get("user_name", current_user.get("username", "Anonymous")), 100)
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
        user_id=user_id,
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
        current_user = g.get("current_user", {}) or {}
        scan_directory = directory or str(_config().UPLOAD_FOLDER)
        result = manual_scan(
            scan_directory,
            user_id=current_user.get("sub"),
            user_name=current_user.get("username", "System"),
        )

        # Create export if scanning custom directory
        export_zip = None
        if directory:
            export_zip = create_zip_export(result, include_metadata=True)

        # Log the scan if it was successful
        if result.get("scanned", 0) > 0:
            HistoryService.log(
                dataset_id=None,
                user_id=current_user.get("sub"),
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
@require_role("admin")
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
    current_user = g.get("current_user", {}) or {}
    if current_user.get("role") == "admin":
        return _ok(ScanLogService.get_recent(limit))
    return _ok(ScanLogService.get_recent(limit, user_id=current_user.get("sub")))


@monitor_bp.get("/history")
@require_auth
def get_history():
    limit = min(int(request.args.get("limit", 100)), 500)
    current_user = g.get("current_user", {}) or {}
    include_all = request.args.get("scope") == "all" and current_user.get("role") == "admin"
    if include_all:
        return _ok(HistoryService.get_recent(limit))
    return _ok(HistoryService.get_recent(limit, user_id=current_user.get("sub")))


# ═════════════════════════════════════════════════════════════════════════════
# AI
# ═════════════════════════════════════════════════════════════════════════════

# In-memory session store (swap for Redis in production)
_chat_sessions: dict[str, list[dict]] = {}
_MAX_HISTORY = 20


@ai_bp.post("/chat")
@jwt_required
@rate_limit(max_requests=60, window_seconds=3600)
def chat_endpoint():
    body = request.get_json(silent=True) or {}
    message = sanitize_str(body.get("message", ""), 2000)
    session_id = sanitize_str(body.get("session_id", "default"), 64)
    context = sanitize_str(body.get("context", ""), 1000)

    if not message:
        return _err("message is required.")

    current_user = g.get("current_user", None) or {
        "sub": "guest",
        "username": "Guest",
        "role": "guest",
    }
    if current_user.get("role") == "guest" and len(message) > 500:
        return _err("Guest AI chat is limited to 500 characters per message.", 403, "GUEST_LIMIT")
    if current_user.get("role") != "guest" and not ProfileService.has_permission(current_user.get("sub"), "ai_chat"):
        return _err("Insufficient permissions", 403, "FORBIDDEN")

    session_key = f"{current_user.get('sub', 'guest')}:{session_id}"
    history = _chat_sessions.get(session_key, [])
    reply = execute_chat_action(
        message,
        user_role=str(current_user.get("role", "")),
        username=str(current_user.get("username", "")),
    )
    if reply is None:
        reply = ai_chat(message, history, context)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    _chat_sessions[session_key] = history[-_MAX_HISTORY:]

    return _ok({"reply": reply, "session_id": session_id})


@ai_bp.post("/chat/clear")
@require_auth
def clear_chat():
    body = request.get_json(silent=True) or {}
    session_id = sanitize_str(body.get("session_id", "default"), 64)
    current_user = g.get("current_user", {}) or {}
    _chat_sessions.pop(f"{current_user.get('sub', 'guest')}:{session_id}", None)
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
@jwt_required
def get_dashboard():
    """Get comprehensive dashboard statistics."""
    stats = get_dashboard_stats()
    return _ok(stats)


@analytics_bp.get("/timeline")
@jwt_required
def get_timeline():
    """Get timeline data for charts (daily uploads, duplicates, storage)."""
    days = min(int(request.args.get("days", 30)), 365)
    data = get_timeline_data(days)
    return _ok(data)


@analytics_bp.get("/file-types")
@jwt_required
def get_file_types():
    """Get distribution of file types in repository."""
    distribution = get_file_type_distribution()
    return _ok(distribution)


@analytics_bp.get("/user-activity")
@require_auth
@require_role("admin")
def get_user_activity_endpoint():
    """Get user activity metrics."""
    limit = min(int(request.args.get("limit", 50)), 500)
    activity = get_user_activity(limit)
    return _ok(activity)


@analytics_bp.get("/top-duplicates")
@jwt_required
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
@require_permission("export_data")
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
@require_permission("export_data")
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
@require_permission("export_data")
def cleanup_exports():
    """Remove old export files (older than 7 days)."""
    days = int(request.args.get("days", 7))
    deleted_count = cleanup_old_exports(days)
    return _ok({
        "deleted_count": deleted_count,
        "days_retained": days,
    }, message=f"Cleaned up {deleted_count} old export files.")


@export_bp.get("/list")
@require_permission("export_data")
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
@require_permission("export_data")
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
@jwt_required
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
@jwt_required
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
@jwt_required
def get_duplicate_statistics():
    """
    Get comprehensive duplicate statistics for the system.
    Shows total duplicates, wasted storage, and percentages.
    """
    stats = DuplicateService.get_duplicate_statistics()
    return _ok(stats)


@duplicates_bp.post("/mark-for-deduplication")
@require_permission("manage_alerts")
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
        user_id=g.get("current_user", {}).get("sub"),
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
@require_permission("run_scanner")
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
            user_id=g.get("current_user", {}).get("sub"),
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
            user_id=g.get("current_user", {}).get("sub"),
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


# ═════════════════════════════════════════════════════════════════════════════
# USER PROFILES (Role-based profiles)
# ═════════════════════════════════════════════════════════════════════════════

@profile_bp.get("/me")
@require_auth
def get_my_profile():
    """Get current user's complete profile with role metadata."""
    uid = g.current_user.get("sub")
    profile_data = ProfileService.get_user_profile_data(uid)

    if not profile_data:
        return _err("Profile not found.", 404)

    return _ok(profile_data)


@profile_bp.get("/avatar/<path:filename>")
def get_profile_avatar(filename: str):
    """Serve uploaded profile avatars."""
    safe_name = sanitize_filename(filename)
    if safe_name != filename or not _is_allowed_avatar(safe_name):
        return _err("Avatar not found.", 404)
    return send_from_directory(_profile_avatar_folder(), safe_name)


@profile_bp.post("/avatar")
@require_auth
def upload_profile_avatar():
    """Upload the current user's profile avatar and store its app-served URL."""
    uid = g.current_user.get("sub")
    file = request.files.get("avatar")
    if not file or not file.filename:
        return _err("Avatar image is required.", 400)

    if not _is_allowed_avatar(file.filename):
        return _err("Avatar must be a JPG, PNG, GIF, or WebP image.", 400)

    if request.content_length and request.content_length > 5 * 1024 * 1024:
        return _err("Avatar image must be 5 MB or smaller.", 413, "FILE_TOO_LARGE")

    original_name = sanitize_filename(file.filename)
    extension = Path(original_name).suffix.lower()
    filename = f"{uid}_{uuid.uuid4().hex}{extension}"
    destination = _profile_avatar_folder() / filename

    try:
        file.save(destination)
        avatar_url = f"/api/profile/avatar/{filename}"
        updated_profile = ProfileService.update_user_profile(uid, avatar_url=avatar_url)
        return _ok({"avatar_url": avatar_url, "profile": updated_profile}, message="Profile photo uploaded.")
    except Exception as exc:
        return _err(f"Profile photo upload failed: {exc}", 500)


@profile_bp.patch("/me")
@require_auth
def update_my_profile():
    """Update current user's profile (full_name, bio, preferences, etc.)."""
    uid = g.current_user.get("sub")
    body = request.get_json(silent=True) or {}

    # Allowed fields for user to update
    allowed_fields = [
        "full_name", "bio", "avatar_url", "phone_number", "department",
        "title", "timezone", "language", "theme", "notifications_enabled",
        "email_notifications", "preferences"
    ]

    updates = {k: v for k, v in body.items() if k in allowed_fields and v is not None}
    if isinstance(updates.get("preferences"), dict):
        updates["preferences"].pop("two_factor_mobile_enabled", None)
        current_preferences = ProfileService.get_user_preferences(uid)
        updates["preferences"] = {**current_preferences, **updates["preferences"]}

    if not updates:
        return _err("No valid fields to update.", 400)

    try:
        updated_profile = ProfileService.update_user_profile(uid, **updates)
        return _ok(updated_profile, message="Profile updated successfully.")
    except Exception as exc:
        return _err(f"Profile update failed: {exc}", 500)


@profile_bp.post("/2fa-mobile")
@require_auth
def update_mobile_2fa():
    """Enable or disable mobile 2FA. Enabling requires a mobile OTP."""
    uid = g.current_user.get("sub")
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled"))
    phone_number = _normalize_phone(body.get("phone_number", ""))

    if enabled:
        if not phone_number:
            return _err("Mobile number is required to enable 2FA.", 400, "PHONE_REQUIRED")
        otp_ok, otp_error = _verify_otp(uid, "mobile_2fa", body.get("otp", ""))
        if not otp_ok:
            return _err(otp_error, 400, "INVALID_OTP")

    preferences = ProfileService.get_user_preferences(uid)
    preferences["two_factor_mobile_enabled"] = enabled

    try:
        updated_profile = ProfileService.update_user_profile(
            uid,
            phone_number=phone_number,
            preferences=preferences,
        )
        return _ok(updated_profile, message="Mobile 2FA updated successfully.")
    except Exception as exc:
        return _err(f"Mobile 2FA update failed: {exc}", 500)


@profile_bp.get("/role-info")
def get_role_info():
    """Get information about all roles and their permissions."""
    return _ok(ProfileService.get_role_summary())


@profile_bp.get("/role-info/<role>")
def get_role_details(role: str):
    """Get detailed information about a specific role."""
    role = sanitize_str(role, 50).lower()
    role_info = ProfileService.get_role_profile(role)

    if not role_info:
        return _err(f"Role '{role}' not found.", 404)

    return _ok(role_info)


@profile_bp.get("/users")
@require_auth
@require_role("admin")
def get_all_users_profiles():
    """Get all user profiles (admin only)."""
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    profiles = ProfileService.get_all_profiles(limit, offset)
    return _ok({
        "profiles": profiles,
        "total": len(profiles),
        "limit": limit,
        "offset": offset
    })


@profile_bp.get("/users/role/<role>")
@require_auth
@require_role("admin")
def get_users_by_role(role: str):
    """Get all users with a specific role (admin only)."""
    role = sanitize_str(role, 50).lower()
    limit = min(int(request.args.get("limit", 100)), 500)

    profiles = ProfileService.get_profiles_by_role(role, limit)
    return _ok({
        "role": role,
        "profiles": profiles,
        "total": len(profiles)
    })


@profile_bp.get("/users/<user_id>")
@require_auth
def get_user_profile(user_id: str):
    """Get a specific user's profile."""
    user_id = sanitize_str(user_id, 128)
    profile_data = ProfileService.get_user_profile_data(user_id)

    if not profile_data:
        return _err("User profile not found.", 404)

    # Check if user is requesting their own profile or if requester is admin
    current_uid = g.current_user.get("sub")
    current_user_role = g.current_user.get("role")

    if current_uid != user_id and current_user_role != "admin":
        return _err("You don't have permission to view this profile.", 403)

    return _ok(profile_data)


@profile_bp.get("/users/<user_id>/stats")
@require_auth
def get_user_stats(user_id: str):
    """Get user statistics."""
    user_id = sanitize_str(user_id, 128)

    # Check permission
    current_uid = g.current_user.get("sub")
    current_user_role = g.current_user.get("role")

    if current_uid != user_id and current_user_role != "admin":
        return _err("You don't have permission to view these stats.", 403)

    stats = ProfileService.get_user_stats(user_id)
    if not stats:
        return _err("User not found.", 404)

    return _ok(stats)


@profile_bp.get("/users/<user_id>/permissions")
@require_auth
def get_user_permissions(user_id: str):
    """Get user's permissions."""
    user_id = sanitize_str(user_id, 128)

    # Check permission
    current_uid = g.current_user.get("sub")
    current_user_role = g.current_user.get("role")

    if current_uid != user_id and current_user_role != "admin":
        return _err("You don't have permission to view these permissions.", 403)

    permissions = ProfileService.get_user_permissions(user_id)
    if not permissions and user_id != current_uid:
        return _err("User not found.", 404)

    return _ok({"user_id": user_id, "permissions": permissions})


@profile_bp.patch("/users/<user_id>")
@require_auth
@require_role("admin")
def update_user_profile_admin(user_id: str):
    """Update a user's profile (admin only)."""
    user_id = sanitize_str(user_id, 128)
    body = request.get_json(silent=True) or {}

    # Admin can update more fields
    allowed_fields = [
        "full_name", "bio", "avatar_url", "phone_number", "department",
        "title", "timezone", "language", "theme", "notifications_enabled",
        "email_notifications", "preferences", "is_verified", "profile_status",
        "permissions"
    ]

    updates = {k: v for k, v in body.items() if k in allowed_fields and v is not None}

    if not updates:
        return _err("No valid fields to update.", 400)

    try:
        updated_profile = ProfileService.update_user_profile(user_id, **updates)
        if not updated_profile:
            return _err("User not found.", 404)
        return _ok(updated_profile, message="User profile updated successfully.")
    except Exception as exc:
        return _err(f"Profile update failed: {exc}", 500)


@profile_bp.post("/users/<user_id>/verify")
@require_auth
@require_role("admin")
def verify_user_profile(user_id: str):
    """Verify a user profile (admin only)."""
    user_id = sanitize_str(user_id, 128)

    try:
        updated_profile = ProfileService.update_user_profile(user_id, is_verified=1)
        if not updated_profile:
            return _err("User not found.", 404)
        return _ok(updated_profile, message="User profile verified.")
    except Exception as exc:
        return _err(f"Verification failed: {exc}", 500)


@profile_bp.post("/users/<user_id>/suspend")
@require_auth
@require_role("admin")
def suspend_user_profile(user_id: str):
    """Suspend a user profile (admin only)."""
    user_id = sanitize_str(user_id, 128)
    current_uid = g.current_user.get("sub")
    if user_id == current_uid:
        return _err("You cannot deactivate your own administrator account.", 400)

    try:
        with get_db() as conn:
            user = row_to_dict(conn.execute(
                "SELECT id, role, is_active FROM users WHERE id = ?", (user_id,)
            ).fetchone())
            if not user:
                return _err("User not found.", 404)

            if user.get("role") in {"admin", "administrator"} and user.get("is_active"):
                admin_count = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role IN ('admin', 'administrator') AND is_active = 1"
                ).fetchone()[0]
                if admin_count <= 1:
                    return _err("Cannot deactivate the last active administrator.", 400)

            conn.execute(
                "UPDATE users SET is_active = 0, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
                (user_id,),
            )

        updated_profile = ProfileService.update_user_profile(user_id, profile_status="suspended")
        if not updated_profile:
            return _err("User not found.", 404)
        return _ok(updated_profile, message="User deactivated. They cannot log in until reactivated.")
    except Exception as exc:
        return _err(f"Suspension failed: {exc}", 500)


@profile_bp.post("/users/<user_id>/activate")
@require_auth
@require_role("admin")
def activate_user_profile(user_id: str):
    """Activate a suspended user profile (admin only)."""
    user_id = sanitize_str(user_id, 128)

    try:
        with get_db() as conn:
            user = row_to_dict(conn.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone())
            if not user:
                return _err("User not found.", 404)
            conn.execute(
                "UPDATE users SET is_active = 1, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
                (user_id,),
            )

        updated_profile = ProfileService.update_user_profile(user_id, profile_status="active")
        if not updated_profile:
            return _err("User not found.", 404)
        return _ok(updated_profile, message="User activated. They can log in now.")
    except Exception as exc:
        return _err(f"Activation failed: {exc}", 500)


@profile_bp.post("/users/<user_id>/role")
@require_auth
@require_role("admin")
def assign_user_role(user_id: str):
    """Assign a role to a user (admin only)."""
    user_id = sanitize_str(user_id, 128)
    body = request.get_json(silent=True) or {}
    new_role = sanitize_str(body.get("role", ""), 50).lower()

    if new_role not in {"admin", "registered", "guest"}:
        return _err("Invalid role. Must be one of: admin, registered, guest.", 400)

    try:
        with get_db() as conn:
            # Check if user exists
            user = row_to_dict(conn.execute(
                "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone())

            if not user:
                return _err("User not found.", 404)

            # Prevent demoting the last admin
            if user["role"] == "admin" and new_role != "admin":
                admin_count = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role IN ('admin', 'administrator') AND is_active = 1"
                ).fetchone()[0]
                if admin_count <= 1:
                    return _err("Cannot demote the last remaining admin.", 400)

            # Update the role
            conn.execute(
                "UPDATE users SET role = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
                (new_role, user_id),
            )

        # Update user profile with role-derived permissions and preferences.
        default_permissions = ProfileService.ROLE_PERMISSIONS[new_role]
        default_preferences = ProfileService.get_role_profile(new_role)["default_preferences"]
        ProfileService.update_user_profile(
            user_id,
            permissions=default_permissions,
            preferences=default_preferences,
        )

        return _ok({"user_id": user_id, "new_role": new_role}, message=f"User role updated to {new_role}.")
    except Exception as exc:
        return _err(f"Role assignment failed: {exc}", 500)
