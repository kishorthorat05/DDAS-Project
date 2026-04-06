#!/usr/bin/env python
"""Direct test without IPython imports."""

if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path
    
    # Setup
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))
    
    # Load env with absolute path
    from dotenv import load_dotenv
    env_file = project_root / ".env"
    load_dotenv(env_file, override=True)
    
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    print(f"API Key found: {len(api_key) >= 20}")
    
    # Show what the server should use
    print("\nKEYS LOADED:")
    for k in ["GOOGLE_API_KEY", "GOOGLE_MODEL"]:
        v = os.getenv(k, "NOT_FOUND")
        if k == "GOOGLE_API_KEY":
            v = v[:30] + "..." if len(v) > 30 else v
        print(f"  {k}: {v}")
    
    # Now test by running the server
    print("\nStarting DDAS server...")
    print("Open http://localhost:5000 and test the chatbot")
    print("Logs will appear below:\n")
    
    # Suppress jupyter/ipython by setting env var
    os.environ["PYDEVD_WARN_SLOW_RESOLVE_TIMEOUT"] = "2"
    os.environ["JUPYTER_ENABLE_LAB"] = "false"
    
    # Import and start app
    from app import create_app
    app = create_app()
    
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
