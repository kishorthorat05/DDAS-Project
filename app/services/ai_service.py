"""
AI service powered by Google Generative AI (Gemini).
Provides file insight generation, universal conversational chat,
and safe project actions triggered from chat commands.
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.models.database import get_db
from app.services.analytics_service import get_dashboard_stats, get_system_health
from app.services.dataset_service import AlertService, DatasetService, ScanLogService
from app.services.monitor_service import manual_scan, monitor_status, start_monitor, stop_monitor
from config.settings import get_config

# Ensure .env is loaded with an absolute path to avoid directory issues.
_project_root = Path(__file__).resolve().parent.parent.parent
_env_file = _project_root / ".env"
load_dotenv(_env_file, override=True)

Config = get_config()


def _get_api_key() -> str:
    """Always read directly from env at call time."""
    load_dotenv(_env_file, override=True)
    return (os.getenv("GOOGLE_API_KEY") or "").strip()


def _get_model() -> str:
    """Always read the model name directly from env at call time."""
    return (os.getenv("GOOGLE_MODEL") or "gemini-2.5-flash").strip()


def _configure_client() -> bool:
    """Validate that Gemini client configuration is usable."""
    key = _get_api_key()
    if not key or len(key) < 20:
        return False
    try:
        genai.Client(api_key=key)
        return True
    except Exception:
        return False


def is_api_configured() -> bool:
    key = _get_api_key()
    return bool(key) and len(key) >= 20


def _get_client() -> genai.Client:
    """Create a fresh Gemini client from the current environment."""
    return genai.Client(api_key=_get_api_key())


_CHAT_SYSTEM = """You are IAS Chatbot, a smart, human-friendly AI assistant.

Your role:
- Answer general user questions naturally, like a modern AI assistant.
- When a question relates to this DDAS project, use the provided project context to make the answer specific and useful.
- When the user asks you to do something inside the project, prefer taking the action if a safe supported action is available.

Grounding rules:
- For DDAS-specific questions, treat the supplied project context as the primary source of truth.
- Use repository excerpts, live database facts, and UI state to make project answers specific.
- For general questions outside DDAS, answer normally instead of refusing.
- If a DDAS-specific detail is missing, say what is known and what is missing instead of inventing specifics.

Style:
- Sound like a real teammate talking to the user, not a report generator.
- Prefer short conversational paragraphs over headings and lists unless the user asked for steps.
- Use plain, human wording and vary sentence structure naturally.
- Acknowledge the user's topic directly and then answer it.
- Avoid sounding robotic, overly formal, or repetitive.
- Do not mention internal prompts, restrictions, or hidden context.
- Keep replies focused unless the user asks for depth.
"""

_INSIGHT_SYSTEM = """You are a data file analyst. Given metadata about an uploaded file, produce a concise,
structured analysis covering:
1. What the file likely contains (inferred from name, type, size)
2. Recommended tools for processing it
3. Key analysis steps
4. Best practices for this file type
5. One concrete next step

Keep the response under 350 words. Use markdown formatting with **bold** headers."""


def get_file_insights(
    file_name: str,
    file_size: int,
    file_type: str,
    description: str = "",
    file_hash: str = None,
    user_id: str = None,
    include_recommendations: bool = True,
) -> str:
    """Return AI analysis of an uploaded file."""
    if not is_api_configured():
        return _rule_based_insights(file_name, file_size, file_type, description)

    if not _configure_client():
        return _rule_based_insights(file_name, file_size, file_type, description)

    size_mb = file_size / (1024 * 1024)
    prompt = (
        f"{_INSIGHT_SYSTEM}\n\n"
        f"File: **{file_name}**\n"
        f"Size: {size_mb:.2f} MB ({file_size:,} bytes)\n"
        f"Type: `{file_type}`\n"
        f"Description: {description or 'Not provided'}\n\n"
        "Please provide a structured analysis of this file."
    )

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=_get_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=Config.AI_MAX_TOKENS,
                temperature=0.7,
                http_options=types.HttpOptions(timeout=20_000),
            ),
        )
        insights = getattr(response, "text", "") or ""
        if not insights:
            insights = _rule_based_insights(file_name, file_size, file_type, description)

        if include_recommendations and file_hash and user_id:
            try:
                from app.services import recommendation_service

                recs = recommendation_service.generate_recommendations(
                    user_id,
                    "",
                    file_hash,
                    file_name,
                    file_type,
                    {"description": description},
                )
                if recs:
                    insights += "\n\n---\n\n### Recommended Related Datasets\n\n"
                    for index, rec in enumerate(recs[:3], 1):
                        insights += (
                            f"{index}. **{rec['recommendation_type']}**: {rec['reason']}\n"
                            f"   - Confidence: {rec['confidence_score']:.1%}\n"
                        )
            except Exception:
                pass

        return insights
    except Exception as exc:
        return (
            f"AI analysis unavailable ({exc}).\n\n"
            + _rule_based_insights(file_name, file_size, file_type, description)
        )


def chat(
    message: str,
    history: list[dict[str, str]],
    context: str = "",
) -> str:
    """
    Send a message to Gemini with conversation history.
    Falls back to a grounded local response when API access is unavailable.
    """
    project_context = _build_chat_context(message, context)

    key = _get_api_key()
    print(f"[CHAT] API Key available: {bool(key)}, length: {len(key) if key else 0}")

    if not key or len(key) < 20:
        print("[CHAT] No API key available, using grounded fallback")
        return _grounded_fallback_chat(message, history, project_context)

    if not _configure_client():
        print("[CHAT] Client config failed, using grounded fallback")
        return _grounded_fallback_chat(message, history, project_context)

    print(f"[CHAT] Attempting Gemini API call with model: {_get_model()}")

    system = _CHAT_SYSTEM
    if project_context:
        system += f"\n\nProject context:\n{project_context}"

    transcript_parts = [system]
    for turn in history[-18:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            speaker = "Assistant" if turn["role"] == "assistant" else "User"
            transcript_parts.append(f"{speaker}: {turn['content']}")
    transcript_parts.append(f"User: {message}")
    prompt = "\n\n".join(transcript_parts)

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=_get_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=Config.AI_MAX_TOKENS,
                temperature=0.85,
                top_p=0.95,
                top_k=64,
                http_options=types.HttpOptions(timeout=20_000),
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                ],
            ),
        )

        if response and getattr(response, "text", ""):
            reply = response.text.strip()
            print(f"[CHAT] SUCCESS: Gemini response {len(reply)} chars")
            return reply

        print("[CHAT] Empty Gemini response, using grounded fallback")
        return _grounded_fallback_chat(message, history, project_context)
    except Exception as exc:
        print(f"[CHAT] API ERROR: {type(exc).__name__}: {str(exc)[:120]}")
        return _grounded_fallback_chat(message, history, project_context)


def execute_chat_action(
    message: str,
    user_role: str = "",
    username: str = "",
) -> str | None:
    """Execute supported project actions from chat requests."""
    action = _detect_chat_action(message)
    if not action:
        return None

    kind = action["kind"]
    role = (user_role or "").lower()

    try:
        if kind == "monitor_status":
            status = monitor_status()
            running = "running" if status.get("running") else "stopped"
            return (
                f"The monitor is currently {running}. "
                f"It's watching `{status.get('directory', Config.MONITORED_DIR)}`."
            )

        if kind == "start_monitor":
            if role not in {"admin", "operator"}:
                return "I can see the request, but starting the monitor is only allowed for admin or operator users."
            started = start_monitor(action.get("directory"))
            if started:
                target_dir = action.get("directory") or Config.MONITORED_DIR
                return f"The monitor is now running and watching `{target_dir}`."
            return "The monitor was already running, so there was nothing new to start."

        if kind == "stop_monitor":
            if role != "admin":
                return "Stopping the monitor is restricted to admin users."
            stop_monitor()
            return "The monitor has been stopped."

        if kind == "scan":
            directory = action.get("directory")
            result = manual_scan(directory)
            if result.get("error"):
                return f"I tried to run the scan, but it failed: {result['error']}"
            return (
                f"Scan finished for `{result.get('directory')}`. "
                f"I checked {result.get('scanned', 0)} files, found {result.get('duplicates', 0)} duplicates, "
                f"and hit {result.get('errors', 0)} errors."
            )

        if kind == "dashboard":
            stats = get_dashboard_stats()
            return (
                f"Right now DDAS has {stats.get('total_datasets', 0)} datasets and "
                f"{stats.get('duplicates_detected', 0)} detected duplicates. "
                f"There are {stats.get('unread_alerts', 0)} unread alerts, and about "
                f"{stats.get('total_storage_gb', 0):.2f} GB stored."
            )

        if kind == "system_health":
            health = get_system_health()
            return (
                f"System health looks like this: database is `{health.get('database_status')}`, "
                f"pending alerts are {health.get('pending_alerts', 0)}, and scan errors in the last 24 hours are "
                f"{health.get('errors_24h', 0)}."
            )

        if kind == "recent_datasets":
            items = DatasetService.get_all(limit=5, offset=0)
            if not items:
                return "There aren't any datasets in the repository yet."
            names = ", ".join(f"{item['file_name']} ({item.get('file_type') or 'unknown'})" for item in items)
            return f"The most recent datasets are: {names}."

        if kind == "alerts":
            unread_only = bool(action.get("unread_only"))
            alerts = AlertService.get_all(unread_only=unread_only, limit=5)
            if not alerts:
                return "There are no matching alerts right now."
            titles = ", ".join(f"{item['title']} [{item.get('severity', 'info')}]" for item in alerts)
            if unread_only:
                return f"The latest unread alerts are: {titles}."
            return f"The latest alerts are: {titles}."

        if kind == "scan_logs":
            logs = ScanLogService.get_recent(limit=5)
            if not logs:
                return "There are no recent scan logs yet."
            lines = ", ".join(
                f"{log.get('file_name') or Path(log.get('file_path', '')).name or 'unknown file'}"
                f"{' (duplicate)' if log.get('is_duplicate') else ''}"
                for log in logs
            )
            return f"The latest scan activity includes: {lines}."
    except Exception as exc:
        return f"I tried to run that project action, but it failed: {exc}"

    return None


def _tokenize_for_search(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", text.lower())
    stop_words = {
        "about", "after", "again", "also", "any", "are", "can", "chat", "could",
        "data", "ddas", "does", "for", "from", "give", "how", "into", "like", "more",
        "need", "not", "project", "relative", "response", "should", "static", "system",
        "that", "the", "their", "them", "there", "this", "use", "what", "when", "with",
        "you", "your",
    }
    unique: list[str] = []
    for token in tokens:
        if token in stop_words or token in unique:
            continue
        unique.append(token)
    return unique[:8]


def _extract_directory(message: str) -> str | None:
    patterns = [
        r"(?:in|for|on|from)\s+([A-Za-z]:\\[^\n]+)",
        r"(?:in|for|on|from)\s+([.]{0,2}[\\/][^\n]+)",
        r"(?:in|for|on|from)\s+([A-Za-z0-9_./\\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1).strip().strip(' ."\'')
    return None


def _detect_chat_action(message: str) -> dict | None:
    text = message.strip()
    lowered = text.lower()

    if any(phrase in lowered for phrase in ("monitor status", "status of monitor", "is monitor running")):
        return {"kind": "monitor_status"}

    if any(phrase in lowered for phrase in ("start monitor", "turn on monitor", "enable monitor")):
        return {"kind": "start_monitor", "directory": _extract_directory(text)}

    if any(phrase in lowered for phrase in ("stop monitor", "turn off monitor", "disable monitor")):
        return {"kind": "stop_monitor"}

    if re.search(r"\b(scan|run scan|scan folder|scan directory|scan downloads)\b", lowered):
        return {"kind": "scan", "directory": _extract_directory(text)}

    if any(phrase in lowered for phrase in ("dashboard stats", "show dashboard", "analytics summary", "project stats")):
        return {"kind": "dashboard"}

    if any(phrase in lowered for phrase in ("system health", "health status", "check health")):
        return {"kind": "system_health"}

    if any(phrase in lowered for phrase in ("recent datasets", "show datasets", "list datasets", "latest datasets")):
        return {"kind": "recent_datasets"}

    if any(phrase in lowered for phrase in ("unread alerts", "show unread alerts")):
        return {"kind": "alerts", "unread_only": True}

    if any(phrase in lowered for phrase in ("show alerts", "latest alerts", "list alerts")):
        return {"kind": "alerts", "unread_only": False}

    if any(phrase in lowered for phrase in ("scan logs", "recent scans", "latest scans")):
        return {"kind": "scan_logs"}

    return None


def _safe_read_text(path: Path, max_chars: int = 7000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def _candidate_context_files() -> list[Path]:
    candidates = [
        _project_root / "README.md",
        _project_root / "FEATURES.md",
        _project_root / "QUICK_START.md",
        _project_root / "CHATBOT_GUIDE.md",
        _project_root / "app" / "api" / "routes.py",
        _project_root / "app" / "services" / "ai_service.py",
        _project_root / "app" / "services" / "dataset_service.py",
        _project_root / "app" / "services" / "monitor_service.py",
        _project_root / "app" / "services" / "analytics_service.py",
        _project_root / "app" / "models" / "database.py",
        _project_root / "static" / "index.html",
    ]
    return [path for path in candidates if path.exists()]


def _extract_relevant_snippets(message: str) -> list[str]:
    tokens = _tokenize_for_search(message)
    scored: list[tuple[int, str]] = []

    for path in _candidate_context_files():
        text = _safe_read_text(path)
        if not text:
            continue

        lowered_text = text.lower()
        file_score = sum(lowered_text.count(token) for token in tokens) if tokens else 0
        if tokens and file_score == 0:
            continue

        snippets: list[str] = []
        lines = text.splitlines()
        for index, line in enumerate(lines):
            lowered_line = line.lower()
            if not tokens or any(token in lowered_line for token in tokens):
                start = max(0, index - 1)
                end = min(len(lines), index + 2)
                excerpt = " ".join(part.strip() for part in lines[start:end] if part.strip())
                excerpt = re.sub(r"\s+", " ", excerpt)
                if excerpt and excerpt not in snippets:
                    snippets.append(excerpt[:260])
            if len(snippets) >= 2:
                break

        if not snippets and not tokens:
            fallback_excerpt = re.sub(r"\s+", " ", text)[:260]
            if fallback_excerpt:
                snippets.append(fallback_excerpt)

        for snippet in snippets:
            scored.append((file_score + 1, f"{path.relative_to(_project_root)}: {snippet}"))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [snippet for _, snippet in scored[:6]]


def _fetch_live_project_state() -> list[str]:
    context_parts: list[str] = []
    try:
        with get_db() as conn:
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_datasets,
                    COALESCE(SUM(file_size), 0) AS total_size,
                    COUNT(DISTINCT file_type) AS file_types
                FROM datasets
                """
            ).fetchone()
            if totals:
                context_parts.append(
                    "Repository stats: "
                    f"{totals['total_datasets']} datasets, "
                    f"{totals['file_types']} file types, "
                    f"{totals['total_size']} bytes stored."
                )

            recent_files = conn.execute(
                """
                SELECT file_name, file_type, user_name, created_at
                FROM datasets
                ORDER BY created_at DESC
                LIMIT 5
                """
            ).fetchall()
            if recent_files:
                recent_summary = ", ".join(
                    f"{row['file_name']} ({row['file_type'] or 'unknown'}, by {row['user_name']})"
                    for row in recent_files
                )
                context_parts.append(f"Recent datasets: {recent_summary}.")

            recent_alerts = conn.execute(
                """
                SELECT title, severity
                FROM alerts
                ORDER BY created_at DESC
                LIMIT 3
                """
            ).fetchall()
            if recent_alerts:
                alert_summary = ", ".join(
                    f"{row['title']} [{row['severity']}]"
                    for row in recent_alerts
                )
                context_parts.append(f"Recent alerts: {alert_summary}.")
    except Exception as exc:
        context_parts.append(f"Live database context unavailable: {type(exc).__name__}.")

    return context_parts


def _build_chat_context(message: str, ui_context: str = "") -> str:
    context_parts = _fetch_live_project_state()
    snippets = _extract_relevant_snippets(message)

    if snippets:
        context_parts.append("Relevant repository excerpts:")
        context_parts.extend(f"- {snippet}" for snippet in snippets)

    if ui_context:
        context_parts.append(f"UI context: {ui_context}")

    return "\n".join(context_parts[:14])


def _grounded_fallback_chat(message: str, history: list[dict[str, str]], project_context: str) -> str:
    lowered = message.lower()

    if any(word in lowered for word in ("hello", "hi", "hey")):
        return "Hi. I'm here and ready to help. Ask me anything, and if Gemini is available you'll get a full dynamic reply."

    if any(word in lowered for word in ("upload", "file", "import")):
        return (
            "You can upload a file from the Upload section of the app. "
            "Choose the file, submit it, and DDAS will hash it, check for duplicates, "
            "store the metadata, and generate AI insights when Gemini is available."
        )

    if any(word in lowered for word in ("duplicate", "duplicates", "hash", "same file")):
        return (
            "DDAS checks duplicates by generating a SHA-256 hash for each file and comparing it with files already in the repository. "
            "If the hash matches an existing file, the system flags it as a duplicate."
        )

    return (
        "I couldn't get a live Gemini response just now, so I'm using a simple local reply instead. "
        "Your Gemini API integration is already wired into the chatbot through `GOOGLE_API_KEY` and `GOOGLE_MODEL` in `.env`. "
        "Once the Gemini request succeeds from your running app, the chatbot will answer naturally and dynamically like a normal conversation."
    )


def _rule_based_insights(name: str, size: int, ftype: str, desc: str) -> str:
    size_mb = size / (1024 * 1024)
    ext = ftype.lstrip(".").lower()

    type_info = {
        "csv": ("Tabular or spreadsheet data", "Python Pandas, Excel, DuckDB", "Load with `pd.read_csv()`, inspect columns, handle missing values."),
        "tsv": ("Tab-separated tabular data", "Python Pandas, Excel", "Load with `pd.read_csv(sep='\\t')` and inspect column types."),
        "json": ("Structured nested data", "Python json, Pandas, Node.js", "Parse with `json.load()` and normalize nested fields if needed."),
        "xlsx": ("Excel workbook", "Python openpyxl, Pandas, Excel", "Use `pd.ExcelFile()` to inspect sheets before loading."),
        "xls": ("Legacy Excel workbook", "xlrd, Pandas, LibreOffice", "Convert to xlsx if you need modern tooling."),
        "pdf": ("Fixed-layout document", "pdfplumber, PyMuPDF, Adobe tools", "Extract text first, then validate page structure."),
        "jpg": ("JPEG image", "Pillow, OpenCV, ImageMagick", "Inspect resolution, orientation, and metadata."),
        "png": ("PNG image", "Pillow, OpenCV", "Check transparency and dimensions before processing."),
        "nc": ("NetCDF scientific data", "xarray, netCDF4, CDO", "Open with `xr.open_dataset()` and inspect dimensions."),
        "geojson": ("GeoJSON spatial data", "GeoPandas, QGIS, Leaflet", "Load with `geopandas.read_file()` and validate geometry."),
    }

    category, tools, steps = type_info.get(
        ext,
        (
            f"Unknown or binary file (`{ftype}`)",
            "File-type specific tools",
            "Inspect file metadata and magic bytes before processing.",
        ),
    )

    description_line = f"**Description:** {desc}\n\n" if desc else ""
    return (
        f"## {category}\n\n"
        f"**File:** `{name}`\n"
        f"**Size:** {size_mb:.2f} MB\n"
        f"**Recommended tools:** {tools}\n\n"
        f"**Key steps:** {steps}\n\n"
        f"{description_line}"
        f"**Best practices:**\n"
        f"- Verify integrity after upload.\n"
        f"- Keep the original file untouched.\n"
        f"- Record source and transformation details.\n\n"
        f"*Set `GOOGLE_API_KEY` in `.env` for deeper AI-powered analysis.*"
    )
