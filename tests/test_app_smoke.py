import io
import os
import tempfile
import uuid
from pathlib import Path

import pytest

from app import create_app
from app.models.database import get_db
from app.services.monitor_service import monitor_status
from config.settings import TestingConfig


class SmokeTestConfig(TestingConfig):
    DATABASE_URL = f"sqlite:///{Path(tempfile.gettempdir()) / 'ddas_smoke_test.db'}"
    START_MONITOR_ON_BOOT = False
    SECRET_KEY = "test-secret-key"
    JWT_SECRET = "test-jwt-secret"


@pytest.fixture
def app():
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


def _register_and_login(client):
    username = f"smoke_{uuid.uuid4().hex[:8]}"
    client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "email": f"{username}@example.com"},
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
    response = client.get("/api/datasets")
    assert response.status_code == 401
    assert response.get_json()["code"] == "AUTH_REQUIRED"


def test_auth_flow_and_dataset_listing(client):
    username, headers = _register_and_login(client)
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.get_json()["data"]["username"] == username

    datasets_response = client.get("/api/datasets", headers=headers)
    assert datasets_response.status_code == 200
    assert isinstance(datasets_response.get_json()["data"], list)


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


def test_monitor_does_not_autostart_in_testing(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "monitor_user", "password": "secret123", "email": "monitor@example.com"},
    )
    assert response.status_code == 201
    assert monitor_status()["running"] is False
