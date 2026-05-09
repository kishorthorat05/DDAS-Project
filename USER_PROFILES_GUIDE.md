# User Profiles Implementation Guide

## Overview

This document describes the **User Profile** system that has been added to DDAS. Each user now has a comprehensive profile that captures role-specific information, preferences, permissions, and statistics.

---

## Database Schema

### `user_profiles` Table

A new table has been added to store user profile data with the following fields:

```sql
CREATE TABLE user_profiles (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL UNIQUE REFERENCES users(id),
    full_name           TEXT,
    bio                 TEXT,
    avatar_url          TEXT,
    phone_number        TEXT,
    department          TEXT,
    title               TEXT,
    timezone            TEXT DEFAULT 'UTC',
    language            TEXT DEFAULT 'en',
    theme               TEXT DEFAULT 'light',  -- light | dark
    notifications_enabled INTEGER DEFAULT 1,
    email_notifications INTEGER DEFAULT 1,
    permissions         TEXT,  -- JSON: role-specific permissions
    preferences         TEXT,  -- JSON: user preferences
    is_verified         INTEGER DEFAULT 0,
    verification_token  TEXT,
    profile_status      TEXT DEFAULT 'active',  -- active | inactive | suspended
    total_uploads       INTEGER DEFAULT 0,
    total_downloads     INTEGER DEFAULT 0,
    datasets_created    INTEGER DEFAULT 0,
    duplicates_found    INTEGER DEFAULT 0,
    created_at          TEXT,
    updated_at          TEXT,
    last_active         TEXT
);
```

### Indexes
- `idx_user_profile_user` - Fast lookup by user_id
- `idx_user_profile_status` - Query by profile status
- `idx_user_profile_verified` - Find verified profiles

---

## Role Profiles

### Guest
- **Description**: Public access to dashboard and analytics
- **Permissions**: `["view_dashboard", "view_analytics"]`
- **Default Limit**: 10 items per page

### Viewer
- **Description**: Read-only access to datasets and analytics
- **Permissions**: `["view_dashboard", "view_analytics", "view_datasets", "download"]`
- **Default Limit**: 50 items per page

### Registered (Default)
- **Description**: Can upload datasets and use AI chat
- **Permissions**: 
  - `view_dashboard`, `view_analytics`, `view_datasets`
  - `download`, `upload`, `create_alerts`, `ai_chat`, `export_data`
- **Default Limit**: 100 items per page
- **Auto-refresh**: Enabled

### Operator
- **Description**: Can run scanners and manage monitoring
- **Permissions**: (All Registered permissions +)
  - `run_scanner`, `start_monitor`, `manage_alerts`
- **Default Limit**: 500 items per page
- **Features**: Alerts enabled, analytics access

### Admin
- **Description**: Full access to all features
- **Permissions**: `["*"]` (All permissions)
- **Default Limit**: 9999 items per page
- **Features**: Full access to analytics, all management functions

---

## Profile Service (`app/services/profile_service.py`)

The `ProfileService` class provides methods to manage user profiles:

### Core Methods

#### `ProfileService.get_role_profile(role: str) -> dict`
Get the default profile configuration for a role.

```python
profile = ProfileService.get_role_profile("admin")
# Returns: {
#     "role": "admin",
#     "description": "Administrator - Full access...",
#     "permissions": ["*"],
#     "default_preferences": {...}
# }
```

#### `ProfileService.get_user_profile_data(user_id: str) -> dict`
Get complete user profile with role information.

```python
profile_data = ProfileService.get_user_profile_data(user_id)
# Returns user + profile + role_metadata
```

#### `ProfileService.update_user_profile(user_id: str, **updates) -> dict`
Update user profile fields (handles JSON serialization).

```python
ProfileService.update_user_profile(user_id, 
    full_name="John Doe",
    preferences={"limit": 100, "sort_order": "desc"}
)
```

#### `ProfileService.get_profiles_by_role(role: str, limit: int = 100) -> list[dict]`
Get all profiles for a specific role.

```python
admin_profiles = ProfileService.get_profiles_by_role("admin")
```

#### `ProfileService.has_permission(user_id: str, permission: str) -> bool`
Check if user has a specific permission.

```python
if ProfileService.has_permission(user_id, "upload"):
    # Allow file upload
```

#### `ProfileService.get_user_permissions(user_id: str) -> list[str]`
Get all permissions for a user.

```python
permissions = ProfileService.get_user_permissions(user_id)
# Returns: ["view_dashboard", "upload", "download", ...]
```

#### `ProfileService.get_user_preferences(user_id: str) -> dict`
Get user preferences.

```python
prefs = ProfileService.get_user_preferences(user_id)
# Returns: {"limit": 100, "sort_order": "desc", "auto_refresh": true}
```

#### `ProfileService.update_user_preferences(user_id: str, **prefs) -> dict`
Update user preferences (partial update).

```python
ProfileService.update_user_preferences(user_id, 
    limit=200,
    auto_refresh=False
)
```

#### `ProfileService.increment_user_stat(user_id: str, stat_name: str, amount: int = 1)`
Increment user statistics.

```python
ProfileService.increment_user_stat(user_id, "total_uploads")
ProfileService.increment_user_stat(user_id, "duplicates_found", 5)
```

#### `ProfileService.get_user_stats(user_id: str) -> dict`
Get user statistics.

```python
stats = ProfileService.get_user_stats(user_id)
# Returns: {
#     "total_uploads": 10,
#     "total_downloads": 50,
#     "datasets_created": 3,
#     "duplicates_found": 15
# }
```

---

## API Endpoints

### Profile Endpoints (`/api/profile`)

#### `GET /api/profile/me`
Get current user's complete profile with role metadata.

**Authentication**: Required (`@require_auth`)

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "admin",
    "profile": {
      "full_name": "John Doe",
      "bio": "Data analyst",
      "avatar_url": "https://...",
      "department": "Analytics",
      "timezone": "UTC",
      "permissions": ["*"],
      "preferences": {"limit": 100, "sort_order": "desc"},
      "is_verified": 1,
      "profile_status": "active",
      "total_uploads": 10,
      "last_active": "2026-05-09T10:30:00Z"
    },
    "role_metadata": {
      "role": "admin",
      "description": "Administrator - Full access to all features and settings",
      "permissions": ["*"],
      "default_preferences": {...}
    }
  }
}
```

#### `PATCH /api/profile/me`
Update current user's profile.

**Authentication**: Required

**Request Body**:
```json
{
  "full_name": "John Doe",
  "bio": "Data analyst",
  "timezone": "America/New_York",
  "theme": "dark",
  "preferences": {
    "limit": 50,
    "auto_refresh": true
  }
}
```

#### `GET /api/profile/role-info`
Get information about all roles and their permissions.

**Authentication**: Not required

**Response**:
```json
{
  "success": true,
  "data": {
    "guest": {
      "role": "guest",
      "description": "Guest - Public access...",
      "permissions": ["view_dashboard", "view_analytics"],
      "default_preferences": {...}
    },
    "viewer": {...},
    "registered": {...},
    "operator": {...},
    "admin": {...}
  }
}
```

#### `GET /api/profile/role-info/<role>`
Get detailed information about a specific role.

**Parameters**: `role` - Role name (guest, viewer, registered, operator, admin)

#### `GET /api/profile/users`
Get all user profiles (admin only).

**Authentication**: Required
**Authorization**: `@require_role("admin")`

**Query Parameters**:
- `limit` - Max 500 (default: 100)
- `offset` - Pagination offset (default: 0)

#### `GET /api/profile/users/role/<role>`
Get all users with a specific role (admin/operator only).

**Query Parameters**:
- `limit` - Max 500 (default: 100)

#### `GET /api/profile/users/<user_id>`
Get a specific user's profile.

**Authentication**: Required (own profile or admin)

#### `GET /api/profile/users/<user_id>/stats`
Get user statistics.

**Authentication**: Required (own stats or admin)

**Response**:
```json
{
  "success": true,
  "data": {
    "total_uploads": 10,
    "total_downloads": 50,
    "datasets_created": 3,
    "duplicates_found": 15
  }
}
```

#### `GET /api/profile/users/<user_id>/permissions`
Get user's permissions.

**Authentication**: Required (admin/operator can view other users)

#### `PATCH /api/profile/users/<user_id>`
Update a user's profile (admin only).

**Authentication**: Required
**Authorization**: `@require_role("admin")`

**Request Body** (can include):
```json
{
  "full_name": "Jane Smith",
  "profile_status": "active",
  "is_verified": 1,
  "permissions": ["view_dashboard", "upload", "download"],
  "preferences": {"limit": 100}
}
```

#### `POST /api/profile/users/<user_id>/verify`
Verify a user profile (admin only).

**Authentication**: Required
**Authorization**: `@require_role("admin")`

#### `POST /api/profile/users/<user_id>/suspend`
Suspend a user profile (admin only).

#### `POST /api/profile/users/<user_id>/activate`
Activate a suspended user profile (admin only).

---

## Registration Flow

When a new user registers, a profile is automatically created:

### Registration Endpoint (`POST /api/auth/register`)

**New Fields**:
- `full_name` - User's full name (optional)

**Process**:
1. User submits registration: `{username, password, email, full_name}`
2. User record is created in `users` table
3. **Profile is automatically created** with:
   - Default role: `"viewer"`
   - Role-specific permissions
   - Default preferences
   - User metadata (full_name, timezone, etc.)
4. JWT token is issued

### Example Registration

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "SecurePass123",
    "email": "john@example.com",
    "full_name": "John Doe"
  }'
```

---

## Login Flow

When a user logs in:

1. Credentials are verified
2. JWT token is issued with user data
3. **Profile last_active timestamp is updated** (on `/api/auth/me` or `/api/profile/me`)

---

## Profile-Role Mapping

| Feature | Guest | Viewer | Registered | Operator | Admin |
|---------|-------|--------|-----------|----------|-------|
| View Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ |
| View Analytics | ✅ | ✅ | ✅ | ✅ | ✅ |
| Download Files | ❌ | ✅ | ✅ | ✅ | ✅ |
| Upload Files | ❌ | ❌ | ✅ | ✅ | ✅ |
| Create Alerts | ❌ | ❌ | ✅ | ✅ | ✅ |
| AI Chat | ❌ | ❌ | ✅ | ✅ | ✅ |
| Run Scanner | ❌ | ❌ | ❌ | ✅ | ✅ |
| Start Monitor | ❌ | ❌ | ❌ | ✅ | ✅ |
| Stop Monitor | ❌ | ❌ | ❌ | ❌ | ✅ |
| Manage Users | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Default Preferences by Role

```python
{
  "guest": {
    "limit": 10,
    "sort_order": "desc",
    "auto_refresh": False
  },
  "viewer": {
    "limit": 50,
    "sort_order": "desc",
    "auto_refresh": False,
    "page_size": 20
  },
  "registered": {
    "limit": 100,
    "sort_order": "desc",
    "auto_refresh": True,
    "page_size": 20
  },
  "operator": {
    "limit": 500,
    "sort_order": "desc",
    "auto_refresh": True,
    "page_size": 50,
    "alerts": True
  },
  "admin": {
    "limit": 9999,
    "sort_order": "desc",
    "auto_refresh": True,
    "page_size": 100,
    "alerts": True,
    "analytics": True
  }
}
```

---

## Usage Examples

### Get Current User's Profile

```python
from app.services.profile_service import ProfileService

profile = ProfileService.get_user_profile_data(user_id)
print(f"User: {profile['username']}")
print(f"Role: {profile['role']}")
print(f"Permissions: {profile['profile']['permissions']}")
```

### Check User Permissions

```python
from app.utils.security import require_auth, g
from app.services.profile_service import ProfileService

@app.route('/api/protected', methods=['POST'])
@require_auth
def protected_route():
    user_id = g.current_user['sub']
    
    if ProfileService.has_permission(user_id, 'upload'):
        # Allow upload
        pass
    else:
        # Deny and return 403
        pass
```

### Update User Statistics

```python
from app.services.profile_service import ProfileService

# When user uploads file
ProfileService.increment_user_stat(user_id, "total_uploads")
ProfileService.increment_user_stat(user_id, "datasets_created")
```

### Get All Admins

```python
from app.services.profile_service import ProfileService

admins = ProfileService.get_profiles_by_role("admin", limit=100)
for admin in admins:
    print(f"{admin['username']} - {admin['full_name']}")
```

---

## Database Functions

### Helper Functions in `app/models/database.py`

```python
# Create a new user profile
create_user_profile(user_id: str, role: str = "viewer", full_name: str = "", email: str = "") -> dict

# Get a user's profile
get_user_profile(user_id: str) -> dict | None

# Update a user's profile
update_user_profile(user_id: str, **updates) -> dict | None

# Get user with profile data merged
get_user_with_profile(user_id: str) -> dict | None

# Get all user profiles (paginated)
get_all_user_profiles(limit: int = 100, offset: int = 0) -> list[dict]

# Get profiles by role
get_profiles_by_role(role: str, limit: int = 100) -> list[dict]
```

---

## Profile Statuses

- **active** - User profile is active and can login
- **inactive** - User profile exists but inactive
- **suspended** - User profile is suspended (admin action)

---

## Integration Points

### 1. **User Registration**
   - New profiles are created during registration
   - Default role and permissions are assigned

### 2. **Authentication**
   - User role is included in JWT token
   - Profile last_active is updated on login

### 3. **Authorization**
   - `@require_role()` decorators use profile permissions
   - Permission checks via `ProfileService.has_permission()`

### 4. **Analytics**
   - User statistics are tracked (uploads, downloads, etc.)
   - User activity is logged to `user_activity` table

### 5. **UI/Frontend**
   - Role badges display based on profile data
   - UI elements show/hide based on permissions
   - User preferences control UI behavior

---

## Security Considerations

1. **Sensitive Fields**: Passwords and tokens are never returned in profile data
2. **Authorization**: Non-admin users can only view/edit their own profiles
3. **Verification**: Email verification status is tracked in `is_verified`
4. **Status**: Users can be suspended without deleting their account
5. **Permissions**: Role-specific permissions are validated on each request

---

## Migration for Existing Users

If there are existing users without profiles, they can be created via:

```python
from app.models.database import get_db, create_user_profile

with get_db() as conn:
    users = conn.execute("SELECT id, username, email, role FROM users WHERE id NOT IN (SELECT user_id FROM user_profiles)").fetchall()
    for user in users:
        create_user_profile(user['id'], role=user['role'], full_name=user['username'], email=user['email'])
```

---

## Next Steps

1. **Frontend Integration**: Update UI to display profile information
2. **Admin Dashboard**: Create profile management interface
3. **User Settings**: Add profile editing UI
4. **Analytics Dashboard**: Display user statistics and activity
5. **Notifications**: Send profile verification emails

