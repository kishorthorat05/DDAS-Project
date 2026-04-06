# Duplicate Detector - Complete Guide

## 🎯 Overview
The Duplicate Detector scans your computer's file system and identifies duplicate files by computing SHA256 hashes. It displays detailed information about each duplicate including file name, type, size, location, and status.

## ✨ Key Features

### 1. **Directory Scanning** 📁
- Scan any folder on your computer for duplicates
- **Recursive scanning**: Option to include all subfolders
- Real-time progress updates
- Detailed scan statistics

### 2. **Filename-Based Search** 🔍
- Search system-wide for all instances of a specific filename
- Use exact filenames or wildcards (e.g., `*.jpg`, `photo*`)
- Automatically scans common system locations:
  - Windows: Downloads, Documents, Desktop, Pictures, Videos, AppData\Temp
  - Linux/Mac: /home, /Users, and user directories
- Finds and groups all duplicates

### 3. **Duplicate Detection**
- Computes SHA256 hash for every file
- Groups identical files by hash (same content = same hash)
- Shows original vs copy badges (⭐ vs 📄)
- Calculates wasted storage automatically

### 4. **Complete File Information Display**
For each file found, the detector shows:
- **File Name**: The exact filename
- **File Type**: Extension (.jpg, .pdf, .doc, etc.)
- **File Size**: Size in bytes/KB/MB/GB
- **File Location**: Full absolute path to the file on disk
- **Status**: Duplicate or Unique
- **Created Date**: File creation timestamp

### 5. **Statistics Dashboard**
- 📊 **Duplicate Groups**: Number of groups with duplicates
- 📋 **Duplicate Files**: Total redundant file copies
- 💾 **Storage Wasted**: Total recoverable storage space

### 6. **Advanced Search & Filter**
- Search by filename across results
- Filter by file path/location
- Real-time filtering
- Multiple search methods

## 🚀 How to Use

### Method 1: Scan a Specific Directory

**Step 1**: Navigate to **Duplicates** page
- Click the "Duplicates" button in the left sidebar

**Step 2**: Enter folder path in "📁 Scan Files & Folders" section
- **Windows**: `C:\Users\Downloads` or `C:\Users\YourName\Documents`
- **Mac/Linux**: `/Users/username/Downloads` or `/home/username/Documents`

**Step 3**: Configure scan options
- ✅ Check **"Scan subfolders"** to include nested directories
- ⬜ Uncheck to scan only the top-level folder

**Step 4**: Click **"📁 Scan Directory"** button
- Wait for scan to complete
- View scan statistics:
  - Number of files scanned
  - Duplicate groups discovered
  - Total number of duplicate files
  - Wasted storage calculation

**Step 5**: Review results
- Expand each duplicate group by clicking on it
- View all copies of the duplicate file
- See file paths and details

---

### Method 2: Search System-Wide by Filename

**Step 1**: Navigate to **Duplicates** page

**Step 2**: Enter filename in "🔍 Search for Duplicate Files by Name" section
- Exact filename: `photo.jpg`, `document.pdf`
- Wildcard patterns: `*.jpg`, `*.pdf`, `photo*`

**Step 3**: Click **"🔍 Search System for Duplicates"** button
- System searches common locations:
  - **Windows**: Downloads, Documents, Desktop, Pictures, Videos, Temp
  - **Mac/Linux**: Home, Users, and user directories
- Wait for search to complete

**Step 4**: Review search results
- Summary shows:
  - Total files found
  - Number of duplicate groups
  - Number of duplicate copies
  - Total combined size
- Each group shows:
  - **Original** (⭐) - first copy
  - **Copies** (📄) - duplicates

**Step 5**: Expand duplicate groups
- Click any group to expand
- View all found instances with details

---

### Method 3: Local Search & Filter

**Step 1**: Use the search bar at the bottom
- Search by filename: `photo`, `document`
- Search by location path: `Downloads`, `Desktop`, `Users`

**Step 2**: Press Enter or click "Search" button

**Step 3**: View filtered results
- Shows only matching duplicates
- Click "Clear" to reset filter

## 📊 Understanding Duplicate Results

### What You'll See for Each File

```
⭐ Original - photo.jpg
├─ FILE TYPE      : .jpg
├─ FILE SIZE      : 2.5 MB
├─ LOCATION       : C:\Users\Name\Pictures\photo.jpg
├─ CREATED        : 2 days ago
└─ STATUS         : ⚠️ Duplicate

📄 Copy - photo.jpg
├─ FILE TYPE      : .jpg
├─ FILE SIZE      : 2.5 MB
├─ LOCATION       : C:\Users\Name\Downloads\photo.jpg
├─ CREATED        : 1 day ago
└─ STATUS         : ⚠️ Duplicate

📄 Copy - photo.jpg
├─ FILE TYPE      : .jpg
├─ FILE SIZE      : 2.5 MB
├─ LOCATION       : D:\Backups\photo.jpg
├─ CREATED        : 5 hours ago
└─ STATUS         : ⚠️ Duplicate
```

### File Details Explained

| Field | Description |
|-------|-------------|
| **FILE NAME** | Exact filename including extension |
| **FILE TYPE** | File extension (.jpg, .pdf, .doc, etc.) |
| **FILE SIZE** | Size in bytes, shown as B/KB/MB/GB |
| **LOCATION** | Full absolute path on your system |
| **CREATED** | File creation date/timestamp |
| **STATUS** | ⭐ Original or 📄 Copy/Duplicate |

### Group Summary

```
Hash: abc123def456...
📦 Copies: 3                (3 identical files found)
💾 Total: 45.2 MB           (combined storage used)
⚠️ Wasted: 30.1 MB          (recoverable space = 2 × 15.1 MB)
```

## 📊 Understanding Duplicate Groups

### Group Information
```
Hash: abc123def456...
📦 Copies: 3               (number of identical copies)
💾 Total: 45.2 MB         (total storage used)
⚠️ Wasted: 30.1 MB        (storage that could be freed)
```

### File Details
Each file in the group shows:
- **⭐ Original**: The first/original copy of the file
- **📄 Copy**: All subsequent duplicates
- **📍 Location**: Full path where the file is stored
- **📊 Size**: File size in bytes
- **📅 Created**: File creation date

## 🎨 Visual Indicators

| Icon | Meaning |
|------|---------|
| 📁 | Folder/Directory scanning |
| 🔍 | Search functionality |
| ⭐ | Original file |
| 📄 | Duplicate/Copy |
| 💾 | Storage size |
| ⚠️ | Wasted storage |
| 📍 | File location/path |
| 📊 | Storage statistics |

## 🔧 Technical Details

### How It Works
1. **File Discovery**: Scans directory recursively (if enabled)
2. **Hash Computation**: Computes SHA256 hash of each file
3. **Duplicate Detection**: Groups files by identical hash values
4. **Storage Analysis**: Calculates wasted storage for each group
5. **Results Return**: Displays all duplicates with metadata

### API Endpoints

#### 1. Scan Directory Endpoint
```
POST /api/duplicates/scan-directory
```

**Request Body:**
```json
{
  "directory": "C:\\Users\\Downloads",
  "recursive": true,
  "extensions": null
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "directory": "C:\\Users\\Downloads",
    "scanned_files": 150,
    "total_duplicates": 5,
    "total_duplicate_files": 12,
    "duplicate_size_bytes": 450000000,
    "duplicate_groups": [
      {
        "file_hash": "abc123...",
        "total_copies": 3,
        "file_locations": [
          {
            "file_name": "photo.jpg",
            "file_location": "C:\\Users\\Downloads\\photo.jpg",
            "file_size": 2048576,
            "file_type": ".jpg",
            "created_at": 1234567890
          }
        ]
      }
    ]
  }
}
```

#### 2. Search by Filename Endpoint
```
POST /api/duplicates/search-by-filename
```

**Request Body:**
```json
{
  "filename": "photo.jpg",
  "search_paths": null
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "search_query": "photo.jpg",
    "total_files": 3,
    "total_duplicates": 3,
    "total_size_bytes": 7500000,
    "duplicate_groups": [
      {
        "file_hash": "abc123...",
        "total_copies": 3,
        "file_name": "photo.jpg",
        "file_type": ".jpg",
        "files": [
          {
            "file_name": "photo.jpg",
            "file_type": ".jpg",
            "file_size": 2500000,
            "file_location": "C:\\Users\\Downloads\\photo.jpg",
            "file_hash": "abc123...",
            "created_at": 1234567890,
            "status": "duplicate"
          }
        ],
        "total_storage_used": 7500000,
        "storage_wasted": 5000000
      }
    ]
  }
}
```

## 💡 Tips & Tricks

### Finding Large Duplicates
1. Scan your main storage folder (e.g., `C:\Users`)
2. Sort results by "Wasted" storage (largest first)
3. These are the best candidates for cleanup

### Common Duplicate Locations
- **Downloads**: Often has multiple copies of same file
- **Documents**: Backup/archive copies
- **Desktop**: Copy & paste operations
- **Cloud sync folders**: Different versions uploaded

### System Performance
- Large scans (500+ files) may take a few seconds
- Storage in RAM is minimal (hashes only, not full files)
- Safe operation - doesn't modify any files

## ⚙️ Configuration

### Supported File Types
All file types are supported:
- Images: `.jpg`, `.png`, `.gif`, `.bmp`, `.webp`
- Documents: `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`
- Archives: `.zip`, `.rar`, `.7z`, `.tar`
- Code: `.py`, `.js`, `.java`, `.cpp`
- And more...

### Exclusions
Files are automatically skipped:
- Hidden files (starting with `.`)
- System files
- Zero-byte files
- Files with access errors

## 🐛 Troubleshooting

### "Access Denied" Errors
- Run application with administrator privileges
- Ensure you have read permissions for the folder
- Try scanning a specific subfolder instead

### Slow Scanning
- Reduce scope: scan specific folders instead of entire drive
- Exclude subfolders: uncheck "Scan subfolders"
- Close other applications using disk

### No Duplicates Found
- Try scanning different directories
- Duplicates only found when 2+ identical files exist
- Check if files are actually identical (not just similar)

### Path Not Found
- Ensure path exists and is correctly formatted
- Use backslashes `\` on Windows
- Check for typos in folder names

## 📝 Notes

- Scans are **read-only** - no files are modified
- Results are temporary - refresh to rescan
- Large duplicate groups are expanded on click for performance
- All paths shown are absolute filesystem paths

---

**Version**: 1.0.0  
**Last Updated**: April 3, 2026  
**Status**: ✅ Production Ready
