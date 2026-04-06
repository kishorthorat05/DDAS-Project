# Duplicate File Detection & Display System

## Overview
The DDAS system now includes a powerful duplicate detection system that identifies all duplicate files with the same hash content and displays them with their storage locations, sizes, and deduplication potential.

## Features

### 1. **Duplicate Detection Service** (`DuplicateService`)
Located in `app/services/dataset_service.py`, this service provides:

#### Methods:
- **`get_duplicates_by_hash(file_hash)`**
  - Get all files with the same hash (duplicates)
  - Returns structured duplicate group with all locations
  - Includes storage savings calculation

- **`get_all_duplicates(limit=100)`**
  - Get all duplicate groups in the system
  - Sorted by number of copies (most duplicated first)
  - Returns list of duplicate groups

- **`get_duplicates_for_file(dataset_id)`**
  - Get all duplicates for a specific file
  - Shows original file and all duplicate locations

- **`find_duplicates_by_name(file_name)`**
  - Search for files with same name (potential duplicates)
  - Useful for finding similarly named duplicates

- **`get_duplicate_statistics()`**
  - Get comprehensive duplicate statistics
  - Shows total duplicates, wasted storage, percentages
  - Includes efficiency metrics

### 2. **API Endpoints**

#### Get All Duplicates
```
GET /api/duplicates/all?limit=100
Authorization: Bearer <token>
```
**Response:**
```json
{
  "success": true,
  "data": {
    "duplicates": [
      {
        "file_hash": "abc123...",
        "total_copies": 3,
        "original_file": {...},
        "duplicate_locations": [...],
        "total_storage_used": 1048576,
        "storage_saved_if_deduplicated": 2097152
      }
    ],
    "total_groups": 5
  }
}
```

#### Get Duplicates by Hash
```
GET /api/duplicates/by-hash/<file_hash>
Authorization: Bearer <token>
```

#### Get Duplicates for Specific File
```
GET /api/duplicates/for-file/<dataset_id>
Authorization: Bearer <token>
```

#### Search Duplicates by Name
```
GET /api/duplicates/by-name?name=<filename>
Authorization: Bearer <token>
```

#### Get Duplicate Statistics
```
GET /api/duplicates/statistics
Authorization: Bearer <token>
```
**Response:**
```json
{
  "success": true,
  "data": {
    "total_files": 1500,
    "unique_files": 1200,
    "duplicate_files": 300,
    "duplicate_groups": 50,
    "duplicate_percentage": 20.0,
    "total_storage_bytes": 10737418240,
    "wasted_storage_bytes": 2147483648,
    "wasted_storage_percentage": 20.0,
    "potential_savings_gb": 2.0
  }
}
```

#### Mark for Deduplication
```
POST /api/duplicates/mark-for-deduplication
Authorization: Bearer <token>
Content-Type: application/json

{
  "file_hash": "abc123...",
  "action": "delete"  // or "archive" or "convert_to_link"
}
```

### 3. **UI Component**

#### Location
`static/components/DuplicateDetector.html`

#### Features:
- **Statistics Dashboard**: Shows total duplicates, wasted storage, efficiency metrics
- **Search Functionality**: Search duplicates by file name
- **Duplicate Groups**: Expandable groups showing:
  - Original file (highlighted)
  - All duplicate locations with paths
  - File sizes and creation dates
  - Storage savings potential
- **Real-time Updates**: Refresh or scan for new duplicates
- **Responsive Design**: Works on desktop and mobile
- **Detailed Storage Info**: Shows exact storage savings in GB

#### Integration
Add to your HTML:
```html
<!-- Include the component -->
<link rel="stylesheet" href="/static/components/DuplicateDetector.css">
<div id="duplicate-detector-container"></div>
<script src="/static/components/DuplicateDetector.js"></script>

<!-- Initialize -->
<script>
  document.addEventListener('DOMContentLoaded', () => {
    DuplicateDetector.init();
  });
</script>
```

Or inline in existing HTML:
```html
<iframe src="/static/components/DuplicateDetector.html" style="width: 100%; height: 100%; border: none;"></iframe>
```

## Data Display Structure

### Duplicate Group Object
```javascript
{
  file_hash: "sha256:abc123...",
  total_copies: 3,
  original_file: {
    id: "dataset_id_1",
    file_name: "report.pdf",
    file_path: "/uploads/report.pdf",
    file_size: 1048576,
    file_type: ".pdf",
    created_at: "2025-01-15T10:30:00Z",
    user_name: "admin"
  },
  duplicate_locations: [
    {
      id: "dataset_id_2",
      file_name: "report.pdf",
      file_path: "/downloads/report.pdf",
      file_size: 1048576,
      created_at: "2025-01-16T14:20:00Z"
    },
    {
      id: "dataset_id_3",
      file_name: "report_backup.pdf",
      file_path: "/backups/report_backup.pdf",
      file_size: 1048576,
      created_at: "2025-01-17T08:10:00Z"
    }
  ],
  all_files: [...], // Combined array of original + duplicates
  total_storage_used: 3145728,
  storage_saved_if_deduplicated: 2097152  // (3145728 - 1048576)
}
```

## Usage Examples

### Python Backend
```python
from app.services.dataset_service import DuplicateService

# Get all duplicates
duplicates = DuplicateService.get_all_duplicates(limit=50)
print(f"Found {len(duplicates)} duplicate groups")

# Get statistics
stats = DuplicateService.get_duplicate_statistics()
print(f"Potential savings: {stats['potential_savings_gb']} GB")
print(f"Duplication rate: {stats['duplicate_percentage']}%")

# Get duplicates for specific file
dup_group = DuplicateService.get_duplicates_by_hash("abc123...")
print(f"Total copies: {dup_group['total_copies']}")
print(f"Storage saved if deduplicated: {dup_group['storage_saved_if_deduplicated']} bytes")
```

### JavaScript Frontend
```javascript
// Initialize the component
DuplicateDetector.init();

// Refresh data
DuplicateDetector.refresh();

// Search by name
document.getElementById('search-file-name').value = 'report.pdf';
DuplicateDetector.searchDuplicates();

// View details
DuplicateDetector.showDetails('file_hash_here');

// Scan for new duplicates
DuplicateDetector.scanNow();
```

### API Calls
```bash
# Get all duplicates
curl -X GET "http://localhost:5000/api/duplicates/all?limit=100" \
  -H "Authorization: Bearer <token>"

# Get statistics
curl -X GET "http://localhost:5000/api/duplicates/statistics" \
  -H "Authorization: Bearer <token>"

# Search by name
curl -X GET "http://localhost:5000/api/duplicates/by-name?name=report" \
  -H "Authorization: Bearer <token>"

# Get duplicates for specific hash
curl -X GET "http://localhost:5000/api/duplicates/by-hash/abc123..." \
  -H "Authorization: Bearer <token>"

# Mark for deduplication
curl -X POST "http://localhost:5000/api/duplicates/mark-for-deduplication" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_hash": "abc123...",
    "action": "delete"
  }'
```

## Display Information Details

### File Locations Display
For each duplicate group, the UI shows:
- **Original File** (Highlighted in blue):
  - File name
  - Full path location
  - File size
  - Creation date
  - User who uploaded

- **Duplicate Locations** (White background):
  - File name (may differ from original)
  - Full system path
  - Exact file size (identical)
  - Date created/uploaded
  - Checkbox to select for action

### Storage Savings Information
- **Total Storage Used**: Sum of all copies
- **Individual File Size**: Each copy's exact size
- **Potential Savings**: `(total_copies - 1) × file_size`
- **Wasted Storage**: Aggregate of all duplicates in system
- **Efficiency Metrics**: Percentage of storage used efficiently

## Integration Points

### With Scanning System
When scan completes, automatically detect duplicates:
```python
# In monitor_service.py
result = manual_scan()
duplicates = DuplicateService.get_all_duplicates()
# Display results
```

### With Upload System
On file upload, check for duplicates:
```python
# In routes.py /upload/file
file_hash = hash_file(dest)
dup_group = DuplicateService.get_duplicates_by_hash(file_hash)
if dup_group['total_copies'] > 1:
    # Notify user of duplication
```

### With Export System
Export duplicate information in scan results:
```python
# Include duplicate data in exports
duplicates = DuplicateService.get_all_duplicates()
export_data['duplicates'] = duplicates
```

## Performance Considerations

- Database queries are indexed on `file_hash`
- Statistics calculation uses GROUP BY for efficiency
- Results are paginated (limit parameter)
- Frontend component uses lazy loading for large datasets
- Caching can be added for statistics (refreshed hourly)

## Security

- All endpoints require JWT authentication
- Bearer token from Authorization header
- Rate limited to prevent abuse
- File paths are restricted to uploaded/monitored directories
- SQL injection prevented through parameterized queries

## Future Enhancements

- [ ] Fuzzy duplicate detection (near-duplicates)
- [ ] Automatic deduplication with hard links
- [ ] Duplicate history timeline
- [ ] WebSocket real-time updates
- [ ] Batch deduplication operations
- [ ] Custom deduplication policies
- [ ] Integration with cloud storage deduplication
