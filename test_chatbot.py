#!/usr/bin/env python
"""
Quick verification script for DDAS chatbot integration.
Tests API key loading, module imports, and basic functionality.
"""

import os
import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_api_key():
    """Test 1: Verify API key is loaded"""
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        print("[FAIL] API Key: Not found in .env")
        return False
    if len(key) < 20:
        print("[FAIL] API Key: Invalid length")
        return False
    print(f"[PASS] API Key: Loaded successfully (length: {len(key)})")
    return True

def test_imports():
    """Test 2: Verify AI service imports"""
    try:
        from app.services.ai_service import is_api_configured, chat, _CHAT_SYSTEM
        print("[PASS] Imports: AI service modules loaded")
        return True
    except ImportError as e:
        print(f"[FAIL] Imports: {e}")
        return False

def test_configuration():
    """Test 3: Verify configuration status"""
    try:
        from app.services.ai_service import is_api_configured
        if is_api_configured():
            print("[PASS] Configuration: Gemini API is ready")
            return True
        else:
            print("[WARN] Configuration: API key configured but may need validation")
            return False
    except Exception as e:
        print(f"[FAIL] Configuration: {e}")
        return False

def test_system_prompt():
    """Test 4: Verify system prompt is human-like"""
    try:
        from app.services.ai_service import _CHAT_SYSTEM
        
        human_markers = [
            "conversational",
            "friendly",
            "approachable",
            "human-like",
            "relatable"
        ]
        
        prompt_lower = _CHAT_SYSTEM.lower()
        found_markers = sum(1 for marker in human_markers if marker in prompt_lower)
        
        if found_markers >= 3:
            print(f"[PASS] System Prompt: Human-like personality detected ({found_markers} markers)")
            return True
        else:
            print("[WARN] System Prompt: May need personality enhancement")
            return False
    except Exception as e:
        print(f"[FAIL] System Prompt: {e}")
        return False

def test_generation_config():
    """Test 5: Verify generation settings for variety"""
    try:
        from app.services.ai_service import chat
        import inspect
        
        source = inspect.getsource(chat)
        
        checks = {
            "temperature": "0.8" in source or "temperature=0.8" in source,
            "top_p": "top_p" in source,
            "top_k": "top_k" in source,
        }
        
        if all(checks.values()):
            print("[PASS] Generation Config: Optimized for natural responses")
            return True
        else:
            missing = [k for k, v in checks.items() if not v]
            print(f"[WARN] Generation Config: Missing optimizations: {missing}")
            return False
    except Exception as e:
        print(f"[FAIL] Generation Config: {e}")
        return False

def test_fallback_responses():
    """Test 6: Verify fallback responses are present"""
    try:
        from app.services.ai_service import _rule_based_chat
        import inspect
        
        source = inspect.getsource(_rule_based_chat)
        
        if "friendly" in source.lower() and "engaging" not in source.lower():
            # Check if fallback responses exist
            if "Hello" in source or "Hi" in source:
                print("[PASS] Fallback Responses: Human-like fallbacks configured")
                return True
        
        print("[WARN] Fallback Responses: May need verification")
        return False
    except Exception as e:
        print(f"[FAIL] Fallback Responses: {e}")
        return False

def run_all_tests():
    """Run all tests and summarize results"""
    print("\n" + "="*60)
    print("DDAS CHATBOT INTEGRATION VERIFICATION")
    print("="*60 + "\n")
    
    tests = [
        ("Step 1: API Key", test_api_key),
        ("Step 2: Module Imports", test_imports),
        ("Step 3: Configuration", test_configuration),
        ("Step 4: System Prompt", test_system_prompt),
        ("Step 5: Generation Config", test_generation_config),
        ("Step 6: Fallback Responses", test_fallback_responses),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        print("-" * 40)
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    status = "SUCCESS" if passed == total else "PARTIAL" if passed > 0 else "FAILED"
    print(f"RESULT: {status} ({passed}/{total} checks passed, {percentage:.0f}%)")
    print("="*60)
    
    if passed == total:
        print("\n[OK] Chatbot is ready to use!")
        print("\nNext Steps:")
        print("1. Start server: python run.py")
        print("2. Open http://localhost:5000")
        print("3. Click 'AI Chat' tab")
        print("4. Try asking: 'How do I upload a file?'")
    else:
        print("\n[WARN] Some checks failed. Review configuration.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
