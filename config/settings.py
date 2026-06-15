# config/settings.py
# Project configuration — safe to commit to git.
# Credentials (API keys, passwords, tokens) go in .env — never here.

import os

# --- Scorer thresholds ---
MIN_REVIEW_SCORE = 4.0       # minimum average star rating
MIN_REVIEW_COUNT = 50        # minimum number of reviews

# --- Database ---
DB_PATH = "data/smartcartlab.db"

# --- Schedule ---
PUBLISH_HOUR = 8             # hour to publish the daily pick (24h format)

# --- Credentials (read from .env) ---
KEEPA_API_KEY         = os.getenv("KEEPA_API_KEY")
TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID   = os.getenv("TELEGRAM_CHANNEL_ID")
WORDPRESS_URL         = os.getenv("WORDPRESS_URL")
WORDPRESS_USER        = os.getenv("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD")
