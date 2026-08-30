# config/settings.py
# Project configuration — safe to commit to git.
# Credentials (API keys, passwords, tokens) go in .env — never here.

import os
from pathlib import Path


def _load_env_file(filepath: Path):
    """Carica il file .env nelle variabili d'ambiente senza librerie esterne."""
    if not filepath.is_file():
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Ignora righe vuote e commenti
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")  # Rimuove apici se presenti
            os.environ.setdefault(key, value)


# Carica .env dalla root del progetto
BASE_DIR = Path(__file__).resolve().parent.parent
_load_env_file(BASE_DIR / ".env")


# --- Scorer thresholds ---
MIN_REVIEW_SCORE = 4.0        # minimum average star rating
MIN_REVIEW_COUNT = 50         # minimum number of reviews

# --- Database ---
DB_PATH = os.getenv("DB_PATH", "data/smartcartlab.db")
SOCIAL_DB_PATH = os.getenv("SOCIAL_DB_PATH", "data/socialmanager.db")

# --- Schedule ---
PUBLISH_HOUR = 8              # hour to publish the daily pick (24h format)

# --- Credentials (read from .env) ---
KEEPA_API_KEY          = os.getenv("KEEPA_API_KEY")
TELEGRAM_BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID    = os.getenv("TELEGRAM_CHANNEL_ID")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

# --- WordPress ---
WORDPRESS_URL          = os.getenv("WORDPRESS_URL")
WORDPRESS_USER         = os.getenv("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD")

# --- LLM / Ollama ---
OLLAMA_URL             = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL           = os.getenv("OLLAMA_MODEL", "gemma3:4b")

# --- Mastodon ---
MASTODON_API_BASE_URL  = os.getenv("MASTODON_API_BASE_URL", "https://mastodon.social")
MASTODON_ACCESS_TOKEN  = os.getenv("MASTODON_ACCESS_TOKEN")

# --- Facebook ---
FACEBOOK_PAGE_ID       = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_ACCESS_TOKEN  = os.getenv("FACEBOOK_ACCESS_TOKEN")

# --- Dashboard params ---
APP_TIMEZONE = "Europe/Rome"
