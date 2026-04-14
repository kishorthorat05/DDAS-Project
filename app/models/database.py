"""
Database models and schema management for DDAS.
Uses sqlite3 directly — no ORM overhead, keeps it lightweight.
"""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from config.settings import get_config


def _get_db_path() -> Path:
    db_url = get_config().DATABASE_URL
    if db_url.startswith("sqlite:///"):
        path = Path(db_url[len("sqlite:///"):])
    else:
        path = Path(db_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ─────────────────────────── connection helper ────────────────────────────────

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Thread-safe SQLite connection with WAL mode + foreign keys enabled."""
    conn = sqlite3.connect(str(_get_db_path()), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


# ─────────────────────────── schema ──────────────────────────────────────────

SCHEMA_SQL = """
-- Organizations / Teams
CREATE TABLE IF NOT EXISTS organizations (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    owner_id        TEXT NOT NULL,
    plan_tier       TEXT NOT NULL DEFAULT 'free',  -- free | pro | enterprise
    max_storage_gb  INTEGER DEFAULT 100,
    max_users       INTEGER DEFAULT 5,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Role definitions & permissions
CREATE TABLE IF NOT EXISTS roles (
    id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name        TEXT NOT NULL UNIQUE,  -- admin, owner, operator, viewer, auditor
    permissions TEXT NOT NULL,  -- JSON array: ["upload", "download", "delete", "share", "manage_team", etc.]
    is_system   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    username        TEXT UNIQUE NOT NULL,
    email           TEXT UNIQUE,
    password_hash   TEXT NOT NULL,
    organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    role_id         TEXT REFERENCES roles(id) ON DELETE SET NULL,
    role            TEXT DEFAULT 'viewer',   -- backward compat: admin | operator | viewer
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_login      TEXT,
    login_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role_id);

-- Registered datasets (enhanced with org, version, tags, compression)
CREATE TABLE IF NOT EXISTS datasets (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    organization_id     TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    file_hash           TEXT NOT NULL UNIQUE,
    file_name           TEXT NOT NULL,
    file_size           INTEGER NOT NULL DEFAULT 0,
    file_size_compressed INTEGER,  -- After compression
    file_path           TEXT NOT NULL,
    file_type           TEXT,
    user_id             TEXT REFERENCES users(id) ON DELETE SET NULL,
    user_name           TEXT NOT NULL DEFAULT 'System',
    period              TEXT,
    spatial_domain      TEXT,
    attributes          TEXT,   -- JSON blob
    description         TEXT,
    tags                TEXT,   -- JSON array: ["important", "frequently-used", etc.]
    version             INTEGER DEFAULT 1,
    is_latest_version   INTEGER DEFAULT 1,
    source_location     TEXT,  -- Local, AWS S3, GCS, Azure Blob, etc.
    cloud_uri           TEXT,  -- URI if stored in cloud
    compression_method  TEXT,  -- gzip, bzip2, zstd, none
    reuse_count         INTEGER DEFAULT 0,
    quality_score       REAL DEFAULT 0.0,  -- 0-1, based on metadata completeness
    download_timestamp  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_datasets_hash      ON datasets(file_hash);
CREATE INDEX IF NOT EXISTS idx_datasets_org       ON datasets(organization_id);
CREATE INDEX IF NOT EXISTS idx_datasets_user      ON datasets(user_id);
CREATE INDEX IF NOT EXISTS idx_datasets_file_type ON datasets(file_type);
CREATE INDEX IF NOT EXISTS idx_datasets_tags      ON datasets(tags);
CREATE INDEX IF NOT EXISTS idx_datasets_version   ON datasets(version);
CREATE INDEX IF NOT EXISTS idx_datasets_created   ON datasets(created_at DESC);

-- Dataset versions (version control)
CREATE TABLE IF NOT EXISTS dataset_versions (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    dataset_id      TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    file_hash       TEXT NOT NULL,
    file_size       INTEGER,
    file_size_compressed INTEGER,
    changes_summary TEXT,  -- What changed from previous version
    created_by      TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(dataset_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_versions_dataset ON dataset_versions(dataset_id);
CREATE INDEX IF NOT EXISTS idx_versions_hash    ON dataset_versions(file_hash);

-- Advanced similarity detection (fuzzy, near-duplicate)
CREATE TABLE IF NOT EXISTS similarity_results (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    file_hash_1     TEXT NOT NULL,
    file_hash_2     TEXT NOT NULL,
    similarity_score REAL NOT NULL,  -- 0.0 to 1.0 (0 = different, 1 = identical)
    algorithm       TEXT,  -- "cosine", "jaccard", "levenshtein", "ssdeep", etc.
    match_type      TEXT NOT NULL,  -- "exact", "fuzzy", "semantic"
    analysis_result TEXT,  -- JSON with details
    computed_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(file_hash_1, file_hash_2, algorithm)
);

CREATE INDEX IF NOT EXISTS idx_similarity_hash1 ON similarity_results(file_hash_1);
CREATE INDEX IF NOT EXISTS idx_similarity_hash2 ON similarity_results(file_hash_2);
CREATE INDEX IF NOT EXISTS idx_similarity_score ON similarity_results(similarity_score DESC);

-- Cloud storage integrations
CREATE TABLE IF NOT EXISTS cloud_integrations (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,  -- "aws_s3", "gcs", "azure_blob", "sftp", etc.
    name            TEXT NOT NULL,
    endpoint        TEXT,
    bucket_name     TEXT,
    access_key      TEXT,  -- encrypted
    secret_key      TEXT,  -- encrypted
    region          TEXT,
    is_active       INTEGER DEFAULT 1,
    sync_enabled    INTEGER DEFAULT 0,
    sync_interval_minutes INTEGER DEFAULT 60,
    last_sync       TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_cloud_org ON cloud_integrations(organization_id);

-- Performance metrics & analytics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id                      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    organization_id         TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    metric_date             TEXT NOT NULL,
    total_uploads           INTEGER DEFAULT 0,
    total_duplicates_found  INTEGER DEFAULT 0,
    duplicate_rate_percent  REAL,
    storage_saved_bytes     INTEGER DEFAULT 0,
    bandwidth_saved_bytes   INTEGER DEFAULT 0,
    average_file_size       INTEGER,
    total_datasets          INTEGER,
    unique_users            INTEGER,
    reuse_percentage        REAL,  -- % of data reused vs re-downloaded
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_metrics_org  ON performance_metrics(organization_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON performance_metrics(metric_date DESC);

-- Data sharing & collaboration
CREATE TABLE IF NOT EXISTS shared_datasets (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    dataset_id      TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    shared_by       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_with     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission      TEXT NOT NULL DEFAULT 'view',  -- view, download, comment, edit
    access_level    TEXT NOT NULL DEFAULT 'users',  -- users, team, organization, public
    expiry_date     TEXT,
    is_revoked      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_shared_dataset ON shared_datasets(dataset_id);
CREATE INDEX IF NOT EXISTS idx_shared_user    ON shared_datasets(shared_with);
CREATE INDEX IF NOT EXISTS idx_shared_by      ON shared_datasets(shared_by);

-- Team members (organization collaboration)
CREATE TABLE IF NOT EXISTS team_members (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         TEXT REFERENCES roles(id),
    joined_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_active       INTEGER DEFAULT 1,
    UNIQUE(organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_team_org  ON team_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_team_user ON team_members(user_id);

-- Data reuse recommendations
CREATE TABLE IF NOT EXISTS reuse_recommendations (
    id                      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id                 TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dataset_id              TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    recommendation_type     TEXT NOT NULL,  -- "duplicate", "similar", "relevant_metadata", "trending"
    reason                  TEXT NOT NULL,  -- Explanation for the recommendation
    confidence_score        REAL,  -- 0-1
    is_accepted             INTEGER DEFAULT 0,
    is_rejected             INTEGER DEFAULT 0,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_rec_user ON reuse_recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_rec_dataset ON reuse_recommendations(dataset_id);

-- Bandwidth optimization (delta, compression tracking)
CREATE TABLE IF NOT EXISTS bandwidth_optimization (
    id                      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    dataset_id              TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    optimization_method     TEXT NOT NULL,  -- "compression", "delta_sync", "chunking"
    original_size           INTEGER,
    optimized_size          INTEGER,
    compression_ratio       REAL,  -- original_size / optimized_size
    method_details          TEXT,  -- JSON with specifics (algo, level, etc.)
    applied_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_bw_dataset ON bandwidth_optimization(dataset_id);

-- User behavior & activity tracking
CREATE TABLE IF NOT EXISTS user_activity (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    activity_type   TEXT NOT NULL,  -- "download", "upload", "search", "share", "view"
    resource_type   TEXT,  -- "dataset", "report", "settings"
    resource_id     TEXT,
    details         TEXT,  -- JSON with additional context
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_org  ON user_activity(organization_id);
CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity(activity_type);
CREATE INDEX IF NOT EXISTS idx_activity_date ON user_activity(created_at DESC);

-- Download / scan history (enhanced)
CREATE TABLE IF NOT EXISTS download_history (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    dataset_id          TEXT REFERENCES datasets(id) ON DELETE SET NULL,
    organization_id     TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    user_id             TEXT REFERENCES users(id) ON DELETE SET NULL,
    user_name           TEXT NOT NULL DEFAULT 'System',
    file_name           TEXT,
    file_hash           TEXT,
    attempt_timestamp   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    action              TEXT NOT NULL DEFAULT 'download_attempt',
    status              TEXT NOT NULL DEFAULT 'success',   -- success | duplicate_detected | error
    ip_address          TEXT,
    bandwidth_saved     INTEGER,  -- bytes saved if reused
    is_reuse            INTEGER DEFAULT 0,  -- 1 if data was reused instead of re-downloaded
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_dataset    ON download_history(dataset_id);
CREATE INDEX IF NOT EXISTS idx_history_org        ON download_history(organization_id);
CREATE INDEX IF NOT EXISTS idx_history_user       ON download_history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_status     ON download_history(status);
CREATE INDEX IF NOT EXISTS idx_history_timestamp  ON download_history(attempt_timestamp DESC);

-- Enhanced Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id                      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    organization_id         TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    alert_type              TEXT NOT NULL DEFAULT 'duplicate',
    severity                TEXT NOT NULL DEFAULT 'warning',   -- info | warning | critical
    title                   TEXT NOT NULL,
    message                 TEXT NOT NULL,
    file_name               TEXT,
    file_hash               TEXT,
    file_path               TEXT,
    existing_dataset_id     TEXT REFERENCES datasets(id) ON DELETE SET NULL,
    triggered_by_user_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    similar_matches_count   INTEGER,  -- For near-duplicate alerts
    metadata TEXT,  -- JSON: who, where, when, action taken
    is_read                 INTEGER NOT NULL DEFAULT 0,
    is_actioned             INTEGER DEFAULT 0,
    action_taken            TEXT,  -- "reuse", "archive", "delete", etc.
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_org     ON alerts(organization_id);
CREATE INDEX IF NOT EXISTS idx_alerts_read    ON alerts(is_read);
CREATE INDEX IF NOT EXISTS idx_alerts_type    ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_user    ON alerts(triggered_by_user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);

-- Scan logs (enhanced)
CREATE TABLE IF NOT EXISTS scan_logs (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    organization_id     TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    file_path           TEXT NOT NULL,
    file_name           TEXT,
    file_size           INTEGER,
    file_hash           TEXT,
    is_duplicate        INTEGER NOT NULL DEFAULT 0,
    similar_count       INTEGER DEFAULT 0,  -- Near-duplicates found
    is_compressed       INTEGER DEFAULT 0,
    original_size       INTEGER,
    compressed_size     INTEGER,
    bandwidth_saved     INTEGER,
    scanned_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    error               TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_logs_org     ON scan_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_scan_logs_scanned ON scan_logs(scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_logs_hash    ON scan_logs(file_hash);
"""


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    db_path = _get_db_path()
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
    print(f"[DB] Initialized at {db_path}")
