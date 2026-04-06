"""
Basic tests for DDAS security utilities and core services.
Run: pytest tests/ -v
"""
import os
import sys
import tempfile
import pytest

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("FLASK_ENV", "testing")

from app.utils.security import (
    hash_file, hash_bytes, sanitize_filename, is_allowed_extension,
    sanitize_str, is_safe_url, validate_file_path,
    hash_password, verify_password,
    create_access_token, decode_token,
    RateLimiter,
)


# ─── Security utils ───────────────────────────────────────────────────────────

class TestHashFile:
    def test_hash_bytes_deterministic(self):
        assert hash_bytes(b"hello") == hash_bytes(b"hello")

    def test_hash_bytes_different_inputs(self):
        assert hash_bytes(b"hello") != hash_bytes(b"world")

    def test_hash_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content")
            path = f.name
        h = hash_file(path)
        assert len(h) == 64  # sha256 hex = 64 chars
        os.unlink(path)


class TestFilenameValidation:
    def test_allowed_extension(self):
        assert is_allowed_extension("data.csv")
        assert is_allowed_extension("report.xlsx")
        assert is_allowed_extension("image.png")

    def test_blocked_extension(self):
        assert not is_allowed_extension("script.exe")
        assert not is_allowed_extension("virus.bat")
        assert not is_allowed_extension("malware.sh")

    def test_sanitize_filename(self):
        assert "/" not in sanitize_filename("../../../etc/passwd")
        assert sanitize_filename("normal_file.csv") == "normal_file.csv"
        assert sanitize_filename("file with spaces.csv") == "file with spaces.csv"

    def test_validate_file_path(self):
        assert not validate_file_path("../etc/passwd")
        assert not validate_file_path("..\\windows\\system32")
        assert validate_file_path("/safe/path/file.csv")


class TestInputSanitization:
    def test_sanitize_str_xss(self):
        result = sanitize_str("<script>alert('xss')</script>")
        assert "<script>" not in result

    def test_sanitize_str_max_length(self):
        result = sanitize_str("a" * 1000, max_length=100)
        assert len(result) <= 100

    def test_sanitize_str_none(self):
        assert sanitize_str(None) == ""


class TestURLValidation:
    def test_blocks_private_ips(self):
        assert not is_safe_url("http://192.168.1.1/file.csv")
        assert not is_safe_url("http://10.0.0.1/file.csv")
        assert not is_safe_url("http://127.0.0.1/file.csv")
        assert not is_safe_url("http://localhost/file.csv")

    def test_allows_public_https(self):
        assert is_safe_url("https://example.com/data.csv")
        assert is_safe_url("https://data.gov/file.csv")

    def test_blocks_non_http(self):
        assert not is_safe_url("ftp://example.com/file.csv")
        assert not is_safe_url("file:///etc/passwd")


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "secure_password_123!"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes_same_password(self):
        pw = "my_password"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        # bcrypt salts produce different hashes
        assert h1 != h2
        # But both verify
        assert verify_password(pw, h1)
        assert verify_password(pw, h2)


class TestJWT:
    def test_create_and_decode(self):
        payload = {"sub": "user_123", "username": "test", "role": "viewer"}
        token = create_access_token(payload)
        decoded = decode_token(token)
        assert decoded["sub"] == "user_123"
        assert decoded["type"] == "access"

    def test_invalid_token_raises(self):
        import jwt
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("not.a.valid.token")


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            assert rl.is_allowed("key_test", max_requests=10, window_seconds=60)

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.is_allowed("key_block", max_requests=5, window_seconds=60)
        # 6th should be blocked
        assert not rl.is_allowed("key_block", max_requests=5, window_seconds=60)

    def test_different_keys_independent(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.is_allowed("key_a", max_requests=5, window_seconds=60)
        # key_b should still work
        assert rl.is_allowed("key_b", max_requests=5, window_seconds=60)
