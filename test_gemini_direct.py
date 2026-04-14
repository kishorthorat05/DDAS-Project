#!/usr/bin/env python
"""Manual Gemini API smoke test using the google-genai SDK."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    print("=" * 70)
    print("GEMINI API DIRECT TEST")
    print("=" * 70)

    print("\n[Step 1] Loading environment variables...")
    load_dotenv(override=True)

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    model = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash").strip()

    print(f"  API Key: {api_key[:30]}... (length: {len(api_key)})")
    print(f"  Model: {model}")

    if not api_key or len(api_key) < 20:
        print("\n[FAIL] API key is missing or invalid.")
        return 1

    print("\n[Step 2] Importing google.genai...")
    try:
        from google import genai
        from google.genai import types
        print("  [OK] Module imported")
    except Exception as exc:
        print(f"  [FAIL] {exc}")
        return 1

    print("\n[Step 3] Creating Gemini client...")
    try:
        client = genai.Client(api_key=api_key)
        print("  [OK] Client created")
    except Exception as exc:
        print(f"  [FAIL] {exc}")
        return 1

    print("\n[Step 4] Sending simple test message...")
    try:
        response = client.models.generate_content(
            model=model,
            contents="Hi, tell me in one sentence what DDAS stands for.",
            config=types.GenerateContentConfig(
                max_output_tokens=100,
                temperature=0.8,
                http_options=types.HttpOptions(timeout=20_000),
            ),
        )
        reply = getattr(response, "text", "") or ""
        if not reply.strip():
            print("  [FAIL] Empty response from Gemini")
            return 1
        print(f"  [OK] Response received ({len(reply.strip())} chars)")
        print(f"\n  Bot: {reply.strip()}\n")
    except Exception as exc:
        print(f"  [FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return 1

    print("[Step 5] Testing with system instructions...")
    try:
        system_prompt = (
            "You are a helpful DDAS assistant. "
            "Respond in a friendly conversational tone. "
            "Keep responses under 200 words."
        )
        response2 = client.models.generate_content(
            model=model,
            contents="How do I upload a file to DDAS?",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=150,
                temperature=0.8,
                http_options=types.HttpOptions(timeout=20_000),
            ),
        )
        reply2 = getattr(response2, "text", "") or ""
        if not reply2.strip():
            print("  [FAIL] Empty response from Gemini")
            return 1
        print(f"  [OK] Response received ({len(reply2.strip())} chars)")
        preview = reply2.strip()
        print(f"\n  Bot: {preview[:200]}...\n" if len(preview) > 200 else f"\n  Bot: {preview}\n")
    except Exception as exc:
        print(f"  [FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return 1

    print("=" * 70)
    print("[SUCCESS] Gemini API is working properly!")
    print("=" * 70)
    print("\nThe chatbot should now get dynamic responses.")
    print("Install/update dependencies: pip install -r requirements.txt")
    print("Start the server: python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
