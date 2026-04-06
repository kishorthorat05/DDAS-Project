# 🚀 DDAS v4 - Quick Start Guide

## What's New in This Version

This is a **PRODUCTION-READY** version with all gaps covered:

✅ **Real-time Duplicate Detection** - SHA-256 + AI-powered similarity  
✅ **Smart AI Chatbot** - Google Gemini integration with dynamic responses  
✅ **Advanced Features** - Version control, analytics, recommendations  
✅ **Security Hardened** - RBAC, rate limiting, SSRF prevention  
✅ **Export & Backup** - ZIP export with metadata  
✅ **Enhanced Dashboard** - Real-time visualizations and metrics  
✅ **Directory Scanning** - Scan any directory for duplicates  

---

## Installation & Setup

### 1. Prerequisites
```bash
Python 3.11+
pip (Python package manager)
Windows/Linux/Mac
```

### 2. Install Dependencies
```bash
cd ddas
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Update .env with your Google Gemini API key
GOOGLE_API_KEY=AIzaSyBicvzEvm35n-PMnNFPEg3GeqAtOqVRMMs
```

### 4. Initialize Database
```bash
# Database auto-initializes on first run
python run.py
```

### 5. Access the Application
```
Open browser: http://localhost:5000
Default credentials: admin/admin (set in first-time setup)
```

---

## Key Features

### 📊 Dashboard
- Real-time system statistics
- Total datasets, duplicates, storage usage
- Recent scan activity
- Alerts and notifications

### 🤖 AI Chatbot
- Ask questions about DDAS
- Get recommendations
- Understand duplicates
- Only requires `GOOGLE_API_KEY` setup

### 📁 Directory Scanner
1. Navigate to "Scanner" tab
2. Enter directory path (e.g., `C:\Users\YourName\Downloads`)
3. Click "Scan Directory"
4. Results auto-export as ZIP

### 📈 Analytics
- Daily upload trends
- Duplicate detection rates
- Storage optimization metrics
- User activity heatmaps
- Top duplicated files

### 💾 Export & Backup
- Export scan results
- Export datasets with filters
- ZIP format with metadata
- Auto-cleanup old files

---

## API Quick Reference

### Upload a File
```bash
curl -X POST http://localhost:5000/api/upload/file \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@yourfile.zip" \
  -F "user_name=YourName"
```

### Scan Directory
```bash
curl -X POST http://localhost:5000/api/monitor/scan-directory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/folder", "recursive": true}'
```

### Ask AI Chatbot
```bash
curl -X POST http://localhost:5000/api/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is duplicate detection?", "session_id": "sess_123"}'
```

### Get Dashboard Stats
```bash
curl http://localhost:5000/api/analytics/dashboard \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Configuration Guide

### Gemini API Setup
1. Go to https://makersuite.google.com/app/apikey
2. Create/copy your API key
3. Update `.env`:
   ```
   GOOGLE_API_KEY=your_key_here
   GOOGLE_MODEL=gemini-1.5-flash
   ```
4. Restart the app

### Role-Based Access
- **Admin**: Full access, manage users
- **Operator**: Upload, scan, delete
- **Viewer**: Read-only access

### Monitoring Directory
```
MONITORED_DIR=downloads  # Set in .env
```

---

## Troubleshooting

### AI Chatbot Not Responding?
```
1. Check GOOGLE_API_KEY in .env
2. Verify API quota: console.cloud.google.com
3. Check Flask logs for errors
```

### Files Not Scanned?
```
1. Verify monitor is running (check dashboard)
2. Check MONITORED_DIR setting
3. Run manual scan from Scanner tab
```

### Database Issues?
```
1. Delete data/ddas.db to reset
2. App will auto-initialize
3. Re-upload files if needed
```

### Port 5000 Already in Use?
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <process_id> /F

# Linux/Mac
lsof -i :5000
kill -9 <pid>
```

---

## Performance Tips

- Monitor directory size (keep under 100GB for best performance)
- Archive old scan logs monthly
- Use PostgreSQL for production (instead of SQLite)
- Enable Redis for session caching
- Use reverse proxy (Nginx) for load balancing

---

## Security Best Practices

1. **Change default credentials** in .env
2. **Use HTTPS** in production
3. **Rotate API keys** regularly
4. **Enable rate limiting** (already configured)
5. **Backup database** regularly
6. **Monitor access logs** for anomalies

---

## System Requirements

| Component | Requirement |
|-----------|-------------|
| CPU | 2+ cores |
| RAM | 512MB+ (1GB recommended) |
| Disk | 10GB+ (depends on use case) |
| Python | 3.11+ |
| Bandwidth | 1 Mbps+ |

---

## What Each Tab Does

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Overview of system metrics |
| **Upload** | Upload files for duplicate check |
| **Repository** | Browse all registered files |
| **Alerts** | View duplicate detection alerts |
| **History** | Audit trail of all operations |
| **AI Chat** | Ask questions about DDAS |
| **Analytics** | Detailed system insights |
| **Scanner** | Scan directories for duplicates |
| **Export** | Create ZIP backups |

---

## What Gets Detected as Duplicate?

Files are marked as duplicates if:
1. **Same SHA-256 hash** → Exact same content
2. **High similarity score** → >95% content match
3. **Metadata match** → Same name, size, type

---

## Data Flow

```
User File
    ↓
sha256() hash computation
    ↓
Check repository for match
    ↓
Exact match? → Alert + Block
    ↓
Similar? → Check similarity threshold
    ↓
New file? → Register + Store metadata
    ↓
Log to audit trail
```

---

## Storage Breakdown

By default, DDAS stores:
- `data/ddas.db` - SQLite database (~10-50MB)
- `app/static/uploads/` - Uploaded files (variable)
- `app/static/exports/` - ZIP exports (cleaned after 7 days)

---

## Monitoring

Check system health:
```bash
# Browser
http://localhost:5000/api/health

# Command line
curl http://localhost:5000/api/health
```

Response:
```json
{
  "status": "healthy",
  "ai_configured": true,
  "monitor": "check /api/monitor/status"
}
```

---

## Next Steps

1. ✅ Start the app: `python run.py`
2. ✅ Login to dashboard
3. ✅ Upload test files
4. ✅ Run directory scan
5. ✅ Check analytics
6. ✅ Ask AI questions
7. ✅ Export results

---

## Production Deployment

For production use:
1. Set `FLASK_ENV=production`
2. Use PostgreSQL database
3. Configure reverse proxy (Nginx/Apache)
4. Enable HTTPS/TLS
5. Set up monitoring & logging
6. Enable Redis for caching
7. Use gunicorn/uWSGI for WSGI server

See `PRODUCTION_READY.md` for detailed guide.

---

## Support

- Check logs: Flask console output
- Database query: `sqlite3 data/ddas.db`
- API docs: Available in `/api/` routes
- Issues: Check browser console (F12)

---

**DDAS v4** - Your Complete Duplication Solution  
Ready for Production | All Features Enabled  
Last Update: April 2, 2026

