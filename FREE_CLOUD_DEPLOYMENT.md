# DDAS Free Cloud Deployment Guide

This guide deploys the DDAS Flask project from scratch with no required paid plan. Use it for demos, college/project submissions, and low-traffic testing. It is not a production-grade deployment because free cloud platforms usually sleep, expire, or limit persistent storage.

## Recommended Free Options

| Platform | Best for | Cost note | Main limitation |
| --- | --- | --- | --- |
| Render Free Web Service | easiest public cloud deployment | can run without paying if you stay inside free limits | service sleeps after idle time and local SQLite/uploads are lost after restart/redeploy |
| PythonAnywhere Free | simple Flask hosting without a card | free account available | 512 MiB disk, 1 web app, 1 web worker, app expires monthly unless renewed |

Avoid Fly.io and Railway if your requirement is strictly no money/no payment method. Fly.io says there is no current free account/free tier for new users. Railway is mainly trial/credit based, not a permanent no-cost deployment.

## Project Requirements

DDAS is a Python Flask app. It uses:

- `run.py` as the app entry point.
- `requirements.txt` for dependencies.
- `static/index.html` for the frontend.
- SQLite by default at `data/ddas.db`.
- Local uploads by default at `data/uploads`.

For free hosting, keep file sizes small. Uploaded files and SQLite databases can quickly exceed free storage limits.

## Step 1: Prepare The Project Locally

From the project folder:

```powershell
cd C:\Users\Kishor\Desktop\ddas
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

Confirm these work locally:

- Register
- Login
- Guest login
- Upload
- Profile page
- Export/download
- Duplicate scan/search

## Step 2: Create Safe Environment Values

Generate strong secrets:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
```

Use one output for `SECRET_KEY` and the other for `JWT_SECRET`.

Minimum cloud environment variables:

```env
FLASK_ENV=production
SECRET_KEY=your-generated-secret-key
JWT_SECRET=your-generated-jwt-secret
DATABASE_URL=sqlite:///data/ddas.db
START_MONITOR_ON_BOOT=false
SCAN_INTERVAL=5
GOOGLE_API_KEY=optional-google-api-key
GOOGLE_MODEL=gemini-2.5-flash
```

Set `CORS_ORIGINS` after you know your deployed URL:

```env
CORS_ORIGINS=https://your-app-name.onrender.com
```

For PythonAnywhere, use:

```env
CORS_ORIGINS=https://yourusername.pythonanywhere.com
```

Important: do not commit your real `.env` file to GitHub.

## Step 3: Push To GitHub

Create a GitHub repository, then run:

```powershell
git init
git add .
git commit -m "Prepare DDAS for deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

If the repository already exists:

```powershell
git add .
git commit -m "Update deployment files"
git push
```

## Option A: Deploy Free On Render

Render is the easiest option for this project.

### 1. Create the service

1. Go to `https://render.com`.
2. Sign up or log in.
3. Click `New`.
4. Choose `Web Service`.
5. Connect your GitHub repository.
6. Select this DDAS repository.

### 2. Configure Render

Use these settings:

```text
Name: ddas
Runtime: Python
Branch: main
Build Command: pip install -r requirements.txt
Start Command: gunicorn run:app
Instance Type: Free
```

### 3. Add environment variables

In Render dashboard, open your service:

```text
Environment -> Add Environment Variable
```

Add:

```env
FLASK_ENV=production
SECRET_KEY=your-generated-secret-key
JWT_SECRET=your-generated-jwt-secret
DATABASE_URL=sqlite:///data/ddas.db
START_MONITOR_ON_BOOT=false
SCAN_INTERVAL=5
GOOGLE_API_KEY=optional-google-api-key
GOOGLE_MODEL=gemini-2.5-flash
CORS_ORIGINS=https://your-app-name.onrender.com
```

### 4. Deploy

Click:

```text
Manual Deploy -> Deploy latest commit
```

After deploy, open:

```text
https://your-app-name.onrender.com
```

### 5. Render free limitations

Render Free is good for demos, but remember:

- The service sleeps after about 15 minutes without traffic.
- First request after sleep can take about a minute.
- Local files are ephemeral. SQLite DB and uploaded files can disappear after restart, redeploy, or spin-down.
- Free Render Postgres exists, but it expires after 30 days.
- Free services are suspended if monthly free limits are exhausted.

Because DDAS stores uploads and SQLite locally, Render Free should be treated as demo-only unless you later add durable external storage/database.

## Option B: Deploy Free On PythonAnywhere

PythonAnywhere is slower/tighter but better if you want simple free Flask hosting without cloud build complexity.

### 1. Create account

1. Go to `https://www.pythonanywhere.com`.
2. Create a free account.
3. Open `Consoles`.
4. Start a `Bash` console.

### 2. Clone the project

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If Python 3.11 is unavailable, use the newest Python version offered in your PythonAnywhere account.

### 3. Create `.env`

Inside the project folder:

```bash
nano .env
```

Add:

```env
FLASK_ENV=production
SECRET_KEY=your-generated-secret-key
JWT_SECRET=your-generated-jwt-secret
DATABASE_URL=sqlite:///data/ddas.db
START_MONITOR_ON_BOOT=false
SCAN_INTERVAL=5
GOOGLE_API_KEY=optional-google-api-key
GOOGLE_MODEL=gemini-2.5-flash
CORS_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
```

Save and exit.

### 4. Create the web app

1. Go to the PythonAnywhere `Web` tab.
2. Click `Add a new web app`.
3. Choose `Manual configuration`.
4. Choose Python 3.11 or the available version you used for the virtualenv.

### 5. Configure virtualenv

In the `Web` tab, set:

```text
Virtualenv: /home/YOUR_USERNAME/YOUR_REPO/venv
```

### 6. Edit WSGI file

In the `Web` tab, click the WSGI configuration file link. Replace its contents with:

```python
import os
import sys

project_home = "/home/YOUR_USERNAME/YOUR_REPO"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, ".env"))

from run import app as application
```

Replace `YOUR_USERNAME` and `YOUR_REPO`.

### 7. Reload the app

Click:

```text
Reload
```

Open:

```text
https://YOUR_USERNAME.pythonanywhere.com
```

### 8. PythonAnywhere free limitations

- 512 MiB disk space.
- 1 web app.
- 1 web worker.
- Monthly web app expiry/renewal.
- Free accounts may have restricted internet access.
- Keep uploads small.

## Post-Deployment Checklist

Open your deployed URL and test:

1. Register a new registered user.
2. Log out and log back in.
3. Continue as Guest.
4. Upload a small test file.
5. Check repository list.
6. Open Profile and save name/phone/theme/language.
7. Create/export scan results.
8. Download exported ZIP.
9. Confirm admin-only pages are hidden for registered users.
10. Confirm guest cannot access upload/export/profile.

## Common Problems

### Browser says `Failed to fetch`

This means the frontend could not reach the backend.

Check:

- The deployed app is running.
- You opened the cloud URL, not local `file:///...`.
- `CORS_ORIGINS` matches your exact deployed URL.
- Render/PythonAnywhere logs do not show startup errors.

### Render deploy fails on startup

Check:

```text
Start Command: gunicorn run:app
```

Also verify:

```text
FLASK_ENV=production
SECRET_KEY is set
JWT_SECRET is set
```

Production mode will fail intentionally if secrets are still the default placeholder values.

### Register fails

Check logs for database errors. On free platforms, SQLite must be writable:

```env
DATABASE_URL=sqlite:///data/ddas.db
```

Also confirm the `data` folder exists. The app creates it on boot, but disk limits can still fail writes.

### Uploaded files disappear on Render

This is expected on Render Free because the service filesystem is ephemeral. Use PythonAnywhere for small persistent demo files, or later upgrade/add external object storage.

### App sleeps or is slow to open

This is expected on free web services. Wait 30-90 seconds and refresh.

## Zero-Cost Recommendation

For a simple project demonstration:

1. Use Render Free if you need the fastest setup and public demo URL.
2. Use PythonAnywhere Free if you need small persistent files and can accept tighter limits.
3. Keep file uploads tiny.
4. Set `START_MONITOR_ON_BOOT=false` in the cloud.
5. Do not use the cloud free deployment as production storage.

## Sources Checked

- Render Free docs: `https://render.com/docs/free`
- PythonAnywhere Free Accounts docs: `https://help.pythonanywhere.com/pages/FreeAccountsFeatures/`
- Railway Free Trial docs: `https://docs.railway.com/pricing/free-trial`
- Fly.io pricing/cost docs: `https://fly.io/docs/about/pricing/`
