# Backend Role-Based Access Configuration

## Summary
This guide maps each API endpoint to required role and appropriate decorator.

## Route Protection Template

```python
# Guest-accessible (read-only, public data)
@data_bp.get("/datasets")
@jwt_required  # Optional auth
def get_datasets():
    pass

# Registered users (authenticated)
@data_bp.post("/datasets/upload")
@require_auth  # Must be logged in
def upload():
    pass

# Admin-only routes
@data_bp.delete("/datasets/<dataset_id>")
@require_role("admin")  # Admin only
def delete_dataset(dataset_id):
    pass

# Multiple roles allowed
@monitor_bp.post("/monitor/start")
@require_role("admin", "operator")  # Admin OR Operator
def start_monitor():
    pass
```

## Current Route Protections

### AUTH Routes
```python
POST   /api/auth/register              ✅ @rate_limit (public, no auth)
POST   /api/auth/login                 ✅ @rate_limit (public, no auth)
GET    /api/auth/me                    ✅ @require_auth (authenticated)
POST   /api/auth/refresh               ✅ @rate_limit (public)
```

### DATASETS Routes
```python
GET    /api/datasets                   ✅ @require_auth (authenticated)
GET    /api/datasets/search            ✅ @require_auth (authenticated)
GET    /api/datasets/search/name       ✅ @require_auth (authenticated)
GET    /api/datasets/search/location   ✅ @require_auth (authenticated)
GET    /api/datasets/filter/type       ✅ @require_auth (authenticated)
GET    /api/datasets/filter/size       ✅ @require_auth (authenticated)
GET    /api/datasets/filter/date       ✅ @require_auth (authenticated)
POST   /api/datasets/advanced-search   ✅ @require_auth (authenticated)
GET    /api/datasets/stats             ✅ @require_auth (authenticated)
GET    /api/datasets/<id>              ✅ @require_auth (authenticated)
POST   /api/check-duplicate            ✅ @require_auth (authenticated)
POST   /api/datasets/upload            ✅ @require_auth (registered users)
```

### UPLOAD Routes
```python
POST   /api/upload                     ✅ @require_auth (registered users)
GET    /api/upload/status              ✅ @require_auth (authenticated)
DELETE /api/datasets/<id>              ✅ @require_auth (own datasets)
```

### MONITORS Routes
```python
GET    /api/monitor/status             ✅ @require_auth (authenticated)
POST   /api/monitor/start              ✅ @require_role("admin", "operator")
POST   /api/monitor/stop               ✅ @require_role("admin")
GET    /api/scan-logs                  ✅ @require_auth (authenticated)
GET    /api/history                    ✅ @require_auth (authenticated)
```

### ALERTS Routes
```python
GET    /api/alerts                     ✅ @require_auth (authenticated)
POST   /api/alerts/create              ✅ @require_auth (authenticated)
PUT    /api/alerts/<id>/acknowledge    ✅ @require_auth (authenticated)
DELETE /api/alerts/<id>                ✅ @require_auth (own alerts only)
```

### AI Routes
```python
POST   /api/ai/chat                    ✅ @require_auth + @rate_limit (authenticated)
GET    /api/ai/status                  ✅ @jwt_required (optional auth)
GET    /api/ai/models                  ✅ @jwt_required (optional auth)
```

### ANALYTICS Routes
```python
GET    /api/analytics/dashboard        ✅ @require_auth (authenticated)
GET    /api/analytics/timeline         ✅ @require_auth (authenticated)
GET    /api/analytics/file-types       ✅ @require_auth (authenticated)
GET    /api/analytics/user-activity    ✅ @require_auth (authenticated)
GET    /api/analytics/top-duplicates   ✅ @require_auth (authenticated)
GET    /api/analytics/system-health    ✅ @require_role("admin")
```

### EXPORT Routes
```python
GET    /api/export/zip                 ✅ @require_auth (authenticated)
GET    /api/export/csv                 ✅ @require_auth (authenticated)
POST   /api/export/batch               ✅ @require_auth (authenticated)
```

### DUPLICATES Routes
```python
POST   /api/duplicates/scan-directory  ✅ @require_auth (registered)
POST   /api/duplicates/search-by-filename  ✅ @require_auth (authenticated)
GET    /api/duplicates                 ✅ @require_auth (authenticated)
GET    /api/duplicates/<id>            ✅ @require_auth (authenticated)
```

## Role Hierarchy & Permissions

```
┌─────────────────────────────────────────────┐
│  ADMINISTRATOR                              │
│  - All permissions                          │
│  - Full system access                       │
│  - User management                          │
│  - System configuration                     │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  OPERATOR / ADVANCED USER                   │
│  - Upload/download/delete own data          │
│  - Run monitors and scans                   │
│  - Create alerts and rules                  │
│  - Export and version control               │
│  - Full analytics access                    │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  VIEWER / REGISTERED USER (DEFAULT)         │
│ - Upload files                              │
│ - Access own datasets                       │
│ - Basic monitoring                          │
│ - Personal alerts only                      │
│ - Personal analytics                        │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  GUEST USER (UNAUTHENTICATED)               │
│ - View public datasets (read-only)          │
│ - View public analytics                     │
│ - Search duplicates                         │
│ - Limited AI chat                           │
└─────────────────────────────────────────────┘
```

## Protected Routes by Role

### Admin-Only Operations
```python
# Delete any dataset
@require_role("admin")
DELETE /api/datasets/<dataset_id>

# Manage users
@require_role("admin")
GET/POST /api/admin/users

# System settings
@require_role("admin")
GET/POST /api/admin/settings

# View audit logs
@require_role("admin")
GET /api/admin/audit-log

# Stop monitor
@require_role("admin")
POST /api/monitor/stop
```

### Admin + Operator
```python
# Start monitor (admin and advanced users)
@require_role("admin", "operator")
POST /api/monitor/start

# Create alerts
@require_role("admin", "operator") 
POST /api/alerts/create

# Run full scan
@require_role("admin", "operator")
POST /api/duplicates/scan-directory
```

### Authenticated (Any Logged-In User)
```python
# All dataset searches/filters
@require_auth
GET /api/datasets/*

# Upload files
@require_auth
POST /api/datasets/upload

# Chat
@require_auth
POST /api/ai/chat

# Analytics
@require_auth
GET /api/analytics/*

# Export
@require_auth
POST /api/export/*
```

## Implementation Recommendations

1. **Always use @require_auth or @require_role**
   - Never leave endpoints without protection
   - Use @jwt_required only for truly public endpoints

2. **Check ownership on delete/update**
   ```python
   @data_bp.delete("/datasets/<dataset_id>")
   @require_auth
   def delete_dataset(dataset_id: str):
       ds = DatasetService.get_by_id(dataset_id)
       user_id = g.current_user.get("sub")
       
       # Check if user owns dataset
       if ds["owner_id"] != user_id and g.current_user.get("role") != "admin":
           return _err("Forbidden", 403)
       
       DatasetService.delete(dataset_id)
       return _ok({"deleted": True})
   ```

3. **Rate limit auth endpoints**
   - `/api/auth/register` - 5 per hour per IP
   - `/api/auth/login` - 10 per 5 minutes per IP
   - `/api/ai/chat` - 60 per hour per user

4. **Log role-based actions**
   ```python
   # For audit trail
   current_user = g.current_user or {}
   log.info(f"Action: {action}, User: {current_user.get('username')}, Role: {current_user.get('role')}")
   ```

5. **Return appropriate HTTP codes**
   - 401 Unauthorized (no token)
   - 403 Forbidden (authenticated but no permission)
   - 404 Not Found (for sensitive data)

## Testing Role-Based Access

```bash
# Test as Guest (no token)
curl http://localhost:5000/api/datasets
# Result: 401 Unauthorized or 200 with public data

# Test as Registered User
TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","password":"pass123"}' | jq -r '.access_token')

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/datasets
# Result: 200 with user's datasets

# Test Admin route with non-admin token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/admin/users
# Result: 403 Forbidden

# Test Admin route with admin token
ADMIN_TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"adminpass"}' | jq -r '.access_token')

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:5000/api/admin/users
# Result: 200 with user list
```
