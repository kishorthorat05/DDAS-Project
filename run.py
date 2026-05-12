"""
DDAS — Data Download Duplication Alert System
Entry point. Dotenv is loaded here first, before any app imports.
"""
from dotenv import load_dotenv
load_dotenv(override=False)   # must be FIRST — before importing app

from app import create_app
import os
import socket


def get_lan_ip() -> str:
    """Return the best local network IP for opening the app from another device."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    lan_ip = get_lan_ip()
    print("DDAS is starting...", flush=True)
    print(f"Local URL:   http://127.0.0.1:{port}", flush=True)
    print(f"Network URL: http://{lan_ip}:{port}", flush=True)

    app = create_app()
    app.run(
        host="0.0.0.0",
        port=port,
        debug=bool(app.config.get("DEBUG", False)),
        use_reloader=False,   # reloader conflicts with watchdog thread
    )   
else:
    app = create_app()
