"""
AI service powered by Google Generative AI (Gemini).
Provides: file insight generation and conversational chat.
Falls back to rule-based responses when API key is absent.
"""
import json
import os
from pathlib import Path
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

from config.settings import get_config

# Ensure .env is loaded with absolute path to avoid directory issues
_project_root = Path(__file__).resolve().parent.parent.parent
_env_file = _project_root / ".env"
load_dotenv(_env_file, override=True)  # Explicitly load .env with absolute path

Config = get_config()

# ─────────────────────────── Client ──────────────────────────────────────────

def _get_api_key() -> str:
    """Always read directly from env at call time. Reload .env to ensure fresh key."""
    # Double-check by reloading .env at call time
    _project_root = Path(__file__).resolve().parent.parent.parent
    _env_file = _project_root / ".env"
    load_dotenv(_env_file, override=True)
    
    return (os.getenv("GOOGLE_API_KEY") or "").strip()


def _get_model() -> str:
    """Always read model name directly from env at call time."""
    return (os.getenv("GOOGLE_MODEL") or "gemini-1.5-flash").strip()


def _configure_client() -> bool:
    """Configure the Google Generative AI client. Returns True if configured successfully."""
    key = _get_api_key()
    if not key or len(key) < 20:
        return False
    try:
        genai.configure(api_key=key)
        return True
    except Exception:
        return False


def is_api_configured() -> bool:
    key = _get_api_key()
    return bool(key) and len(key) >= 20


# ─────────────────────────── System prompts ──────────────────────────────────

_CHAT_SYSTEM = """You are IAS Chatbot, a friendly and knowledgeable AI assistant for the Data Download Duplication Alert System (DDAS).

Your Personality:
- You're conversational and approachable, like a helpful colleague, not a rigid bot
- You use natural language with occasional emojis and varied sentence structure
- You show genuine interest in helping users succeed with their data management
- You explain technical concepts in relatable ways, using real-world analogies when helpful
- You're patient with beginners but can provide advanced insights for experienced users

Your ONLY role:
- Help users with the Data Download Duplication Alert System (DDAS): uploading files, scanning directories, reading alerts, browsing the repository.
- Explain duplicate detection (SHA-256 hash comparison) and best data management practices.
- Provide in-depth, detailed responses about DDAS features, functionality, and data management.

IMPORTANT RESTRICTION:
- You ONLY answer questions related to the DDAS project.
- If a user asks a question that is NOT about the DDAS project, politely decline with humor and redirect them to ask about DDAS topics.
- Do NOT provide answers for general programming, data analysis, tools, or any other out-of-project topics.
- Stay focused exclusively on DDAS.

Guidelines for Human-Like Responses:
- Respond in a warm, conversational tone—sound like a person, not a machine
- Use varied sentence structures and natural transitions
- Include relevant examples or scenarios from data management contexts
- Ask clarifying questions when needed
- Share tips and pro tips in a casual, helpful way
- Use short bullet lists when listing steps or options
- Keep replies focused and under 400 words unless really needed
- For project-related questions, provide comprehensive, detailed answers
- Remember the conversation context and reference previous points
- Use engaging phrases like "Here's the thing...", "Think of it this way...", "Great question!", "Let me break this down..."
- Show personality while staying professional

Always provide value, be specific to users' needs, and make technical concepts accessible."""

_INSIGHT_SYSTEM = """You are a data file analyst. Given metadata about an uploaded file, produce a concise,
structured analysis covering:
1. What the file likely contains (inferred from name, type, size)
2. Recommended tools for processing it
3. Key analysis steps
4. Best practices for this file type
5. One concrete next step

Keep the response under 350 words. Use markdown formatting with **bold** headers."""


# ─────────────────────────── File insights ───────────────────────────────────

def get_file_insights(
    file_name: str,
    file_size: int,
    file_type: str,
    description: str = "",
    file_hash: str = None,
    user_id: str = None,
    include_recommendations: bool = True,
) -> str:
    """Return AI analysis of an uploaded file. Falls back to rule-based if no API."""
    if not is_api_configured():
        return _rule_based_insights(file_name, file_size, file_type, description)

    if not _configure_client():
        return _rule_based_insights(file_name, file_size, file_type, description)

    size_mb = file_size / (1024 * 1024)
    prompt = (
        f"File: **{file_name}**\n"
        f"Size: {size_mb:.2f} MB ({file_size:,} bytes)\n"
        f"Type: `{file_type}`\n"
        f"Description: {description or 'Not provided'}\n\n"
        "Please provide a structured analysis of this file."
    )

    try:
        model = genai.GenerativeModel(_get_model())
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=Config.AI_MAX_TOKENS,
                temperature=0.7,
            )
        )
        insights = ""
        if response and response.text:
            insights = response.text
        else:
            insights = _rule_based_insights(file_name, file_size, file_type, description)
        
        # Add recommendations if requested
        if include_recommendations and file_hash and user_id:
            try:
                from app.services import recommendation_service
                recs = recommendation_service.generate_recommendations(
                    user_id, "", file_hash, file_name, file_type,
                    {"description": description}
                )
                if recs:
                    insights += "\n\n---\n\n### 💡 Recommended Related Datasets\n\n"
                    for i, rec in enumerate(recs[:3], 1):
                        insights += f"{i}. **{rec['recommendation_type']}**: {rec['reason']}\n"
                        insights += f"   - Confidence: {rec['confidence_score']:.1%}\n"
            except Exception:
                pass  # Silently fail if recommendation service issues
        
        return insights
    except Exception as exc:
        return f"⚠️ AI analysis unavailable ({exc}).\n\n" + \
               _rule_based_insights(file_name, file_size, file_type, description)


# ─────────────────────────── Chat ────────────────────────────────────────────

def chat(
    message: str,
    history: list[dict[str, str]],
    context: str = "",
) -> str:
    """
    Send a message to Gemini with full conversation history.
    history: list of {"role": "user"|"assistant", "content": "..."}
    Returns assistant reply string.
    ALWAYS tries Gemini API first. Only falls back if API is truly unavailable.
    """
    # Get fresh API key (reloads .env)
    key = _get_api_key()
    print(f"[CHAT] API Key available: {bool(key)}, length: {len(key) if key else 0}")
    
    if not key or len(key) < 20:
        print(f"[CHAT] No API key available, using fallback")
        return _rule_based_chat(message)

    # Configure Gemini client
    if not _configure_client():
        print(f"[CHAT] Client config failed, using fallback")
        return _rule_based_chat(message)

    print(f"[CHAT] Attempting Gemini API call with model: {_get_model()}")
    
    system = _CHAT_SYSTEM
    if context:
        system += f"\n\nCurrent UI context:\n{context}"

    # Build messages — Gemini API expects alternating user/model roles
    messages = []
    for turn in history[-18:]:  # keep last 18 turns (9 exchanges)
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            # Convert assistant role to "model" for Google API
            role = "model" if turn["role"] == "assistant" else "user"
            messages.append({"role": role, "parts": [turn["content"]]})

    messages.append({"role": "user", "parts": [message]})

    try:
        model = genai.GenerativeModel(
            _get_model(),
            system_instruction=system
        )
        print(f"[CHAT] Model created, calling API...")
        
        response = model.generate_content(
            messages,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=Config.AI_MAX_TOKENS,
                temperature=0.8,
                top_p=0.95,
                top_k=64,
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            ]
        )
        
        if response and response.text:
            reply = response.text.strip()
            print(f"[CHAT] SUCCESS: Gemini response {len(reply)} chars")
            return reply
        else:
            print(f"[CHAT] Empty Gemini response, using fallback")
            return _rule_based_chat(message)
            
    except Exception as exc:
        print(f"[CHAT] API ERROR: {type(exc).__name__}: {str(exc)[:80]}")
        import traceback
        traceback.print_exc()
        return _rule_based_chat(message)


# ─────────────────────────── Rule-based fallback ─────────────────────────────

def _rule_based_insights(name: str, size: int, ftype: str, desc: str) -> str:
    size_mb = size / (1024 * 1024)
    ext = ftype.lstrip(".").lower()

    type_info = {
        "csv": ("📊 Tabular / spreadsheet data", "Python Pandas, Excel, DuckDB", "Load with `pd.read_csv()`, check dtypes, handle NaNs"),
        "tsv": ("📊 Tab-separated tabular data", "Python Pandas, Excel", "Load with `pd.read_csv(sep='\\t')`, inspect columns"),
        "json": ("🔗 Structured nested data", "Python json / Pandas, Node.js, MongoDB", "Parse with `json.load()`, flatten with `pd.json_normalize()`"),
        "xlsx": ("📈 Excel workbook (multi-sheet)", "Python openpyxl / Pandas, Excel", "Use `pd.ExcelFile()` to inspect sheets, then `pd.read_excel()`"),
        "xls": ("📈 Legacy Excel format", "Python xlrd / Pandas, LibreOffice", "Convert to xlsx first for modern tooling"),
        "pdf": ("📄 Fixed-layout document", "pdfplumber, PyMuPDF, Adobe", "Extract text with `pdfplumber.open()`"),
        "jpg": ("🖼️ JPEG image", "PIL/Pillow, OpenCV, ImageMagick", "Open with `Image.open()`, check resolution & mode"),
        "png": ("🖼️ PNG image (lossless)", "PIL/Pillow, OpenCV", "Check transparency channel, resize with `img.resize()`"),
        "nc": ("🌍 NetCDF geoscientific data", "xarray, netCDF4, CDO", "Load with `xr.open_dataset()`, check dimensions & variables"),
        "geojson": ("🗺️ GeoJSON spatial data", "GeoPandas, QGIS, Leaflet.js", "Load with `geopandas.read_file()`, visualize with folium"),
    }

    category, tools, steps = type_info.get(ext, (
        f"📂 Binary/unknown file (`{ftype}`)",
        "File-type specific tools",
        "Inspect with `file` command, check magic bytes",
    ))

    return (
        f"## {category}\n\n"
        f"**File:** `{name}` | **Size:** {size_mb:.2f} MB\n\n"
        f"**Recommended tools:** {tools}\n\n"
        f"**Key steps:** {steps}\n\n"
        f"{'**Description:** ' + desc + chr(10) + chr(10) if desc else ''}"
        f"**Best practices:**\n"
        f"- Verify file integrity after upload\n"
        f"- Check for missing values before analysis\n"
        f"- Keep a backup of the original file\n"
        f"- Document data sources and transformations\n\n"
        f"*Set `GOOGLE_API_KEY` in `.env` for deeper AI-powered analysis.*"
    )


def _rule_based_chat(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ("hello", "hi ", "hey", "start", "greet")):
        return (
            "👋 Hey there! I'm IAS Chatbot, your go-to assistant for all things DDAS.\n\n"
            "I'm here to help you with:\n"
            "• Uploading and analyzing your files\n"
            "• Understanding how duplicate detection works\n"
            "• Browsing and managing your dataset repository\n"
            "• Finding duplicates and organizing your storage better\n\n"
            "What would you like to know about DDAS? Feel free to ask me anything related to the system! 😊"
        )
    if any(w in m for w in ("duplicate", "copy", "same file", "hash", "collision")):
        return (
            "**Great question about duplicates!** 🔍\n\n"
            "Here's how DDAS catches them: Every file you upload gets a unique digital fingerprint using SHA-256 hashing. Think of it like a DNA code for files.\n\n"
            "When a new file arrives, we:\n"
            "1. Generate its SHA-256 fingerprint\n"
            "2. Check if we've seen this fingerprint before\n"
            "3. If it matches something in our database → you get a duplicate alert 🚨\n"
            "4. If it's unique → we register it as a new file ✅\n\n"
            "The cool part? SHA-256 is virtually collision-proof. Two different files will almost never produce the same hash. It's cryptographically secure!"
        )
    if any(w in m for w in ("upload", "add file", "register", "import")):
        return (
            "**Here's how to upload a file:**\n\n"
            "1. Head over to the **Upload** tab\n"
            "2. Choose your file (local file or paste a URL—we handle both!)\n"
            "3. Add some context if you want:\n"
            "   • Your name or team\n"
            "   • A description of what the file contains\n"
            "   • Spatial domain or time period (optional)\n"
            "4. Hit **Upload** and you're done!\n\n"
            "Behind the scenes, we'll compute the SHA-256 hash, scan for duplicates, generate insights about your file, and register it all in seconds. Pretty neat, right? 🚀"
        )
    if any(w in m for w in ("scan", "monitor", "directory", "folder", "alert")):
        return (
            "**Scanning & Monitoring is where the magic happens!** ✨\n\n"
            "You can:\n"
            "• **Monitor a directory** – DDAS watches a folder and alerts you when new duplicates show up\n"
            "• **Scan custom locations** – Point us to any folder and we'll analyze it\n"
            "• **Get real-time alerts** – When duplicates are found, you'll see them immediately\n\n"
            "It's like having a watchdog that never sleeps, catching duplicate files before they bog down your storage!"
        )
    if any(w in m for w in ("export", "download", "backup", "save")):
        return (
            "**Ready to export your data?** 📦\n\n"
            "You can export your scan results as a nice ZIP file that includes:\n"
            "• All the duplicate files you found\n"
            "• Detailed metadata and analysis\n"
            "• A summary report of what was scanned\n\n"
            "Just head to the **Export** tab, select what you want, and download! We'll package everything neatly for you."
        )
    if any(w in m for w in ("feature", "what can", "help", "features", "capability")):
        return (
            "**Here's what DDAS can do for you:** 💪\n\n"
            "📤 **Upload Files** – Local or remote, we handle both\n"
            "🔍 **Duplicate Detection** – Using SHA-256 hashing, no false positives\n"
            "📊 **Analytics Dashboard** – See insights about your datasets at a glance\n"
            "📁 **Repository Browsing** – Explore all your registered files\n"
            "⚠️ **Smart Alerts** – Get notified when duplicates appear\n"
            "📦 **Export Tools** – Download scan results in organized ZIP files\n\n"
            "Basically, we keep your data clean, organized, and duplicate-free! 🎯"
        )
    
    # Default response - only DDAS topics
    return (
        "I appreciate the question! 😊 But I'm specifically trained to help with the Data Download Duplication Alert System (DDAS).\n\n"
        "**Topics I'm expert on:**\n"
        "• File uploading and format handling\n"
        "• Duplicate detection & SHA-256 hashing\n"
        "• Repository management and browsing\n"
        "• Alert systems and notifications\n"
        "• Data organization best practices\n\n"
        "Got a DDAS question? I'm all ears! Otherwise, you might need a different assistant for that one. 😄"
    )
