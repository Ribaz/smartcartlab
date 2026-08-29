# src/integrations/telegram.py
# Telegram integration for simple notifications and alerts.

import logging
import requests
from typing import Optional
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""


# ---------------------------------------------------------------------------
# Notification Delivery
# ---------------------------------------------------------------------------

def send_telegram_notification(message: str) -> bool:
    """
    Send a plain text or markdown notification message to the configured admin chat.
    Returns True on success, or False on failure.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_CHAT_ID:
        logger.warning("Telegram credentials (token or admin chat ID) not configured. Skipping notification.")
        return False

    url = f"{BASE_URL}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        
        if res_data.get("ok"):
            logger.info("Telegram notification sent successfully.")
            return True
            
        logger.error(f"Telegram API returned an error: {res_data}")
        return False

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False