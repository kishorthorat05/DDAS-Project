"""
FileMonitor — watchdog-based directory watcher.
Detects new files, computes SHA-256 hash, checks repository, fires alerts.
"""
import os
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.services.dataset_service import (
    AlertService, DatasetService, HistoryService, ScanLogService
)
from app.utils.security import hash_file
from config.settings import get_config


def _config():
    return get_config()


class _DDASEventHandler(FileSystemEventHandler):
    """Handle filesystem events: compute hash, check for duplicates, log."""

    def on_created(self, event):
        if event.is_directory:
            return
        _process_file(event.src_path, triggered_by="watchdog")

    def on_moved(self, event):
        if event.is_directory:
            return
        _process_file(event.dest_path, triggered_by="watchdog_move")


def _process_file(file_path: str, triggered_by: str = "manual") -> dict:
    """
    Core pipeline:
    1. Compute hash
    2. Look up repository
    3. Register or flag duplicate
    4. Log everything
    Returns a result summary dict.
    """
    path = Path(file_path)
    file_name = path.name
    result = {
        "file_path": file_path,
        "file_name": file_name,
        "is_duplicate": False,
        "error": None,
        "triggered_by": triggered_by,
    }

    try:
        # Skip system/hidden files and temp files
        if file_name.startswith(".") or file_name.endswith((".tmp", ".part", ".crdownload")):
            return result

        file_hash = hash_file(file_path)
        file_size = path.stat().st_size
        file_type = path.suffix.lower()

        existing = DatasetService.get_by_hash(file_hash)

        if existing:
            result["is_duplicate"] = True

            # Create alert
            AlertService.create(
                title=f"Duplicate detected: {file_name}",
                message=(
                    f"File '{file_name}' matches '{existing['file_name']}' "
                    f"(originally added by {existing['user_name']} on {existing['download_timestamp'][:10]})"
                ),
                alert_type="duplicate",
                severity="warning",
                file_name=file_name,
                file_hash=file_hash,
                file_path=file_path,
                existing_dataset_id=existing["id"],
            )

            # Log history
            HistoryService.log(
                dataset_id=existing["id"],
                user_name="System",
                file_name=file_name,
                file_hash=file_hash,
                action="auto_scan",
                status="duplicate_detected",
                notes=f"Detected by {triggered_by}",
            )
        else:
            # Register as new dataset
            DatasetService.create(
                file_hash=file_hash,
                file_name=file_name,
                file_size=file_size,
                file_path=file_path,
                file_type=file_type,
                user_name="System",
            )

        # Scan log
        ScanLogService.log(
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            file_hash=file_hash,
            is_duplicate=result["is_duplicate"],
        )

    except PermissionError:
        result["error"] = "Permission denied"
        ScanLogService.log(file_path=file_path, file_name=file_name, error="Permission denied")
    except FileNotFoundError:
        result["error"] = "File not found (may have been moved)"
    except Exception as exc:
        result["error"] = str(exc)
        ScanLogService.log(file_path=file_path, file_name=file_name, error=str(exc))

    return result


def manual_scan(directory: str | None = None) -> dict:
    """Scan all files in a directory. Returns summary."""
    scan_dir = directory or _config().MONITORED_DIR
    results = {"scanned": 0, "duplicates": 0, "errors": 0, "directory": scan_dir}

    if not os.path.isdir(scan_dir):
        results["error"] = f"Directory not found: {scan_dir}"
        return results

    for entry in os.scandir(scan_dir):
        if entry.is_file():
            r = _process_file(entry.path, triggered_by="manual_scan")
            results["scanned"] += 1
            if r.get("is_duplicate"):
                results["duplicates"] += 1
            if r.get("error"):
                results["errors"] += 1

    return results


# ─────────────────────────── Observer management ─────────────────────────────

_observer: Observer | None = None
_observer_lock = threading.Lock()


def start_monitor(directory: str | None = None) -> bool:
    """Start the watchdog observer. Safe to call multiple times."""
    global _observer
    with _observer_lock:
        if _observer and _observer.is_alive():
            return False  # already running

        watch_dir = directory or _config().MONITORED_DIR
        if not os.path.isdir(watch_dir):
            os.makedirs(watch_dir, exist_ok=True)

        _observer = Observer()
        _observer.schedule(_DDASEventHandler(), watch_dir, recursive=False)
        _observer.start()
        print(f"[Monitor] Started watching: {watch_dir}")
        return True


def stop_monitor() -> None:
    global _observer
    with _observer_lock:
        if _observer and _observer.is_alive():
            _observer.stop()
            _observer.join(timeout=5)
            _observer = None
            print("[Monitor] Stopped.")


def monitor_status() -> dict:
    return {
        "running": bool(_observer and _observer.is_alive()),
        "directory": _config().MONITORED_DIR,
    }
