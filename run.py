"""
DDAS — Data Download Duplication Alert System
Entry point. Dotenv is loaded here first, before any app imports.
"""
from dotenv import load_dotenv
load_dotenv(override=False)   # must be FIRST — before importing app

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,   # reloader conflicts with watchdog thread
    )
