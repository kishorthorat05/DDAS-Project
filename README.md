# DDAS v3.0 — Data Download Duplication Alert System

Production-ready Flask application with SHA-256 duplicate detection, JWT auth,
Anthropic Claude AI integration, and a modern dark-theme SPA frontend.

---

## Quick Start

```bash
# 1. Clone / extract the project
cd ddas

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set GOOGLR_API_KEY, SECRET_KEY, JWT_SECRET, MONITORED_DIR

# 5. Run
python run.py
# → Open http://localhost:5000
```

---

## Project Structure

```
ddas/
├── run.py                      # Entry point
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   └── settings.py             # All config: dev / prod / test
├── app/
│   ├── __init__.py             # App factory + middleware
│   ├── api/
│   │   └── routes.py           # All API blueprints
│   ├── models/
│   │   └── database.py         # SQLite schema + connection helper
│   ├── services/
│   │   ├── dataset_service.py  # Dataset / History / Alert / ScanLog CRUD
│   │   ├── monitor_service.py  # Watchdog file monitor
│   │   └── ai_service.py       # google gemini integration
│   └── utils/
│       └── security.py         # JWT, bcrypt, rate limiter, validators
├── static/
│   └── index.html              # Full SPA frontend (single file)
├── data/                       # Created at runtime
│   ├── ddas.db                 # SQLite database
│   └── uploads/                # Uploaded files
└── tests/
    └── test_security.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | (insecure default) | Flask session secret |
| `JWT_SECRET` | ✅ | (insecure default) | JWT signing key |
| `GOOGLE_API_KEY` | ✅ for AI | — | API key from makersuite.google.com |
| `GOOGLE_MODEL` | No | `gemini-1.5-flash` | Gemini model string |
| `MONITORED_DIR` | No | `~/Downloads` | Directory to auto-monitor |
| `DATABASE_URL` | No | `sqlite:///data/ddas.db` | SQLite or PostgreSQL URL |
| `FLASK_ENV` | No | `development` | `development` / `production` |
| `CORS_ORIGINS` | No | `http://localhost:5000` | Comma-separated allowed origins |

---

## API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | Login → JWT tokens |
| `GET`  | `/api/auth/me` | Current user (requires auth) |

### Datasets
| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/datasets` | List all datasets |
| `GET`  | `/api/datasets/<id>` | Dataset detail + history |
| `GET`  | `/api/datasets/search?q=` | Search by name/domain/period |
| `GET`  | `/api/datasets/stats` | Repository statistics |
| `POST` | `/api/check-duplicate` | Check if hash exists |

### Upload
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload/file` | Multipart file upload |
| `POST` | `/api/upload/url` | Download & register from URL |

### Alerts
| Method | Endpoint | Description |
|---|---|---|
| `GET`   | `/api/alerts` | All alerts (add `?unread=1` for unread) |
| `PATCH` | `/api/alerts/<id>/read` | Mark single alert read |
| `POST`  | `/api/alerts/read-all` | Mark all read |

### Monitor
| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/monitor/status` | Monitor running state |
| `POST` | `/api/monitor/scan` | Trigger manual scan |
| `POST` | `/api/monitor/start` | Start monitor (operator+) |
| `POST` | `/api/monitor/stop` | Stop monitor (admin only) |
| `GET`  | `/api/scan-logs` | Recent scan log entries |
| `GET`  | `/api/history` | Download history |

### AI
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat` | Chat message (with session history) |
| `POST` | `/api/ai/chat/clear` | Clear chat session |
| `GET`  | `/api/ai/status` | AI config status |

---

## Security Features

- **SHA-256 file hashing** (upgraded from MD5)
- **JWT Bearer auth** — stateless, HS256-signed access tokens (8h) + refresh tokens (30d)
- **bcrypt password hashing** (pbkdf2:sha256:600000 rounds)
- **Role-based access control** — `admin` / `operator` / `viewer` roles
- **Input sanitization** — XSS escaping, SQL-safe search queries, filename sanitization
- **Rate limiting** — per-IP sliding window (in-memory; swap Redis for multi-worker)
- **URL validation** — blocks private/loopback IPs (SSRF prevention)
- **File extension allowlist** — rejects `.exe`, `.bat`, `.sh`, etc.
- **Security headers** — CSP, X-Frame-Options, HSTS (when HTTPS), referrer policy
- **Path traversal prevention** — `..` detection in file paths
- **Max file size** — 200 MB default (configurable)

---

## Production Deployment

```bash
# 1. Set production env vars (never commit .env!)
export FLASK_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

# 2. Run with gunicorn
gunicorn run:app --workers 4 --bind 0.0.0.0:5000 --timeout 120

# 3. Put nginx in front for HTTPS + static file serving
# 4. Use PostgreSQL: set DATABASE_URL=postgresql://user:pass@host/ddas
# 5. Use Redis for rate limiting in multi-worker setup
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## What Changed from v1 (app.py)

| Area | Before | After |
|---|---|---|
| Auth | None | JWT + bcrypt + roles |
| File hashing | MD5 | SHA-256 |
| Storage | Excel (.xlsx) | SQLite (WAL mode, FKs) |
| AI | OpenAI GPT-3.5 | Anthropic Claude |
| Rate limiting | None | Per-IP sliding window |
| Input validation | Minimal | XSS, SSRF, path traversal |
| Frontend | Jinja2 template | SPA (single HTML file) |
| File upload | No ext check | Extension allowlist |
| Structure | Single `app.py` | Layered: config/models/services/api |
