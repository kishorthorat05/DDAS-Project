import io
import os
import tempfile
import uuid
from pathlib import Path

import pytest

from app import create_app
from app.models.database import get_db
from app.services.monitor_service import monitor_status
from app.utils.security import _rate_limiter
from config.settings import TestingConfig


class SmokeTestConfig(TestingConfig):
    DATABASE_URL = f"sqlite:///{Path(tempfile.gettempdir()) / 'ddas_smoke_test.db'}"
    START_MONITOR_ON_BOOT = False
    SECRET_KEY = "test-secret-key"
    JWT_SECRET = "test-jwt-secret"


@pytest.fixture
def app():
    _rate_limiter._store.clear()
    app = create_app(config_object=SmokeTestConfig)
    with get_db() as conn:
        conn.execute("DELETE FROM download_history")
        conn.execute("DELETE FROM alerts")
        conn.execute("DELETE FROM scan_logs")
        conn.execute("DELETE FROM datasets")
        conn.execute("DELETE FROM users")
    app.config["TESTING"] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, role="registered"):
    username = f"smoke_{uuid.uuid4().hex[:8]}"
    client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "email": f"{username}@example.com", "role": role},
    )
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "secret123"},
    )
    payload = response.get_json()
    return username, {"Authorization": f"Bearer {payload['data']['access_token']}"}


def test_health_endpoint_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_protected_routes_require_auth(client):
    response = client.get("/api/export/list")
    assert response.status_code == 401
    assert response.get_json()["code"] == "AUTH_REQUIRED"


def test_guest_profile_and_public_read_only_access(client):
    guest_response = client.post("/api/auth/guest", json={})
    assert guest_response.status_code == 200
    guest = guest_response.get_json()["data"]["user"]
    assert guest["role"] == "guest"
    assert "view_dashboard" in guest["profile"]["permissions"]

    datasets_response = client.get("/api/datasets")
    assert datasets_response.status_code == 200


def test_auth_flow_and_dataset_listing(client):
    username, headers = _register_and_login(client)
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    user_data = me_response.get_json()["data"]
    assert user_data["username"] == username
    assert user_data["role"] == "registered"
    assert "upload" in user_data["profile"]["permissions"]

    datasets_response = client.get("/api/datasets", headers=headers)
    assert datasets_response.status_code == 200
    assert isinstance(datasets_response.get_json()["data"], list)


def test_only_registered_and_admin_can_register(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "legacy_role", "password": "secret123", "role": "viewer"},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_ROLE"


def test_first_admin_can_register_with_admin_profile(client):
    username, headers = _register_and_login(client, role="admin")
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    user_data = me_response.get_json()["data"]
    assert user_data["username"] == username
    assert user_data["role"] == "admin"
    assert "*" in user_data["profile"]["permissions"]


def test_history_is_scoped_to_current_user(client):
    user_one, headers_one = _register_and_login(client)
    user_two, headers_two = _register_and_login(client)

    with get_db() as conn:
        user_one_id = conn.execute("SELECT id FROM users WHERE username = ?", (user_one,)).fetchone()["id"]
        user_two_id = conn.execute("SELECT id FROM users WHERE username = ?", (user_two,)).fetchone()["id"]
        conn.execute(
            """INSERT INTO download_history
               (user_id, user_name, file_name, file_hash, action, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_one_id, user_one, "one.csv", "hash-one", "web_upload", "success"),
        )
        conn.execute(
            """INSERT INTO download_history
               (user_id, user_name, file_name, file_hash, action, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_two_id, user_two, "two.csv", "hash-two", "web_upload", "success"),
        )
        conn.execute(
            """INSERT INTO download_history
               (user_id, user_name, file_name, file_hash, action, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (None, user_one, "legacy-name-only.csv", "hash-legacy", "web_upload", "success"),
        )

    response_one = client.get("/api/history?limit=100", headers=headers_one)
    assert response_one.status_code == 200
    files_one = {row["file_name"] for row in response_one.get_json()["data"]}
    assert files_one == {"one.csv"}

    response_two = client.get("/api/history?limit=100", headers=headers_two)
    assert response_two.status_code == 200
    files_two = {row["file_name"] for row in response_two.get_json()["data"]}
    assert files_two == {"two.csv"}


def test_scan_logs_are_scoped_to_current_user(client):
    user_one, headers_one = _register_and_login(client)
    user_two, headers_two = _register_and_login(client)

    with get_db() as conn:
        user_one_id = conn.execute("SELECT id FROM users WHERE username = ?", (user_one,)).fetchone()["id"]
        user_two_id = conn.execute("SELECT id FROM users WHERE username = ?", (user_two,)).fetchone()["id"]
        conn.execute(
            """INSERT INTO scan_logs
               (user_id, user_name, file_path, file_name, file_size, file_hash, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_one_id, user_one, "/tmp/one.csv", "one.csv", 10, "hash-one", 0),
        )
        conn.execute(
            """INSERT INTO scan_logs
               (user_id, user_name, file_path, file_name, file_size, file_hash, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_two_id, user_two, "/tmp/two.csv", "two.csv", 20, "hash-two", 0),
        )

    response_one = client.get("/api/scan-logs?limit=100", headers=headers_one)
    assert response_one.status_code == 200
    files_one = {row["file_name"] for row in response_one.get_json()["data"]}
    assert files_one == {"one.csv"}

    response_two = client.get("/api/scan-logs?limit=100", headers=headers_two)
    assert response_two.status_code == 200
    files_two = {row["file_name"] for row in response_two.get_json()["data"]}
    assert files_two == {"two.csv"}


def test_analytics_uses_scan_log_storage_and_duplicate_bytes(client):
    username, _ = _register_and_login(client)

    with get_db() as conn:
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
        conn.execute(
            """INSERT INTO scan_logs
               (user_id, user_name, file_path, file_name, file_size, file_hash, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, "/tmp/analytics-new.csv", "analytics-new.csv", 2_500_000, "analytics-new", 0),
        )
        conn.execute(
            """INSERT INTO scan_logs
               (user_id, user_name, file_path, file_name, file_size, file_hash, is_duplicate)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, "/tmp/analytics-dupe.csv", "analytics-dupe.csv", 1_500_000, "analytics-dupe", 1),
        )

    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total_storage_bytes"] >= 4_000_000
    assert data["bandwidth_saved_bytes"] >= 1_500_000


def test_dataset_detail_history_is_scoped_to_current_user(client):
    user_one, headers_one = _register_and_login(client)
    user_two, _ = _register_and_login(client)

    with get_db() as conn:
        user_one_id = conn.execute("SELECT id FROM users WHERE username = ?", (user_one,)).fetchone()["id"]
        user_two_id = conn.execute("SELECT id FROM users WHERE username = ?", (user_two,)).fetchone()["id"]
        dataset_id = "dataset-history-scope"
        conn.execute(
            """INSERT INTO datasets
               (id, file_hash, file_name, file_size, file_path, file_type, user_id, user_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (dataset_id, "dataset-scope-hash", "shared.csv", 10, "/tmp/shared.csv", ".csv", user_one_id, user_one),
        )
        conn.execute(
            """INSERT INTO download_history
               (dataset_id, user_id, user_name, file_name, file_hash, action, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (dataset_id, user_one_id, user_one, "one-dataset.csv", "hash-one-dataset", "download_attempt", "success"),
        )
        conn.execute(
            """INSERT INTO download_history
               (dataset_id, user_id, user_name, file_name, file_hash, action, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (dataset_id, user_two_id, user_two, "two-dataset.csv", "hash-two-dataset", "download_attempt", "success"),
        )

    response = client.get(f"/api/datasets/{dataset_id}", headers=headers_one)
    assert response.status_code == 200
    history_files = {row["file_name"] for row in response.get_json()["data"]["history"]}
    assert history_files == {"one-dataset.csv"}


def test_file_upload_registers_dataset(client):
    _, headers = _register_and_login(client)
    response = client.post(
        "/api/upload/file",
        headers=headers,
        data={
            "user_name": "Smoke Tester",
            "description": "sample",
            "file": (io.BytesIO(b"hello world"), "sample.csv"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["data"]["is_duplicate"] is False
    assert payload["data"]["dataset"]["file_name"] == "sample.csv"

    scan_logs_response = client.get("/api/scan-logs?limit=10", headers=headers)
    assert scan_logs_response.status_code == 200
    scan_log_files = {row["file_name"] for row in scan_logs_response.get_json()["data"]}
    assert "sample.csv" in scan_log_files


def test_profile_update_and_password_change(client):
    username, headers = _register_and_login(client)
    profile_response = client.patch(
        "/api/profile/me",
        headers=headers,
        json={
            "full_name": "Profile Tester",
            "phone_number": "+919876543210",
            "language": "mr",
            "theme": "dark",
            "preferences": {"real_time_alerts": True},
        },
    )
    assert profile_response.status_code == 200
    profile_payload = profile_response.get_json()["data"]
    assert profile_payload["full_name"] == "Profile Tester"
    assert profile_payload["phone_number"] == "+919876543210"
    assert profile_payload["language"] == "mr"
    assert profile_payload["preferences"]["real_time_alerts"] is True

    avatar_response = client.post(
        "/api/profile/avatar",
        headers=headers,
        data={"avatar": (io.BytesIO(b"fake-png-data"), "avatar.png")},
        content_type="multipart/form-data",
    )
    assert avatar_response.status_code == 200
    avatar_url = avatar_response.get_json()["data"]["avatar_url"]
    assert avatar_url.startswith("/api/profile/avatar/")

    image_response = client.get(avatar_url)
    assert image_response.status_code == 200
    assert image_response.data == b"fake-png-data"

    two_factor_otp = client.post(
        "/api/auth/request-otp",
        headers=headers,
        json={"purpose": "mobile_2fa", "phone_number": "+919876543210"},
    )
    assert two_factor_otp.status_code == 200
    two_factor_code = two_factor_otp.get_json()["data"]["dev_otp"]

    two_factor_response = client.post(
        "/api/profile/2fa-mobile",
        headers=headers,
        json={"enabled": True, "phone_number": "+919876543210", "otp": two_factor_code},
    )
    assert two_factor_response.status_code == 200
    profile_payload = two_factor_response.get_json()["data"]
    assert profile_payload["preferences"]["two_factor_mobile_enabled"] is True

    password_otp = client.post(
        "/api/auth/request-otp",
        headers=headers,
        json={"purpose": "change_password", "phone_number": "+919876543210"},
    )
    assert password_otp.status_code == 200
    password_code = password_otp.get_json()["data"]["dev_otp"]

    password_response = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "secret123", "new_password": "newsecret123", "otp": password_code},
    )
    assert password_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "newsecret123"},
    )
    assert login_response.status_code == 200


def test_file_upload_allows_any_file_type(client):
    _, headers = _register_and_login(client)
    response = client.post(
        "/api/upload/file",
        headers=headers,
        data={
            "user_name": "Smoke Tester",
            "description": "binary sample",
            "file": (io.BytesIO(b"MZ fake executable content"), "tool.exe"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert response.get_json()["data"]["dataset"]["file_name"] == "tool.exe"


def test_scan_export_downloads_with_auth(client):
    _, headers = _register_and_login(client)
    export_response = client.post(
        "/api/export/scan-results",
        headers=headers,
        json={"scan_results": {"scanned": 1, "duplicates": 0, "errors": 0}},
    )
    assert export_response.status_code == 200
    filename = export_response.get_json()["data"]["zip_file"]

    download_response = client.get(
        f"/api/export/download?file={filename}",
        headers=headers,
    )
    assert download_response.status_code == 200
    assert "zip" in download_response.headers["Content-Type"]
    assert "attachment" in download_response.headers["Content-Disposition"]
    assert download_response.data.startswith(b"PK")


def test_monitor_does_not_autostart_in_testing(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "monitor_user", "password": "secret123", "email": "monitor@example.com"},
    )
    assert response.status_code == 201
    assert monitor_status()["running"] is False
