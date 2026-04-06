#!/usr/bin/env python
"""Quick test to verify chatbot is calling Gemini API properly."""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("CHATBOT API TEST")
print("=" * 70)

# Load environment
print("\n[1] Loading .env...")
from dotenv import load_dotenv
env_file = project_root / ".env"
load_dotenv(env_file, override=True)
api_key = os.getenv("GOOGLE_API_KEY", "").strip()
print(f"[1] API Key loaded: {api_key[:30]}... (len: {len(api_key)})")

# Test importing AI service
print("\n[2] Importing AI service...")
try:
    from app.services.ai_service import chat
    print("[2] AI service imported successfully")
except Exception as e:
    print(f"[2] FAILED: {e}")
    sys.exit(1)

# Test chat with no history
print("\n[3] Testing chat with Gemini API...")
test_message = "How do I upload a file to DDAS?"
history = []
context = ""

print(f"[3] Calling chat('{test_message[:40]}...', history={len(history)}, context='')")
print("-" * 70)

try:
    response = chat(test_message, history, context)
    print("-" * 70)
    print(f"\n[3] Response received ({len(response)} chars):")
    print("\n" + response[:500])
    if len(response) > 500:
        print(f"\n... [{len(response) - 500} more chars]")
    
    # Check if it's a static response
    if "👋 Hi! I'm IAS Chatbot" in response or "Uploading a File" in response:
        print("\n[ERROR] Still getting STATIC response! API not being called!")
        sys.exit(1)
    else:
        print("\n[SUCCESS] Got DYNAMIC response from Gemini API!")
        
except Exception as e:
    print(f"[3] FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST PASSED - Chatbot is using Gemini API!")
print("=" * 70)
