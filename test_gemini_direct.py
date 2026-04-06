#!/usr/bin/env python
"""Test Gemini API directly to diagnose chatbot issues."""

import os
import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("GEMINI API DIRECT TEST")
print("=" * 70)

# Step 1: Load environment
print("\n[Step 1] Loading environment variables...")
from dotenv import load_dotenv
load_dotenv(override=True)

api_key = os.getenv("GOOGLE_API_KEY", "").strip()
model = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash").strip()

print(f"  API Key: {api_key[:30]}... (length: {len(api_key)})")
print(f"  Model: {model}")

if not api_key or len(api_key) < 20:
    print("\n[FAIL] API key is missing or invalid!")
    sys.exit(1)

# Step 2: Import Google API
print("\n[Step 2] Importing google.generativeai...")
try:
    import google.generativeai as genai
    print("  [OK] Module imported")
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

# Step 3: Configure client
print("\n[Step 3] Configuring Gemini client...")
try:
    genai.configure(api_key=api_key)
    print("  [OK] Client configured")
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

# Step 4: Create model
print("\n[Step 4] Creating GenerativeModel...")
try:
    gemini_model = genai.GenerativeModel(model)
    print(f"  [OK] Model created: {model}")
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

# Step 5: Test simple message
print("\n[Step 5] Sending test message to Gemini...")
test_message = "Hi, tell me in one sentence what DDAS stands for."

try:
    response = gemini_model.generate_content(
        test_message,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=100,
            temperature=0.8,
        )
    )
    
    if response and response.text:
        reply = response.text.strip()
        print(f"  [OK] Response received ({len(reply)} chars)")
        print(f"\n  Bot: {reply}\n")
    else:
        print(f"  [FAIL] Empty response from Gemini")
        sys.exit(1)
        
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: Test system instruction
print("[Step 6] Testing with system instructions...")
try:
    system_prompt = """You are a helpful DDAS assistant. Respond in a friendly, 
conversational tone. Keep responses under 200 words."""
    
    model_with_system = genai.GenerativeModel(
        model,
        system_instruction=system_prompt
    )
    
    response2 = model_with_system.generate_content(
        "How do I upload a file to DDAS?",
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=150,
            temperature=0.8,
        )
    )
    
    if response2 and response2.text:
        reply2 = response2.text.strip()
        print(f"  [OK] Response received ({len(reply2)} chars)")
        print(f"\n  Bot: {reply2[:200]}...\n" if len(reply2) > 200 else f"\n  Bot: {reply2}\n")
    else:
        print(f"  [FAIL] Empty response from Gemini")
        sys.exit(1)
        
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 70)
print("[SUCCESS] Gemini API is working properly! ✓")
print("=" * 70)
print("\nThe chatbot should now get dynamic responses.")
print("Start the server: python run.py")
print("Then test: http://localhost:5000/api/ai/chat")
