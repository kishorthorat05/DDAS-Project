# DDAS Project Details

This document provides deep technical documentation for DDAS. It explains the actual project structure, entry points, modules, database schema, API behavior, hidden/partial features, function groups, and interconnections.

## 1. Project Overview

DDAS stands for Data Download Duplication Alert System. It is a Python/Flask web application with a static single-page frontend. The app helps users upload, register, scan, search, and analyze datasets while detecting duplicate files by cryptographic hash.

The project is intentionally lightweight:

- Flask is used instead of a larger backend framework.
- SQLite is used directly through `sqlite3`.
- The frontend is served as static HTML from Flask.
- Business logic is organized under `app/services`.
- Security helpers are centralized in `app/utils/security.py`.

## 2. Main Purpose

The main purpose is to prevent repeated downloads and storage waste. It does this by computing hashes for files, registering unique datasets, logging download/upload/scan activity, and alerting users when duplicates are detected.

## 3. Entry Points

| File | Role |
| --- | --- |
| `run.py` | Starts the Flask development server. Loads dotenv before importing the app. Prints LAN URLs. |
| `app/__init__.py` | Creates the Flask app, loads config, initializes database, registers blueprints, serves SPA, installs middleware and error handlers. |
| `static/index.html` | Browser UI and frontend JavaScript client. |
| `app/api/routes.py` | HTTP API surface for auth, datasets, uploads, alerts, monitor, AI, analytics, exports, duplicates, and profiles. |

## 4. Folder Structure and File Purposes

| Path | Purpose |
| --- | --- |
| `app/` | Main application package. |
| `app/api/routes.py` | Defines all Flask blueprints and endpoint handlers. |
| `app/models/database.py` | SQLite schema, connection context manager, profile helper queries. |
| `app/services/ai_service.py` | Gemini integration, file insights, chat action detection, fallback chat responses. |
| `app/services/analytics_service.py` | Dashboard, timeline, file-type distribution, user activity, top duplicate, system health metrics. |
| `app/services/cloud_service.py` | Optional cloud integration storage and upload helpers for S3/GCS/Azure/SFTP. |
| `app/services/collaboration_service.py` | Optional team, organization, sharing, and collaboration helpers. |
| `app/services/compression_service.py` | Compression, decompression, delta, and bandwidth optimization helpers. |
| `app/services/dataset_service.py` | Dataset CRUD, history, alerts, scan logs, duplicate grouping, directory/file duplicate scanning. |
| `app/services/export_service.py` | ZIP export creation, dataset export, duplicate summary, cleanup. |
| `app/services/metrics_service.py` | Performance metrics and reporting helpers. |
| `app/services/monitor_service.py` | watchdog monitor, manual scan, file processing pipeline. |
| `app/services/permission_service.py` | Role definitions and permission helpers. |
| `app/services/profile_service.py` | User profile enrichment, preferences, permissions, stats, role summary. |
| `app/services/recommendation_service.py` | Reuse recommendation logic based on duplicates, similarity, metadata, trending reuse. |
| `app/services/similarity_service.py` | Hash, filename, metadata similarity helpers. |
| `app/services/version_control_service.py` | Dataset version tracking, rollback, compare, cleanup helpers. |
| `app/utils/security.py` | JWT, auth decorators, password hashing, file hashing, sanitization, URL safety, rate limiter. |
| `config/settings.py` | Environment-based configuration classes. |
| `static/index.html` | Main UI, styles, auth flow, API client, page navigation, dashboards, profile/user management. |
| `static/components/DuplicateDetector.html` | Older/standalone duplicate detector component. |
| `tests/test_app_smoke.py` | End-to-end Flask route smoke tests. |
| `tests/test_security.py` | Unit tests for security utilities. |
| `test_rbac.py` | Manual HTTP RBAC test script using `requests`. |
| `test_gemini_direct.py` | Direct Gemini API connectivity test. |
| `requirements.txt` | Python dependencies. |
| `*.md` guides | Existing guides for features, deployment, duplicate detector, RBAC, chatbot, user profiles. |

## 5. Application Workflow

1. `run.py` loads `.env`, imports `create_app`, builds the Flask app, prints local/LAN URLs, and starts the server.
2. `create_app()` loads configuration, initializes runtime folders, initializes SQLite tables, registers blueprints, and serves `static/index.html`.
3. Browser loads the SPA.
4. User logs in, registers, or continues as guest.
5. Frontend stores auth data in browser storage and sends JWT bearer tokens to protected APIs.
6. Uploads/scans compute SHA-256 hashes.
7. Unique files become `datasets`; duplicate files create `alerts`, `download_history`, and `scan_logs`.
8. Dashboard, repository, history, analytics, duplicate detector, export, and profile pages fetch API data.
9. Admins can manage users from the profile page.

## 6. Backend Blueprints

| Blueprint | URL Prefix | Main Responsibility |
| --- | --- | --- |
| `auth_bp` | `/api/auth` | Register, login, guest profile, OTP, password change, current user |
| `data_bp` | `/api` | Dataset listing, search, filters, stats, detail, duplicate check |
| `upload_bp` | `/api` | Local file upload, URL upload/download |
| `alert_bp` | `/api` | Alert listing and read state |
| `monitor_bp` | `/api` | Manual scan, monitor lifecycle, scan logs, history |
| `ai_bp` | `/api/ai` | Chat, clear chat, AI status |
| `analytics_bp` | `/api/analytics` | Dashboard and analytics metrics |
| `export_bp` | `/api/export` | ZIP export, list, download, cleanup |
| `duplicates_bp` | `/api/duplicates` | Duplicate group queries and directory/name duplicate scans |
| `profile_bp` | `/api/profile` | Profile, avatar, role info, admin user management |

## 7. Database Usage

The app uses SQLite via `get_db()` in `app/models/database.py`.

### Connection Behavior

- `sqlite3.connect(..., check_same_thread=False, timeout=30)`.
- Row factory is `sqlite3.Row`.
- WAL mode is enabled.
- Foreign keys are enabled.
- Context manager commits on success and rolls back on exception.

### Tables

| Table | Purpose |
| --- | --- |
| `organizations` | Organization/team metadata. |
| `roles` | Role definitions and JSON permissions. |
| `users` | Login identity, password hash, role, active status, login counters. |
| `datasets` | Registered files and metadata. |
| `dataset_versions` | Dataset version records. |
| `similarity_results` | Cached similarity comparisons. |
| `cloud_integrations` | Optional cloud storage credential/config records. |
| `performance_metrics` | Aggregated daily metrics. |
| `shared_datasets` | Dataset sharing records. |
| `team_members` | Organization membership. |
| `reuse_recommendations` | Recommendation records. |
| `bandwidth_optimization` | Compression/bandwidth optimization records. |
| `user_activity` | Generic activity audit data. |
| `download_history` | Upload/download/scan activity history. |
| `alerts` | Duplicate and system alerts. |
| `user_profiles` | Profile details, preferences, permissions, stats. |
| `scan_logs` | File scan results. |

### Important Indexes

| Index | Why it matters |
| --- | --- |
| `idx_datasets_hash` | Fast duplicate lookup by hash. |
| `idx_datasets_user` | User-specific dataset lookup. |
| `idx_history_user` | User-scoped history. |
| `idx_history_timestamp` | Recent history ordering. |
| `idx_alerts_read` | Unread alert count. |
| `idx_scan_logs_scanned` | Recent scan activity. |
| `idx_scan_logs_hash` | Duplicate scan lookup by hash. |

## 8. Module Details

### `run.py`

Functions:

| Function | Purpose |
| --- | --- |
| `get_lan_ip()` | Opens a UDP socket to infer the LAN IP address for display. Falls back to `127.0.0.1`. |

Runtime behavior:

- Loads `.env`.
- Creates the Flask app.
- Prints local and network URLs.
- Runs Flask on `0.0.0.0:PORT`, default `8080`.
- Disables Flask reloader to avoid watchdog thread conflicts.

### `config/settings.py`

Classes:

| Class | Purpose |
| --- | --- |
| `Config` | Base settings for security, JWT, CORS, storage, monitoring, AI, rate limits, hashing, session cookies, and folder initialization. |
| `DevelopmentConfig` | Enables debug behavior. |
| `ProductionConfig` | Disables debug and validates secret defaults. |
| `TestingConfig` | Uses in-memory DB, testing mode, and disables monitor auto-start. |

Function:

| Function | Purpose |
| --- | --- |
| `get_config()` | Chooses config class from `FLASK_ENV`. |

### `app/__init__.py`

Function:

| Function | Purpose |
| --- | --- |
| `create_app(config_object=None)` | Creates the Flask app, configures logging, loads config, initializes directories and DB, installs security/CORS handlers, registers blueprints, exposes health and SPA fallback routes, optionally starts monitor. |
| `request_origin()` | Reads the request `Origin` header for CORS handling. |

Important behavior:

- Adds security headers: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, and CSP.
- Handles CORS manually.
- Serves `static/index.html` for non-API routes.
- Provides JSON error handlers.

### `app/api/routes.py`

This is the HTTP API layer. It imports service functions and converts requests into service calls.

Helper functions:

| Function | Purpose |
| --- | --- |
| `_config()` | Returns active config class. |
| `_ok()` | Standard success JSON response. |
| `_created()` | Standard created JSON response. |
| `_err()` | Standard error JSON response. |
| `_get_ip()` | Reads client IP from headers/request. |
| `_normalize_phone()` | Sanitizes phone values. |
| `_profile_avatar_folder()` | Ensures profile avatar folder exists. |
| `_is_allowed_avatar()` | Allows jpg/jpeg/png/gif/webp avatar uploads. |
| `_issue_otp()` | Creates an in-memory OTP entry. |
| `_verify_otp()` | Validates and consumes in-memory OTPs. |

Important endpoint groups:

| Endpoint | Method | Handler | Purpose |
| --- | --- | --- | --- |
| `/api/auth/register` | POST | `register` | Creates users; later admin requests become registered users if admin exists. |
| `/api/auth/login` | POST | `login` | Verifies password, updates login count, returns access/refresh tokens. |
| `/api/auth/request-otp` | POST | `request_otp` | Creates development OTP for mobile/password workflows. |
| `/api/auth/change-password` | POST | `change_password` | Changes password after verifying current password and OTP. |
| `/api/auth/guest` | POST | `guest_login` | Returns guest profile payload without DB login. |
| `/api/auth/me` | GET | `me` | Returns current authenticated user. |
| `/api/datasets` | GET | `get_datasets` | Lists datasets. |
| `/api/datasets/search` | GET | `search_datasets` | Searches dataset metadata. |
| `/api/datasets/stats` | GET | `dataset_stats` | Returns counts and size stats. |
| `/api/upload/file` | POST | `upload_file` | Saves local upload, hashes it, detects duplicate, logs history. |
| `/api/upload/url` | POST | `upload_from_url` | Downloads URL into upload folder and registers if unique. |
| `/api/alerts` | GET | `get_alerts` | Lists alerts and unread count. |
| `/api/monitor/scan` | POST | `trigger_scan` | Runs manual scan. |
| `/api/scan-logs` | GET | `get_scan_logs` | Returns recent scan logs. |
| `/api/history` | GET | `get_history` | Returns current user history, or all for admin with `scope=all`. |
| `/api/ai/chat` | POST | `chat_endpoint` | Processes chat message, action detection, Gemini/fallback response. |
| `/api/analytics/dashboard` | GET | `get_dashboard` | Returns dashboard metrics. |
| `/api/export/scan-results` | POST | `export_scan_results` | Creates ZIP export for scan results. |
| `/api/export/datasets` | POST | `export_datasets` | Creates dataset metadata export. |
| `/api/duplicates/all` | GET | `get_all_duplicates` | Returns duplicate groups. |
| `/api/duplicates/scan-directory` | POST | `scan_directory_for_duplicates` | Scans a directory for duplicate files. |
| `/api/profile/me` | GET/PATCH | `get_my_profile`, `update_my_profile` | Reads/updates profile. |
| `/api/profile/avatar` | POST | `upload_profile_avatar` | Uploads profile image. |
| `/api/profile/users` | GET | `get_all_users_profiles` | Admin user list. |
| `/api/profile/users/<id>/role` | POST | `assign_user_role` | Admin role assignment. |
| `/api/profile/users/<id>/suspend` | POST | `suspend_user_profile` | Admin deactivates user. |
| `/api/profile/users/<id>/activate` | POST | `activate_user_profile` | Admin reactivates user. |

### `app/models/database.py`

Functions:

| Function | Purpose |
| --- | --- |
| `_get_db_path()` | Resolves configured SQLite path and creates parent folder. |
| `get_db()` | Context manager for SQLite connection/commit/rollback. |
| `row_to_dict()` | Converts one SQLite row to dict. |
| `rows_to_list()` | Converts rows to list of dicts. |
| `init_db()` | Executes schema and performs lightweight role cleanup. |
| `create_user_profile()` | Creates default profile, permissions, and preferences for a user. |
| `get_user_profile()` | Reads profile by user ID. |
| `update_user_profile()` | Dynamic update of whitelisted profile columns at caller level. |
| `get_user_with_profile()` | Merges user row with profile row. |
| `get_all_user_profiles()` | Admin list of user profiles. |
| `get_profiles_by_role()` | Profile list by user role. |

### `app/utils/security.py`

Functions/classes:

| Item | Purpose |
| --- | --- |
| `create_access_token` | Creates JWT access token with expiry. |
| `create_refresh_token` | Creates JWT refresh token. |
| `decode_token` | Validates JWT. |
| `jwt_required` | Optional JWT parser; sets `g.current_user`. |
| `require_auth` | Requires valid authenticated user and checks live active status. |
| `require_role` | Restricts route to named roles. |
| `require_permission` | Restricts route by profile permission. |
| `hash_password`, `verify_password` | Password hashing and verification. |
| `hash_file`, `hash_bytes` | File/content hashing. |
| `is_allowed_extension` | Checks configured extension set. |
| `sanitize_filename` | Normalizes filename. |
| `validate_file_path` | Basic path validation. |
| `sanitize_str` | HTML-escapes and truncates text. |
| `sanitize_search_query` | Allows safe search characters. |
| `RateLimiter` | In-memory timestamp limiter. |
| `rate_limit` | Decorator for selected endpoints; explicitly bypasses login/register. |
| `is_safe_url` | Blocks malformed/private/loopback URLs. |

### `app/services/dataset_service.py`

Classes:

| Class | Purpose |
| --- | --- |
| `DatasetService` | Dataset CRUD, search, filtering, stats. |
| `HistoryService` | Records and reads download/upload/scan activity. |
| `AlertService` | Creates, reads, and updates alerts. |
| `ScanLogService` | Creates and reads scan logs. |
| `DuplicateService` | Duplicate grouping, file-hash lookup, directory scanning, filename search. |

Important logic:

- Datasets are unique by `file_hash`.
- Upload duplicates create history and alerts instead of another dataset row.
- Duplicate groups are generated by grouping datasets by hash.
- Directory scanning computes hashes and builds duplicate groups from file paths.

### `app/services/monitor_service.py`

Class:

| Class | Purpose |
| --- | --- |
| `_DDASEventHandler` | watchdog event handler for created/moved files. |

Functions:

| Function | Purpose |
| --- | --- |
| `_process_file()` | Computes hash, checks duplicates, creates alerts/history/datasets/scan logs. |
| `manual_scan()` | Iterates files in a directory and processes each. |
| `start_monitor()` | Starts watchdog observer. |
| `stop_monitor()` | Stops watchdog observer. |
| `monitor_status()` | Returns monitor state and watched directory. |

### `app/services/ai_service.py`

Functions:

| Function | Purpose |
| --- | --- |
| `_get_api_key`, `_get_model` | Reads Gemini configuration. |
| `_configure_client`, `_get_client`, `is_api_configured` | Google GenAI client setup/status. |
| `get_file_insights` | Generates insights for an uploaded file or falls back to rules. |
| `chat` | Sends message/history/context to Gemini; falls back if missing/error. |
| `execute_chat_action` | Runs supported project actions from chat commands. |
| `_tokenize_for_search` | Tokenizes user messages for project-context lookup. |
| `_extract_directory` | Extracts directory text from chat messages. |
| `_detect_chat_action` | Detects actions such as scan, monitor, stats, alerts, duplicates. |
| `_safe_read_text` | Reads bounded context files. |
| `_candidate_context_files` | Lists files used for project grounding. |
| `_extract_relevant_snippets` | Pulls matching snippets from code/docs. |
| `_fetch_live_project_state` | Reads live DB/project state for chatbot context. |
| `_build_chat_context` | Builds final system/project context string. |
| `_grounded_fallback_chat` | Rule-grounded fallback response. |
| `_rule_based_insights` | Fallback file insight generation. |

Hidden functionality:

- Chat can trigger safe actions such as manual scans, monitor status/start/stop, dashboard summary, system health, alerts summary, duplicate summary, and scan logs.
- Chat is grounded with snippets from project files and live DB stats.

### Other Service Modules

| Module | Implemented capabilities |
| --- | --- |
| `analytics_service.py` | Dashboard stats, timeline, file type distribution, user activity, top duplicates, health. |
| `export_service.py` | JSON/CSV/TXT reports in ZIP files, dataset export, duplicate summary, cleanup. |
| `permission_service.py` | Default permissions, role initialization, organization users, assign role, resource access check, activity logging. |
| `profile_service.py` | Role profiles, user profile enrichment, JSON preferences/permissions, stats, last-active. |
| `cloud_service.py` | Stores encrypted provider configs and uploads to AWS/GCS/Azure/SFTP when optional packages exist. |
| `collaboration_service.py` | Team invite, dataset share/revoke, team member management, org creation/statistics. |
| `compression_service.py` | gzip/bzip2/deflate compression, delta calculation, optimization records, recommendations. |
| `metrics_service.py` | Daily metrics, summaries, timeline, top datasets, user activity stats, JSON export. |
| `recommendation_service.py` | Reuse recommendations from similarity, metadata, trending reuse, user history. |
| `similarity_service.py` | Levenshtein, Jaccard, filename/metadata similarity, cached similarity results. |
| `version_control_service.py` | Dataset versions, rollback, compare, timeline, stats, cleanup. |

## 9. Frontend Details

Primary file: `static/index.html`.

### Pages

| Page ID | Purpose |
| --- | --- |
| `page-dashboard` | Stats, manual scan, recent scan activity. |
| `page-upload` | Upload file and metadata. |
| `page-repository` | Browse/search datasets. |
| `page-alerts` | Alert list and read actions. |
| `page-history` | Upload/scan/download history. |
| `page-ai-chat` | Chatbot UI. |
| `page-analytics` | Analytics metric cards. |
| `page-export` | Create/list/download exports. |
| `page-duplicates` | Duplicate groups and directory/name scanning. |
| `page-profile` | Profile, settings, admin user management. |

### UI/UX Components

- Auth modal with login/register/guest.
- Sidebar navigation with role-based visibility.
- Topbar role badge, alert badge, monitor status.
- Stat cards.
- Tables for repository/history/scan logs.
- Toast notifications.
- Progress bars.
- Duplicate group expandable panels.
- Chat bubbles and typing indicator.
- Profile avatar viewer modal.
- Admin user management table with role select and active toggle.

### Key Frontend Functions

| Function | Purpose |
| --- | --- |
| `api` | Fetch wrapper adding JSON and Authorization headers. |
| `doLogin`, `doRegister`, `skipAuth`, `logout`, `showApp` | Auth UI flow. |
| `setVisibilityByRole`, `updateNavVisibility`, `updateRoleBadge` | RBAC UI behavior. |
| `navigate` | Page switching and lazy data loading. |
| `loadDashboard`, `loadScanLogs`, `triggerScan` | Dashboard and scan behavior. |
| `doFileUpload`, `showUploadResult` | Upload workflow. |
| `loadRepository`, `debounceSearch`, `doSearch` | Repository list/search. |
| `loadAlerts`, `markRead`, `markAllRead` | Alert workflow. |
| `loadHistory` | History table. |
| `sendChat`, `clearChat`, `appendChatBubble` | Chat workflow. |
| `loadAnalytics` | Analytics cards. |
| `loadProfilePage`, `saveProfileSettings`, `uploadProfileAvatarIfSelected` | Profile workflow. |
| `loadUserManagement`, `updateManagedUserRole`, `toggleManagedUserStatus` | Admin user management. |
| `loadDuplicateDetector`, `startSystemScan`, `startFilenameDuplicateSearch`, `filterDuplicates` | Duplicate detector workflow. |
| `loadAvailableExports`, `downloadFile`, `cleanupOldExports` | Export workflow. |
| `fmtBytes`, `fmtDate`, `esc`, `renderMarkdown`, `toast` | Shared utilities. |

## 10. Important Algorithms and Logic

| Logic | Location | Details |
| --- | --- | --- |
| SHA-256 duplicate detection | `security.hash_file`, upload/scan services | Hash entire file in chunks; duplicate if hash exists. |
| Directory scan | `monitor_service.manual_scan`, `DuplicateService.scan_directory_for_duplicates` | Iterates files, hashes them, groups by hash. |
| Alert creation | `AlertService.create`, monitor/upload flows | Duplicate detection creates warning alerts. |
| JWT auth | `security.py` | Access and refresh token creation/decoding. |
| Live active-user check | `require_auth` | Reads DB on every authenticated request to reject inactive accounts. |
| Filename similarity | `similarity_service.analyze_filename_similarity` | Tokenizes names and uses Jaccard similarity. |
| Levenshtein hash similarity | `similarity_service.levenshtein_distance` | Detects near strings, though hash-nearness is limited as a semantic proxy. |
| Metadata similarity | `similarity_service.analyze_metadata_similarity` | Weighted score from size/type/period/domain/tags. |
| Compression recommendation | `compression_service.recommend_compression_method` | Chooses method by size and type. |
| AI action detection | `ai_service._detect_chat_action` | Regex/phrase detection for supported project actions. |

## 11. Error Handling

- API uses `_err(message, status, code)` for consistent JSON failures.
- DB context manager rolls back on exceptions.
- Upload and export handlers catch exceptions and return JSON.
- AI service falls back to grounded/rule-based responses on missing key or API failure.
- Cloud upload helpers catch provider exceptions and return `False`.
- Frontend `api()` catches fetch errors and returns `{success:false}`.
- Toasts show user-facing errors.
- Flask app registers JSON error handlers for 404, 405, 413, 429, and 500.

## 12. Security Implementations

- Password hashing via Werkzeug PBKDF2.
- JWT access and refresh tokens.
- Role and permission decorators.
- Live DB active-status checks for authenticated users.
- Input sanitization for strings/search/filenames.
- URL validation blocks loopback/private addresses.
- Allowed extension checks for uploads.
- Avatar type whitelist.
- Security headers and CSP.
- CORS allow-list from config.
- SQLite parameterized queries are used broadly.
- Cloud secrets are encrypted where possible, though current fallback key is not production-safe.

## 13. Performance Optimizations

- SQLite WAL mode.
- Indexed hash, user, timestamp, role, alert, and scan columns.
- Chunked file hashing.
- Scan/export limits on API list sizes.
- Frontend search debounce.
- Bounded AI history and bounded file snippet reads.
- Optional compression/bandwidth modules.

## 14. Dependencies

See `requirements.txt`.

Required runtime:

- Flask
- Werkzeug
- PyJWT
- cryptography
- requests
- watchdog
- google-genai
- python-dotenv
- pandas
- openpyxl
- zstandard

Dev/test:

- pytest
- pytest-flask

Optional:

- gunicorn
- boto3
- google-cloud-storage
- azure-storage-blob
- paramiko

## 15. Installation and Setup

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Optional `.env`:

```env
FLASK_ENV=development
PORT=8080
SECRET_KEY=change-me
JWT_SECRET=change-me-too
GOOGLE_API_KEY=
GOOGLE_MODEL=gemini-2.5-flash
START_MONITOR_ON_BOOT=false
```

## 16. Execution Flow

1. `run.py` loads `.env`.
2. `create_app()` configures Flask.
3. Config initializes `data/`, `data/uploads/`, `data/profile_avatars/`, `logs/`.
4. `init_db()` creates tables.
5. Blueprints are registered.
6. Browser requests `/`.
7. SPA loads and calls APIs.
8. API handlers call services.
9. Services use DB helpers and filesystem utilities.
10. JSON responses update the UI.

## 17. Hidden or Partial Functionalities

The following are present in code but not fully exposed in the main UI:

- Cloud storage integrations.
- Team collaboration and sharing.
- Compression optimization and bandwidth reports.
- Recommendation engine.
- Similarity result caching.
- Dataset version control.
- Advanced metrics export.
- Manual RBAC test script.
- Direct Gemini test script.

## 18. Unused or Duplicate Code

| Item | Observation |
| --- | --- |
| `static/components/DuplicateDetector.html` | Appears to be an older standalone component; main UI now implements duplicate detector logic directly in `static/index.html`. |
| Multiple guide Markdown files | Useful but overlapping; README/PROJECT_DETAILS/FUNCTIONALITIES/ARCHITECTURE should be treated as the current consolidated docs. |
| `metrics_service.py` vs `analytics_service.py` | Overlapping metric responsibilities; analytics is exposed through routes, metrics is mostly support/future code. |
| `permission_service.py` and `profile_service.py` permissions | Both define role/permission concepts; profile permissions are used by `require_permission`. |
| Optional cloud/collaboration/version/recommendation modules | Implemented service helpers but not fully wired to frontend routes. |
| Runtime DB files and logs | `data/*.db`, `logs/*.log`, profile avatars are runtime artifacts, not source code. |

## 19. Known Issues and Limitations

- SQLite can lock under heavier concurrent writes.
- No formal migration system.
- Frontend is a large single file.
- Some documents and services describe aspirational features not fully wired in the UI.
- Rate limiting is in-memory and resets on process restart.
- OTP storage is in-memory and development-oriented.
- Cloud encryption fallback key is not production-safe.
- File monitor only handles created/moved events and uses non-recursive observer.
- Directory scans can be slow for large folders because work runs synchronously.
- Admin registration is intentionally restricted after the first admin; subsequent users should be promoted by an admin.

## 20. Future Improvements

- Add Alembic-style migrations or a custom migration table.
- Use PostgreSQL for production.
- Split frontend into modules/components.
- Add OpenAPI/Swagger docs.
- Add background jobs for long scans/exports.
- Add WebSocket/SSE scan progress.
- Add better per-organization scoping across all endpoints.
- Add audit logs for admin actions.
- Add CSRF strategy if cookie auth is introduced.
- Add refresh-token lifecycle in frontend.
- Add structured logging.
- Add full UI for cloud, collaboration, recommendations, compression, and versioning.

## 21. File Interconnections

```text
run.py
  -> app.create_app()
      -> config.settings.get_config()
      -> app.models.database.init_db()
      -> app.api.routes blueprints
          -> app.services.*
          -> app.utils.security decorators/helpers
      -> static/index.html served as SPA

static/index.html
  -> fetch('/api/...') through api()
      -> routes.py handlers
          -> services
              -> database.py get_db()
              -> data/uploads, data/profile_avatars, uploads/exports
```

The codebase is organized so that `routes.py` owns HTTP concerns, service modules own business logic, and `database.py` owns SQLite access and schema creation.
