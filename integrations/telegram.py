# integrations/telegram.py
# Shared Telegram delivery integration.

from __future__ import annotations

import logging

import requests

from config.settings import TELEGRAM_BOT_TOKEN


logger = logging.getLogger(__name__)

TELEGRAM_API_BASE_URL = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else ""
)


def send_telegram_message(
    message: str,
    chat_id: str | int,
    *,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: int = 15,
) -> bool:
    """Send a message to a Telegram chat or channel."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning(
            "Telegram bot token not configured. Skipping message delivery."
        )
        return False

    if not chat_id:
        logger.warning(
            "Telegram destination not configured. Skipping message delivery."
        )
        return False

    payload: dict[str, object] = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": disable_web_page_preview,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(
            f"{TELEGRAM_API_BASE_URL}/sendMessage",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        response_data = response.json()
        if response_data.get("ok"):
            logger.info("Telegram message sent successfully.")
            return True

        logger.error(
            "Telegram API returned an error: %s",
            response_data,
        )
        return False

    except requests.RequestException:
        logger.exception("Unable to send Telegram message.")
        return False
