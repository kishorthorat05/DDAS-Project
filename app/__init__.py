"""
DDAS Flask application factory.
Registers all blueprints, middleware, CORS, and error handlers.
"""
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from app.api.routes import (
    ai_bp, alert_bp, auth_bp, data_bp, monitor_bp, upload_bp, analytics_bp, export_bp, duplicates_bp
)
from app.models.database import init_db
from app.services.ai_service import is_api_configured
from app.services.monitor_service import start_monitor
from config.settings import get_config

def create_app(config_object=None) -> Flask:
    config_cls = config_object or get_config()
    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent.parent / "static"),
        template_folder=str(Path(__file__).parent.parent / "templates"),
    )

    # ── Config ────────────────────────────────────────────────────────────────
    app.config.from_object(config_cls)
    app.config["MAX_CONTENT_LENGTH"] = config_cls.MAX_CONTENT_LENGTH
    config_cls.init_dirs()
    if hasattr(config_cls, "validate"):
        config_cls.validate()

    # ── DB ────────────────────────────────────────────────────────────────────
    init_db()

    # ── Security headers ──────────────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' https://generativelanguage.googleapis.com;"
        )
        return response

    # ── CORS (manual, no flask-cors dependency) ───────────────────────────────
    @app.after_request
    def add_cors(response):
        origin = request_origin()
        allowed_origins = app.config.get("CORS_ORIGINS", [])
        if origin in allowed_origins or "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
            response.headers["Access-Control-Max-Age"] = "86400"
        return response

    @app.before_request
    def handle_preflight():
        from flask import request
        if request.method == "OPTIONS":
            return jsonify({}), 204

    # ── Blueprints ────────────────────────────────────────────────────────────
    for bp in (auth_bp, data_bp, upload_bp, alert_bp, monitor_bp, ai_bp, analytics_bp, export_bp, duplicates_bp):
        app.register_blueprint(bp)

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "healthy",
            "ai_configured": is_api_configured(),
            "monitor": "check /api/monitor/status",
        }), 200

    # ── SPA fallback — serve index.html for all non-API routes ────────────────
    @app.get("/")
    @app.get("/<path:path>")
    def spa(path: str = ""):
        # Don't intercept API calls
        if path.startswith("api/"):
            from functools import wraps
            @wraps(lambda: None)
            def noop():
                return jsonify({"error": "Not found"}), 404
            return noop()
        
        static_dir = Path(app.static_folder)  # type: ignore[arg-type]
        if path and (static_dir / path).exists():
            return send_from_directory(str(static_dir), path)
        return send_from_directory(str(static_dir), "index.html")

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found", "code": "NOT_FOUND"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify({"error": "Method not allowed", "code": "METHOD_NOT_ALLOWED"}), 405

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": "File too large (max 200 MB)", "code": "FILE_TOO_LARGE"}), 413

    @app.errorhandler(429)
    def rate_limited(_):
        return jsonify({"error": "Too many requests", "code": "RATE_LIMITED"}), 429

    @app.errorhandler(500)
    def internal(_):
        return jsonify({"error": "Internal server error", "code": "SERVER_ERROR"}), 500

    # ── Start background monitor ──────────────────────────────────────────────
    if app.config.get("START_MONITOR_ON_BOOT") and not app.config.get("TESTING"):
        def _start_monitor_delayed():
            time.sleep(2)
            start_monitor()

        t = threading.Thread(target=_start_monitor_delayed, daemon=True)
        t.start()

    return app


def request_origin() -> str:
    from flask import request
    return request.headers.get("Origin", "")
