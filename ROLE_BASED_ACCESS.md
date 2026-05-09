# Role-Based Access Control (RBAC) Guide

## Overview
DDAS implements three-tier role-based access control:
- **Guest User** - Anonymous, limited read-only access
- **Registered User** - Authenticated with upload and dashboard capabilities
- **Administrator** - Full system control and user management

---

## 1. Guest User Access

### Features Available
- ✅ Browse public datasets (read-only)
- ✅ View statistics and analytics dashboards
- ✅ Search duplicate detection results
- ✅ Download public exports
- ✅ View AI chat (limited messages)
- ✅ View alerts (read-only)

### Features Restricted
- ❌ Upload files
- ❌ Create datasets
- ❌ Delete or modify data
- ❌ Access admin panel
- ❌ Manage user profiles
- ❌ Configure monitors
- ❌ Full AI chat access

### Backend Endpoints
```
GET /api/datasets                     ✅ Public list
GET /api/duplicates                   ✅ Search results
GET /api/analytics/dashboard          ✅ Statistics
GET /api/analytics/timeline           ✅ Timeline data
GET /api/analytics/file-types         ✅ File distribution
GET /api/auth/me                      ❌ (no token)
```

### Frontend Indication
```
Badge: "Guest" (next to username)
Header: "Continue as Guest"
```

---

## 2. Registered User Access

### Features Available
- ✅ All Guest features
- ✅ Upload and register files
- ✅ Manage personal datasets
- ✅ Create and manage monitors
- ✅ Full duplicate detection
- ✅ Export datasets
- ✅ Full AI chat access
- ✅ View and manage personal alerts
- ✅ Personal analytics
- ✅ Create version control snapshots
- ✅ Access recommendation engine

### Features Restricted
- ❌ Delete other users' datasets
- ❌ Manage other users
- ❌ Access admin panel
- ❌ View system logs
- ❌ Manage organization settings

### Backend Endpoints
```
POST /api/auth/register               ✅ Create account
POST /api/auth/login                  ✅ Authenticate
GET  /api/auth/me                     ✅ Current user
POST /api/datasets/upload             ✅ Upload file
GET  /api/datasets                    ✅ List own datasets
POST /api/duplicates/scan-directory   ✅ Scan
POST /api/ai/chat                     ✅ Chat
POST /api/alerts/create               ✅ Create alert
GET  /api/export/zip                  ✅ Export data
DELETE /api/datasets/{id}             ✅ Own datasets only
```

### Frontend Indication
```
Badge: "Registered" (with username)
Full navigation menu
Profile dropdown with logout
```

---

## 3. Administrator Access

### Features Available
- ✅ All Registered User features
- ✅ View all datasets (system-wide)
- ✅ Delete any dataset
- ✅ View system analytics and health
- ✅ Manage user accounts
- ✅ View audit logs
- ✅ Configure system settings
- ✅ Manage organization
- ✅ View all monitors
- ✅ System diagnostics

### Backend Endpoints (Admin-only)
```
GET  /api/admin/users                 ✅ List all users
POST /api/admin/users/{id}/role       ✅ Assign roles
DELETE /api/admin/users/{id}          ✅ Delete user
GET  /api/admin/system/health         ✅ System stats
GET  /api/admin/audit-log             ✅ Audit trail
POST /api/admin/settings              ✅ Configure
```

### Frontend Indication
```
Badge: "Admin" (with username)
Full navigation + "Admin Panel"
System settings option
User management
Audit logs view
```

---

## 4. Role-Based UI Components

### Navigation Menu
```
Guest:
  - Datasets (read-only)
  - Analytics
  - Help

Registered:
  - Datasets (full control)
  - Upload
  - Duplicates
  - Monitors
  - Alerts
  - Analytics
  - AI Chat
  - Exports
  - Profile

Administrator:
  - All Registered features
  - Admin Panel
  - Users Management
  - System Settings
  - Audit Logs
  - Health Monitor
```

### Auth Overlay
```
Guest View:
  - Login button
  - Register button
  - "Continue as Guest" link

Registered View:
  - Username display
  - Profile dropdown
  - Logout button

Admin View:
  - Username (labeled "Admin")
  - Profile dropdown
  - Admin Panel link
  - Logout button
```

---

## 5. Frontend Implementation

### Check User Role
```javascript
function getUserRole() {
  const token = localStorage.getItem('token');
  if (!token) return 'guest';
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.role || 'viewer';
  } catch {
    return 'guest';
  }
}

function isAdmin() {
  return getUserRole() === 'admin' || getUserRole() === 'administrator';
}

function isRegistered() {
  return localStorage.getItem('token') !== null;
}
```

### Show/Hide Elements by Role
```javascript
function setVisibilityByRole(role) {
  const guestOnly = document.querySelectorAll('[data-role="guest"]');
  const registeredOnly = document.querySelectorAll('[data-role="registered"]');
  const adminOnly = document.querySelectorAll('[data-role="admin"]');

  // Hide all restricted elements
  guestOnly.forEach(el => el.style.display = 'none');
  registeredOnly.forEach(el => el.style.display = 'none');
  adminOnly.forEach(el => el.style.display = 'none');

  // Show role-appropriate elements
  if (role === 'guest') {
    guestOnly.forEach(el => el.style.display = 'block');
  } else if (role === 'viewer' || role === 'operator') {
    guestOnly.forEach(el => el.style.display = 'block');
    registeredOnly.forEach(el => el.style.display = 'block');
  } else if (role === 'admin' || role === 'administrator') {
    guestOnly.forEach(el => el.style.display = 'block');
    registeredOnly.forEach(el => el.style.display = 'block');
    adminOnly.forEach(el => el.style.display = 'block');
  }
}
```

### HTML Markup Example
```html
<!-- Guest-only content -->
<div data-role="guest">
  <p>Sign in to unlock more features</p>
</div>

<!-- Registered-only content -->
<button data-role="registered" onclick="uploadFile()">
  Upload File
</button>

<!-- Admin-only content -->
<button data-role="admin" onclick="manageUsers()">
  Manage Users
</button>
```

---

## 6. Backend Implementation

### Protect Endpoints by Role

```python
# Guest-friendly (optional auth)
@data_bp.get("/datasets")
@jwt_required
def get_datasets():
    if g.current_user:
        # Show user's datasets
        pass
    else:
        # Show public datasets
        pass

# Registered users only
@data_bp.post("/datasets/upload")
@require_auth
def upload_dataset():
    # Require authentication
    pass

# Admin only
@data_bp.delete("/datasets/<dataset_id>")
@require_role("admin")
def delete_dataset(dataset_id):
    # Admin-only action
    pass

# Multiple roles
@data_bp.post("/alerts/create")
@require_role("admin", "operator")
def create_alert():
    # Admin or Operator
    pass
```

### Role Hierarchy
```
guest < viewer < operator < admin
 (none)  (default) (advanced) (full)
```

---

## 7. Default Role Assignment

### New User Registration
- Default role: **`viewer`** (Registered User capabilities)
- Can be promoted to `operator` or `admin` by existing admin

### Guest Session
- No user record created
- Temporary session token (if needed)
- Expires on browser close or 24 hours

### Admin Promotion
- Requires existing admin action
- Via `/api/admin/users/{id}/role` endpoint
- Audit logged

---

## 8. API Response Examples

### Auth Response (Registered)
```json
{
  "success": true,
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": "abc123",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "viewer",
    "organization_id": "org456"
  }
}
```

### Me Endpoint (Admin)
```json
{
  "success": true,
  "user": {
    "id": "xyz789",
    "username": "admin_user",
    "email": "admin@example.com",
    "role": "admin",
    "is_active": true,
    "login_count": 42,
    "last_login": "2026-05-08T23:30:00Z"
  }
}
```

### Unauthorized Response
```json
{
  "success": false,
  "error": "Insufficient permissions",
  "code": "FORBIDDEN"
}
```

---

## 9. Testing Access Control

### Test Endpoints by Role

```bash
# Test as Guest (no token)
curl http://localhost:5000/api/datasets

# Test as Registered User
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/datasets/upload

# Test as Admin
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:5000/api/admin/users

# Test permission denial
curl -H "Authorization: Bearer $GUEST_TOKEN" \
  http://localhost:5000/api/admin/users  # Should get 403
```

---

## 10. Security Best Practices

1. **Never trust client-side role checks** - Always verify on backend
2. **Use @require_auth or @require_role decorators** on all endpoints
3. **Log role-based access** for audit trail
4. **Validate JWT payload** - Don't assume role from token
5. **Rate limit auth endpoints** - Prevent brute force
6. **Clear tokens on logout** - Both client and backend
7. **Use HTTPS only** - Protect JWT in transit
8. **Set appropriate token expiry** - Balance security vs UX

---

## 11. Quick Reference Table

| Feature | Guest | Registered | Admin |
|---------|-------|-----------|-------|
| View Datasets | ✅ | ✅ | ✅ |
| Upload Files | ❌ | ✅ | ✅ |
| Delete Dataset | ❌ | Own only | All |
| Run Duplicates Scan | ❌ | ✅ | ✅ |
| Create Monitor | ❌ | ✅ | ✅ |
| Manage Users | ❌ | ❌ | ✅ |
| View Audit Log | ❌ | ❌ | ✅ |
| Export Data | ❌ | ✅ | ✅ |
| Full AI Chat | ❌ | ✅ | ✅ |
| System Settings | ❌ | ❌ | ✅ |

---

## 12. Implementation Checklist

- [ ] Backend: Verify all endpoints have role decorators
- [ ] Frontend: Add `data-role` attributes to UI elements
- [ ] Frontend: Implement `setVisibilityByRole()` function
- [ ] Frontend: Update navigation menu based on role
- [ ] Frontend: Update auth overlay display logic
- [ ] Tests: Verify each role's endpoint access
- [ ] Tests: Verify 403 responses for unauthorized access
- [ ] Security: Enable rate limiting on auth routes
- [ ] Docs: Update API documentation with role requirements
- [ ] Deployment: Set default admin user during initialization
