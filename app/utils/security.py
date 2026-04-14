"""
Security utilities for DDAS.
Covers: JWT tokens, password hashing (bcrypt), input sanitization,
file extension validation, and IP extraction.
"""
import hashlib
import hmac
import html
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import jwt
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from config.settings import get_config


def _config():
    return get_config()

# ─────────────────────────── JWT helpers ─────────────────────────────────────

def create_access_token(payload: dict[str, Any]) -> str:
    """Issue a short-lived JWT access token."""
    now = int(time.time())
    data = {
        **payload,
        "iat": now,
        "exp": now + int(_config().JWT_ACCESS_TOKEN_EXPIRES.total_seconds()),
        "type": "access",
    }
    config = _config()
    return jwt.encode(data, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    now = int(time.time())
    data = {
        "sub": user_id,
        "iat": now,
        "exp": now + int(_config().JWT_REFRESH_TOKEN_EXPIRES.total_seconds()),
        "type": "refresh",
    }
    config = _config()
    return jwt.encode(data, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    config = _config()
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])


# ─────────────────────────── Auth decorator ──────────────────────────────────

def jwt_required(f: Callable) -> Callable:
    """
    Decorator: validates Bearer token from Authorization header.
    Sets g.current_user = decoded payload.
    Allows anonymous access if token missing (g.current_user = None) — 
    use require_auth() for strictly protected routes.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        g.current_user = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                g.current_user = decode_token(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired", "code": "TOKEN_EXPIRED"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token", "code": "TOKEN_INVALID"}), 401
        return f(*args, **kwargs)
    return wrapper


def require_auth(f: Callable) -> Callable:
    """Strictly requires a valid JWT — returns 401 if missing."""
    @wraps(f)
    @jwt_required
    def wrapper(*args, **kwargs):
        if g.current_user is None:
            return jsonify({"error": "Authentication required", "code": "AUTH_REQUIRED"}), 401
        return f(*args, **kwargs)
    return wrapper


def require_role(*roles: str) -> Callable:
    """Restrict endpoint to specific roles (admin, operator, viewer)."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @require_auth
        def wrapper(*args, **kwargs):
            user_role = g.current_user.get("role", "viewer")
            if user_role not in roles:
                return jsonify({"error": "Insufficient permissions", "code": "FORBIDDEN"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────── Password ────────────────────────────────────────

def hash_password(plain: str) -> str:
    return generate_password_hash(plain, method="pbkdf2:sha256:600000")


def verify_password(plain: str, hashed: str) -> bool:
    return check_password_hash(hashed, plain)


# ─────────────────────────── File hashing ────────────────────────────────────

def hash_file(file_path: str | Path, algorithm: str | None = None) -> str:
    """Compute file hash (sha256 by default). Returns hex digest."""
    config = _config()
    algo = algorithm or config.HASH_ALGORITHM
    h = hashlib.new(algo)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(config.HASH_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes, algorithm: str | None = None) -> str:
    algo = algorithm or _config().HASH_ALGORITHM
    return hashlib.new(algo, data).hexdigest()


# ─────────────────────────── File validation ─────────────────────────────────

_DANGEROUS_PATTERNS = re.compile(
    r"\.\.(\\|/)|<script|javascript:|data:text/html",
    re.IGNORECASE,
)


def is_allowed_extension(filename: str) -> bool:
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in _config().ALLOWED_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """Remove path separators and dangerous characters from a filename."""
    name = Path(filename).name          # strip any directory component
    name = re.sub(r"[^\w\s.\-]", "_", name)
    name = name.strip(". ")
    return name or "upload"


def validate_file_path(path: str) -> bool:
    """Ensure path doesn't try to escape upload directory."""
    return not bool(_DANGEROUS_PATTERNS.search(path))


# ─────────────────────────── Input sanitization ──────────────────────────────

def sanitize_str(value: Any, max_length: int = 500) -> str:
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    return html.escape(value.strip())[:max_length]


def sanitize_search_query(query: str) -> str:
    """Strip SQL metacharacters from search input."""
    return re.sub(r"[%;\"'\\]", "", query.strip())[:200]


# ─────────────────────────── In-memory rate limiter ──────────────────────────

class RateLimiter:
    """
    Simple sliding-window rate limiter backed by an in-memory dict.
    For production with multiple workers, swap for Redis-backed flask-limiter.
    """
    def __init__(self) -> None:
        self._store: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        timestamps = self._store[key]
        # Prune old entries
        self._store[key] = [t for t in timestamps if t > cutoff]
        if len(self._store[key]) >= max_requests:
            return False
        self._store[key].append(now)
        return True


_rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 30, window_seconds: int = 60, key_fn: Callable | None = None):
    """Decorator: rate-limit a route per IP (or custom key)."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            key = key_fn(request) if key_fn else f"{f.__name__}:{ip}"
            if not _rate_limiter.is_allowed(key, max_requests, window_seconds):
                return jsonify({
                    "error": "Rate limit exceeded. Please slow down.",
                    "code": "RATE_LIMITED",
                    "retry_after": window_seconds,
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────── Secure URL validator ────────────────────────────

_SAFE_URL_PATTERN = re.compile(
    r'^https?://'
    r'(?!(?:localhost|127\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.))'  # block private IPs
    r'[^\s<>"{}|\\^`\[\]]+$',
    re.IGNORECASE,
)


def is_safe_url(url: str) -> bool:
    """Reject private/loopback IPs and obviously malformed URLs."""
    return bool(_SAFE_URL_PATTERN.match(url.strip()))
