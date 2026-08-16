import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-do-not-use-in-prod")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = 24

    _default_db_path = os.path.join(BASE_DIR, "instance", "vault.db")
    _db_url_env = os.getenv("DATABASE_URL")
    if _db_url_env and _db_url_env.startswith("sqlite:///") and not _db_url_env.startswith("sqlite:////"):
        # Resolve relative sqlite paths against BASE_DIR so it doesn't matter
        # what directory the app happens to be launched from.
        _rel_path = _db_url_env[len("sqlite:///"):]
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, _rel_path)}"
    else:
        SQLALCHEMY_DATABASE_URI = _db_url_env or f"sqlite:///{_default_db_path}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 20 * 1024 * 1024))  # 20 MB
    ALLOWED_EXTENSIONS = {"pdf"}

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # Free alternative: Google Gemini via Google AI Studio (aistudio.google.com/apikey).
    # If ANTHROPIC_API_KEY isn't set but GEMINI_API_KEY is, rag.py falls back to Gemini.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Genuinely free option, no billing/card required at all: Groq
    # (console.groq.com/keys). Runs open-weight models (Llama, etc.) on
    # custom inference hardware. Checked before Gemini in rag.py's fallback order.
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

    # RAG settings
    CHUNK_SIZE = 800          # characters per chunk
    CHUNK_OVERLAP = 150       # characters of overlap between chunks
    TOP_K = 5                 # number of chunks retrieved per question
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
