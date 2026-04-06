#!/usr/bin/env python
"""Simple env test without imports."""

import os
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent
env_file = project_root / ".env"

print(f"Project root: {project_root}")
print(f"Env file path: {env_file}")
print(f"Env file exists: {env_file.exists()}")

# Load explicitly
load_dotenv(env_file, override=True)
key = os.getenv("GOOGLE_API_KEY", "").strip()

print(f"\nAPI Key: {key[:40] if key else 'NOT FOUND'}...")
print(f"Key length: {len(key)}")
print(f"Key is valid: {len(key) >= 20}")

if len(key) >= 20:
    print("\n✓ SUCCESS - API key is properly configured!")
else:
    print("\n✗ FAIL - API key not found or too short!")
