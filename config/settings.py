"""
DDAS Configuration — environment-driven, secure defaults.
Copy .env.example to .env and fill in values before running.
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv(override=False)

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-secrets-token-hex-32")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-jwt-secret-too")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(days=30)

    # Allowed CORS origins (comma-separated in env)
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5000").split(",")

    # ── Storage ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'ddas.db'}")
    UPLOAD_FOLDER: Path = BASE_DIR / "data" / "uploads"
    MAX_CONTENT_LENGTH: int = 200 * 1024 * 1024  # 200 MB

    ALLOWED_EXTENSIONS: set[str] = {
        "csv", "tsv", "xlsx", "xls", "json", "xml",
        "txt", "pdf", "zip", "tar", "gz",
        "jpg", "jpeg", "png", "gif", "bmp", "webp",
        "nc", "h5", "hdf5", "geojson", "shp",
        "html", "htm",
    }

    # ── Monitoring ────────────────────────────────────────────────────────────
    MONITORED_DIR: str = os.getenv("MONITORED_DIR", str(Path.home() / "Downloads"))
    SCAN_INTERVAL_SECONDS: int = int(os.getenv("SCAN_INTERVAL", "5"))

    # ── AI (Google Generative AI) ────────────────────────────────────────────
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
    AI_MAX_TOKENS: int = 600

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATELIMIT_DEFAULT: str = "200 per day;50 per hour"
    RATELIMIT_UPLOAD: str = "20 per hour"
    RATELIMIT_CHAT: str = "60 per hour"

    # ── Hashing ───────────────────────────────────────────────────────────────
    HASH_ALGORITHM: str = "sha256"   # sha256 > md5 for production
    HASH_CHUNK_SIZE: int = 65536     # 64 KB chunks

    # ── Session ───────────────────────────────────────────────────────────────
    SESSION_COOKIE_SECURE: bool = os.getenv("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    @classmethod
    def init_dirs(cls) -> None:
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG: bool = True
    TESTING: bool = False


class ProductionConfig(Config):
    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = True

    @classmethod
    def validate(cls) -> None:
        """Raise on insecure production defaults."""
        if cls.SECRET_KEY.startswith("change-me"):
            raise RuntimeError("Set a real SECRET_KEY in production!")
        if cls.JWT_SECRET.startswith("change-jwt"):
            raise RuntimeError("Set a real JWT_SECRET in production!")


class TestingConfig(Config):
    TESTING: bool = True
    DATABASE_URL: str = "sqlite:///:memory:"
    UPLOAD_FOLDER: Path = Path(__file__).resolve().parent.parent / "data" / "test_uploads"


_ENV_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type[Config]:
    env = os.getenv("FLASK_ENV", "development")
    return _ENV_MAP.get(env, DevelopmentConfig)
