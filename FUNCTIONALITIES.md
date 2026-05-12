# DDAS Functionalities

This document explains every major feature from a user and developer perspective.

## Feature Matrix

| Feature | Guest | Registered | Admin |
| --- | --- | --- | --- |
| View dashboard | Yes | Yes | Yes |
| View repository | Yes | Yes | Yes |
| View analytics | Yes | Yes | Yes |
| Upload file | No | Yes | Yes |
| Run manual scan | No | Yes | Yes |
| View personal history | No | Yes | Yes |
| View all users | No | No | Yes |
| Change user roles | No | No | Yes |
| Activate/deactivate users | No | No | Yes |
| Start/stop monitor | No | No | Yes |
| Export data | No | Yes | Yes |
| AI chat | Limited | Yes | Yes |

## 1. Authentication

### Register

Endpoint: `POST /api/auth/register`

Purpose:

- Creates a user row in `users`.
- Creates a profile row in `user_profiles`.
- Returns access token and user profile.

Important details:

- Username must be at least 3 characters.
- Password must be at least 8 characters.
- Public registration is for `registered` users.
- First admin can exist, but after that admin access should be assigned by an existing admin.
- Duplicate username/email returns a conflict response.

### Login

Endpoint: `POST /api/auth/login`

Purpose:

- Verifies username/password.
- Requires `users.is_active = 1`.
- Updates `last_login` and `login_count`.
- Ensures user profile exists.
- Returns access and refresh tokens.

### Guest

Endpoint: `POST /api/auth/guest`

Returns a non-persistent guest profile with limited permissions.

### Change Password

Endpoint: `POST /api/auth/change-password`

Requires:

- Login token.
- Current password.
- New password.
- OTP.

### OTP

Endpoint: `POST /api/auth/request-otp`

Uses in-memory `_otp_store`; intended for development/demo use.

## 2. Role-Based Access

Roles:

| Role | Meaning |
| --- | --- |
| `guest` | Read-only public-style access. |
| `registered` | Normal authenticated user. |
| `admin` | Full access and user management. |

Permissions are stored in profile JSON and supplemented by role defaults. Admin has `*`.

## 3. User Management

Admin profile page includes:

- User list.
- Active/inactive status.
- Role dropdown.
- Admin safeguards against deactivating or demoting the last active admin.

Relevant endpoints:

- `GET /api/profile/users`
- `POST /api/profile/users/<user_id>/role`
- `POST /api/profile/users/<user_id>/suspend`
- `POST /api/profile/users/<user_id>/activate`

## 4. Dataset Upload

Endpoint: `POST /api/upload/file`

Workflow:

1. User selects a file in UI.
2. Frontend guesses metadata from filename.
3. Backend saves file to upload folder.
4. Backend computes SHA-256 hash.
5. If hash exists, file is treated as duplicate and removed.
6. If unique, dataset row is created.
7. History and insights are returned.

Data fields:

- `file`
- `user_name`
- `description`
- `period`
- `spatial_domain`

## 5. URL Upload

Endpoint: `POST /api/upload/url`

Downloads a remote URL after safety checks, saves it locally, hashes it, and registers it if unique.

Security:

- Uses `is_safe_url`.
- Blocks private/loopback addresses.
- Uses streaming download.

## 6. Duplicate Detection

Duplicate detection is based primarily on exact hash matching.

Used by:

- File upload.
- Manual scan.
- Watchdog monitor.
- Duplicate detector page.

Duplicate outputs:

- Alerts.
- History entries.
- Scan logs.
- Duplicate group reports.

## 7. Manual Scan

Endpoint: `POST /api/monitor/scan`

Registered users and admins can run it.

Workflow:

1. Uses provided directory or upload folder.
2. Iterates files.
3. Computes each hash.
4. Registers unique files or flags duplicates.
5. Logs scan results.
6. Updates dashboard and scan activity table.

## 8. Watchdog Monitor

Endpoints:

- `POST /api/monitor/start`
- `POST /api/monitor/stop`
- `GET /api/monitor/status`

Admin-only start/stop.

The monitor watches configured `MONITORED_DIR` for created/moved files and processes them through the same duplicate pipeline.

## 9. Alerts

Endpoints:

- `GET /api/alerts`
- `PATCH /api/alerts/<alert_id>/read`
- `POST /api/alerts/read-all`

Alerts are generated mostly for duplicates.

UI:

- Alert badge.
- Alert list.
- Mark read.
- Mark all read.

## 10. History

Endpoint: `GET /api/history`

Behavior:

- Normal users see their own history.
- Admin can request all with `scope=all`.

History records include:

- dataset ID
- user ID
- user name
- file name
- hash
- action
- status
- IP
- notes
- timestamp

## 11. Scan Logs

Endpoint: `GET /api/scan-logs`

Shows recent file scan events, including:

- path
- file name
- size
- hash
- duplicate flag
- error
- scanned time

## 12. Dataset Repository

Endpoints:

- `GET /api/datasets`
- `GET /api/datasets/search`
- `GET /api/datasets/search/name`
- `GET /api/datasets/search/location`
- `GET /api/datasets/filter/type`
- `GET /api/datasets/filter/size`
- `GET /api/datasets/filter/date`
- `POST /api/datasets/advanced-search`
- `GET /api/datasets/<dataset_id>`

UI supports list, search, and metadata display.

## 13. Analytics

Endpoints:

- `GET /api/analytics/dashboard`
- `GET /api/analytics/timeline`
- `GET /api/analytics/file-types`
- `GET /api/analytics/user-activity`
- `GET /api/analytics/top-duplicates`
- `GET /api/analytics/system-health`

Metrics:

- total datasets
- duplicates detected
- duplication rate
- active users
- unread alerts
- total storage
- bandwidth saved
- storage efficiency
- new files in last 7 days

## 14. Export and Backup

Endpoints:

- `POST /api/export/scan-results`
- `POST /api/export/datasets`
- `POST /api/export/cleanup`
- `GET /api/export/list`
- `GET /api/export/download`

Generated ZIP files may contain:

- scan report JSON
- duplicates summary JSON
- metadata text
- dataset CSV
- dataset JSON

## 15. AI Chatbot

Endpoints:

- `POST /api/ai/chat`
- `POST /api/ai/chat/clear`
- `GET /api/ai/status`

Capabilities:

- Uses Gemini if configured.
- Falls back to rule-based/project-grounded responses.
- Can detect action requests for scans, monitor status, dashboard stats, health, alerts, duplicates, and scan logs.
- Uses recent conversation history.

## 16. Profile Management

Endpoints:

- `GET /api/profile/me`
- `PATCH /api/profile/me`
- `POST /api/profile/avatar`
- `GET /api/profile/avatar/<filename>`
- `POST /api/profile/2fa-mobile`
- `GET /api/profile/role-info`
- `GET /api/profile/role-info/<role>`

UI features:

- Full name.
- Email display.
- Phone number.
- Avatar upload/preview/viewer.
- Theme/language preferences.
- Alert preferences.
- Login count and last login.
- Recent activity.
- Permissions.

## 17. Duplicate Detector Page

Functions:

- Show duplicate group stats.
- Show duplicate files and wasted storage.
- Scan directory.
- Search by filename.
- Expand/collapse duplicate groups.
- Filter duplicate list.

Endpoints:

- `/api/duplicates/statistics`
- `/api/duplicates/all`
- `/api/duplicates/scan-directory`
- `/api/duplicates/search-by-filename`

## 18. Hidden or Advanced Features

| Feature | Location | Status |
| --- | --- | --- |
| Cloud integrations | `cloud_service.py` | Service code exists, limited UI/API exposure. |
| Team collaboration | `collaboration_service.py` | Service code exists, limited UI/API exposure. |
| Compression optimization | `compression_service.py` | Service code exists, limited UI/API exposure. |
| Recommendation engine | `recommendation_service.py` | Service code exists, limited UI/API exposure. |
| Dataset versioning | `version_control_service.py` | Service code exists, limited UI/API exposure. |
| Similarity cache | `similarity_service.py` | Service code exists, used by recommendations. |
| Metrics service | `metrics_service.py` | Service code exists, analytics routes mostly use `analytics_service.py`. |

## 19. Refresh Buttons

| Button | Function |
| --- | --- |
| Dashboard scan activity Refresh | `loadScanLogs()` |
| Repository Refresh | `loadRepository()` |
| Alerts Refresh | `loadAlerts()` |
| History Refresh | `loadHistory()` |
| Analytics Refresh | `loadAnalytics()` |
| Export Refresh | `loadAvailableExports()` |
| Duplicates Refresh | `loadDuplicateDetector()` |
| Profile Refresh | `loadProfilePage()` |
| Admin users Refresh | `loadUserManagement()` |

## 20. Limitations by Feature

- Manual scans are synchronous and can block for large folders.
- Watchdog monitor is non-recursive.
- Guest access is UI-limited and some public endpoints still expose read-only data.
- Some admin actions are not fully audited.
- Advanced service modules need API/UI completion before end users can use them fully.
