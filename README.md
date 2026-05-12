# DDAS - Data Download Duplication Alert System

DDAS is a Flask-based web application for registering datasets, detecting duplicate downloads/files, monitoring a local folder, viewing analytics, managing user profiles, and interacting with an AI assistant. It is designed for teams that repeatedly download or collect data and need a lightweight way to prevent redundant storage and track reuse.

## Project Overview

| Item | Details |
| --- | --- |
| Application type | Flask single-page web application |
| Frontend | Static HTML/CSS/JavaScript in `static/index.html` |
| Backend | Python Flask blueprints in `app/api/routes.py` |
| Database | SQLite through direct `sqlite3` helpers |
| AI provider | Google Gemini through `google-genai` |
| Main entry point | `run.py` |
| App factory | `app/__init__.py:create_app` |
| Default port | `8080` |

## Main Purpose

The system helps users avoid duplicate data downloads by:

- hashing uploaded or scanned files;
- registering unique datasets;
- creating alerts when duplicate files are found;
- showing scan history, duplicate groups, and analytics;
- allowing admins to manage users, roles, and active/inactive status;
- offering an AI chatbot that can answer project/system questions and run supported actions.

## Core Features

- User registration, login, guest access, and profile management.
- Role-based access for `guest`, `registered`, and `admin`.
- Admin user management with role assignment and active status toggles.
- Dataset upload with metadata fields.
- Duplicate detection by SHA-256 hash.
- Manual scan and watchdog-based directory monitoring.
- Alerts for duplicate detections.
- Scan logs and per-user history.
- Dataset repository browsing and searching.
- Analytics dashboard for dataset count, duplicate rate, storage, bandwidth saved, active users, and alerts.
- Export ZIP generation for scan results and dataset metadata.
- Duplicate detector UI for hash groups, directory scanning, and filename search.
- AI chatbot using Google Gemini when configured, with rule-based fallback behavior.
- Profile photo upload and profile settings.
- Optional service modules for cloud integrations, collaboration, compression, recommendations, metrics, similarity, and version control.

## Technologies

| Area | Technology |
| --- | --- |
| Web framework | Flask, Werkzeug |
| Auth | PyJWT, Werkzeug password hashing |
| Database | SQLite, direct SQL |
| Monitoring | watchdog |
| AI | google-genai |
| HTTP client | requests |
| Config | python-dotenv |
| Data processing | pandas, openpyxl |
| Compression | gzip, bz2, zlib, optional zstandard |
| Testing | pytest, pytest-flask |
| Optional cloud | boto3, google-cloud-storage, azure-storage-blob, paramiko |

## Folder Structure

```text
ddas/
  app/
    __init__.py                 Flask app factory, middleware, blueprint registration
    api/routes.py               All HTTP API endpoints
    models/database.py          SQLite schema and DB helper functions
    services/                   Business logic services
    utils/security.py           JWT, password, sanitization, rate-limit helpers
  config/
    settings.py                 Environment-driven configuration
  static/
    index.html                  Main SPA UI
    components/DuplicateDetector.html
  tests/
    test_app_smoke.py           Flask integration smoke tests
    test_security.py            Security utility tests
  data/
    ddas.db                     Local SQLite database
    uploads/                    Runtime upload folder, created by config
    profile_avatars/            Uploaded profile images
  logs/
    ddas.log                    Runtime app log
  run.py                        Development server entry point
  requirements.txt              Python dependencies
  README.md                     This overview
  PROJECT_DETAILS.md            Deep technical documentation
  FUNCTIONALITIES.md            Feature-by-feature documentation
  ARCHITECTURE.md               Architecture and data-flow documentation
```

## Installation

1. Create and activate a virtual environment.

```powershell
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` if needed.

```powershell
copy .env.example .env
```

4. Optional: set AI and security values in `.env`.

```env
SECRET_KEY=change-this
JWT_SECRET=change-this-too
GOOGLE_API_KEY=your-gemini-key
GOOGLE_MODEL=gemini-2.5-flash
```

## Running

```powershell
python run.py
```

Open:

```text
http://localhost:8080
```

The application prints LAN URLs as well, so another device on the same network can open the app if firewall/network rules allow it.

## Testing

```powershell
pytest
```

Useful test files:

- `tests/test_app_smoke.py` covers app routes, auth, upload, history scoping, scan logs, analytics, export, profile, and monitor behavior.
- `tests/test_security.py` covers hashing, filename validation, sanitization, URL safety, password hashing, JWT, and rate limiter behavior.

## API Summary

| Group | Prefix | Purpose |
| --- | --- | --- |
| Auth | `/api/auth` | Register, login, guest, OTP, password change, current user |
| Datasets | `/api` | Dataset listing, search, filters, stats, details, duplicate check |
| Upload | `/api/upload` | File upload and URL download |
| Alerts | `/api/alerts` | List and mark duplicate/system alerts |
| Monitor | `/api/monitor`, `/api/scan-logs`, `/api/history` | Manual scan, monitor start/stop/status, scan logs, history |
| AI | `/api/ai` | Chat, clear chat, AI status |
| Analytics | `/api/analytics` | Dashboard, timeline, file types, user activity, top duplicates, system health |
| Export | `/api/export` | Generate, list, download, cleanup ZIP exports |
| Duplicates | `/api/duplicates` | Duplicate groups, stats, scan directory, filename search |
| Profile | `/api/profile` | User profile, avatar, roles, admin user management |

## Database

The schema is created in `app/models/database.py` at startup. The primary runtime tables are:

- `users`
- `user_profiles`
- `datasets`
- `download_history`
- `scan_logs`
- `alerts`
- `roles`

Additional tables support planned or partial features:

- `organizations`
- `dataset_versions`
- `similarity_results`
- `cloud_integrations`
- `performance_metrics`
- `shared_datasets`
- `team_members`
- `reuse_recommendations`
- `bandwidth_optimization`
- `user_activity`

## Documentation Set

- `README.md`: concise project documentation and setup.
- `PROJECT_DETAILS.md`: detailed file/module/function/class documentation.
- `FUNCTIONALITIES.md`: user-facing and backend feature guide.
- `ARCHITECTURE.md`: architecture, workflow, data flow, security, and limitations.

## Known Limitations

- SQLite is suitable for local/development use but not ideal for high-concurrency production workloads.
- Several advanced service modules are present but not exposed through full UI/API workflows.
- Cloud integrations need optional provider packages and real credentials.
- The frontend is a large single HTML file, which makes maintenance harder over time.
- The AI assistant depends on `GOOGLE_API_KEY`; without it the project falls back to rule-based responses.

## Future Improvements

- Split the frontend into components or a frontend framework.
- Add migrations instead of schema-only `CREATE TABLE IF NOT EXISTS`.
- Move long-running scans to background jobs.
- Add pagination and filtering to all large lists.
- Add refresh tokens to the frontend flow.
- Add formal OpenAPI documentation.
- Add production database support such as PostgreSQL.
- Add stronger audit trails and admin activity logs.
