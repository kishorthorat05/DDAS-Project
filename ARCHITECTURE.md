# DDAS Architecture

## 1. High-Level Architecture

```text
Browser SPA
  static/index.html
      |
      | fetch JSON / multipart
      v
Flask API
  app/api/routes.py
      |
      | calls
      v
Service Layer
  app/services/*.py
      |
      | get_db()
      v
SQLite Database
  data/ddas.db

Filesystem
  data/uploads/
  data/profile_avatars/
  data/uploads/exports/
  configured monitored directory
```

## 2. Runtime Boot Sequence

```text
run.py
  load .env
  create_app()
    load config
    initialize folders
    initialize DB schema
    register blueprints
    install middleware and error handlers
    optionally start monitor
  app.run()
```

## 3. Layer Responsibilities

| Layer | Files | Responsibility |
| --- | --- | --- |
| Entry | `run.py` | Launch development server. |
| App factory | `app/__init__.py` | Configure Flask and register routes. |
| API | `app/api/routes.py` | Parse HTTP input, auth checks, call services, return JSON. |
| Services | `app/services/*.py` | Business logic. |
| Models/DB | `app/models/database.py` | Schema and direct database helpers. |
| Security | `app/utils/security.py` | JWT, hashing, sanitization, decorators. |
| Frontend | `static/index.html` | UI rendering and API calls. |
| Tests | `tests/*.py` | Verification and regression coverage. |

## 4. Request Flow Examples

### Login

```text
User submits login form
  -> static/index.html doLogin()
  -> POST /api/auth/login
  -> routes.login()
  -> verify_password()
  -> update users.last_login/login_count
  -> ProfileService.get_user_profile_data()
  -> create_access_token()
  -> JSON response
  -> frontend stores token/user and shows app
```

### File Upload

```text
User selects file
  -> frontend builds FormData
  -> POST /api/upload/file
  -> require_permission("upload")
  -> save file to upload folder
  -> hash_file()
  -> DatasetService.get_by_hash()
    if exists:
      HistoryService.log()
      AlertService.create()
      delete uploaded duplicate
    else:
      DatasetService.create()
      HistoryService.log()
      get_file_insights()
  -> JSON response
  -> frontend updates dashboard/repository
```

### Manual Scan

```text
User clicks Manual Scan
  -> POST /api/monitor/scan
  -> require_auth()
  -> monitor_service.manual_scan()
  -> _process_file() for each file
  -> hash_file()
  -> DatasetService.get_by_hash()
  -> DatasetService.create() or AlertService.create()
  -> ScanLogService.log()
  -> HistoryService.log()
  -> JSON response
```

### Duplicate Detector Directory Scan

```text
User enters directory
  -> POST /api/duplicates/scan-directory
  -> require_permission("run_scanner")
  -> DuplicateService.scan_directory_for_duplicates()
  -> iterate files recursively if requested
  -> hash files
  -> group files by hash
  -> return duplicate groups and storage stats
```

### AI Chat

```text
User sends message
  -> POST /api/ai/chat
  -> route checks role/permission
  -> execute_chat_action()
      if action detected: run supported service function
      else: ai_service.chat()
  -> Gemini API if configured
  -> fallback response if not configured/error
  -> save bounded session history
```

## 5. Data Model Relationships

```text
users 1---1 user_profiles
users 1---N datasets
users 1---N download_history
datasets 1---N download_history
datasets 1---N alerts
datasets 1---N dataset_versions
datasets 1---N shared_datasets
datasets 1---N reuse_recommendations
datasets 1---N bandwidth_optimization
organizations 1---N users
organizations 1---N datasets
organizations 1---N team_members
```

Some relationships are optional because many rows allow `NULL` foreign keys for system scans and legacy data.

## 6. Authentication and Authorization Architecture

### JWT

- Access token includes `sub`, `username`, `role`, `iat`, `exp`, and `type`.
- Refresh token includes `sub`, `iat`, `exp`, and `type`.
- `jwt_required` parses token if present.
- `require_auth` requires a token and validates the user still exists and is active.

### Roles

| Role | Backend meaning |
| --- | --- |
| `guest` | Limited read-only profile returned by guest endpoint. |
| `registered` | Normal authenticated role with upload/export/AI/scanner permissions. |
| `admin` | Full access; role checks and permission checks pass. |

### Decorators

| Decorator | Purpose |
| --- | --- |
| `jwt_required` | Optional auth; route can be used by guests/public users. |
| `require_auth` | Requires authenticated active user. |
| `require_role` | Requires one of the named roles. |
| `require_permission` | Requires profile permission or admin. |
| `rate_limit` | In-memory limiter for selected endpoints; bypasses auth register/login. |

## 7. API Architecture

The API is organized by Flask blueprints, but all route functions live in `app/api/routes.py`. This is simple for a small project but can grow large.

Recommended future split:

```text
app/api/auth_routes.py
app/api/dataset_routes.py
app/api/upload_routes.py
app/api/monitor_routes.py
app/api/profile_routes.py
app/api/export_routes.py
```

## 8. Frontend Architecture

The frontend is currently one static HTML file with:

- CSS variables and component styles.
- Auth overlay.
- Sidebar/topbar shell.
- Multiple page sections.
- Inline JavaScript functions.
- Fetch-based API client.
- Role-based DOM visibility.
- Toasts and dynamic HTML rendering.

This keeps setup simple but creates maintenance pressure as features grow.

## 9. Database Architecture

The database is initialized by executing a large SQL string in `database.py`.

Advantages:

- Simple startup.
- No external DB server.
- Easy local development.

Tradeoffs:

- No migrations.
- Schema changes must be handled manually.
- SQLite concurrency limitations.
- Runtime DB file should not be treated as source.

## 10. Filesystem Architecture

| Folder | Purpose |
| --- | --- |
| `data/uploads` | Uploaded/downloaded datasets. |
| `data/profile_avatars` | User profile avatar images. |
| `data/uploads/exports` | Generated ZIP exports. |
| `logs` | Application and server logs. |
| `downloads` | Present in workspace; not central in current app flow. |

## 11. Security Architecture

Security controls:

- Password hashing, not plaintext storage.
- JWT bearer auth.
- Active-user DB check on authenticated requests.
- Role and permission decorators.
- Sanitized strings and filenames.
- Parameterized SQL.
- Upload extension allow-list from config.
- URL safety check for URL downloads.
- Security headers and CSP.
- CORS allow-list.

Security limitations:

- JWT storage in browser storage can be exposed by XSS.
- CSP allows inline scripts/styles because frontend is inline.
- OTP store is in-memory and development-oriented.
- Rate limiter is in-memory.
- SQLite DB and uploaded files are local filesystem assets.
- Cloud secret encryption fallback is not production-grade.

## 12. Performance Architecture

Optimizations:

- SQLite WAL mode.
- Indexes on hashes, timestamps, users, alerts, scan logs.
- Chunked file hashing.
- Bounded list limits.
- Bounded AI context and chat history.
- Debounced frontend search.

Potential bottlenecks:

- Synchronous scans.
- Synchronous exports.
- Large single frontend file.
- SQLite write contention.
- Directory scan memory usage for very large scans.

## 13. Import and Dependency Flow

```text
routes.py
  imports services:
    ai_service
    dataset_service
    monitor_service
    export_service
    analytics_service
    profile_service
  imports security decorators/helpers
  imports database helpers

services
  import database helpers
  import security hash helpers where needed
  import config where filesystem/config is needed

app/__init__.py
  imports routes, init_db, monitor start, config
```

## 14. Error Handling Architecture

Backend:

- Route handlers return `_err`.
- App-level error handlers return JSON.
- DB context manager rolls back.
- Service helpers catch provider/file errors where appropriate.
- AI falls back gracefully.

Frontend:

- `api()` wraps fetch errors.
- Pages render empty states on failure.
- Toasts show success/error feedback.
- Buttons are disabled during long actions.

## 15. Testing Architecture

`tests/test_app_smoke.py` uses Flask `test_client` with a custom test config.

Coverage areas:

- Public health.
- Protected routes.
- Guest access.
- Auth flow.
- Admin registration.
- History scoping.
- Scan log scoping.
- Analytics storage/duplicate bytes.
- Dataset detail history.
- File upload.
- Profile update/password change.
- Upload file type behavior.
- Export downloads.
- Monitor auto-start behavior.

`tests/test_security.py` covers utility functions.

## 16. Deployment Architecture

Development:

```powershell
python run.py
```

Production recommendation:

- Use `gunicorn` or another WSGI server.
- Use a real reverse proxy.
- Use secure `SECRET_KEY` and `JWT_SECRET`.
- Consider PostgreSQL.
- Disable debug.
- Use HTTPS.
- Configure strict CORS.
- Move long tasks to workers.

## 17. Known Architectural Issues

| Issue | Impact |
| --- | --- |
| Large `routes.py` | Harder to maintain as API grows. |
| Large `static/index.html` | Harder frontend maintenance and testing. |
| No migrations | Schema evolution can be fragile. |
| Many service modules are not fully exposed | Feature expectations can exceed UI/API behavior. |
| In-memory OTP/rate/chat sessions | Lost on restart and not horizontally scalable. |
| SQLite local DB | Limited production concurrency. |
| Inline scripts/styles | CSP must allow inline code. |

## 18. Recommended Refactor Roadmap

1. Add migrations.
2. Split routes by domain.
3. Split frontend into modules.
4. Add OpenAPI generation.
5. Add background task queue for scans/exports.
6. Move chat sessions/OTP/rate limits to Redis.
7. Add organization-aware authorization across every data query.
8. Add structured audit logging.
9. Add integration tests for every blueprint.
10. Add deployment profile with gunicorn and production config.
