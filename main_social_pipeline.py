# main_social_pipeline.py
# Periodic batch pipeline: RSS ingestion, AI generation, scheduling, publishing, and one-shot notification.

import os
import logging
import requests
from utils.db_helpers import (
    initialize_social_db,
    save_blog_article,
    get_latest_scheduled_time,
    count_pending_posts,
)
from social.ingestion import process_wordpress_ingestion
from social.generation import process_new_articles
from social.scheduling import process_scheduling
from social.publishing import process_publishing
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID



logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# 4. Telegram One-Shot Notification
# ---------------------------------------------------------------------------

def send_telegram_one_shot_notification(count: int):
    """Send a single Telegram reminder message about pending posts."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not found. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"📢 *SmartCartLab Social*\nThere are *{count} new posts* waiting for your review in the local dashboard!"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info("One-shot Telegram notification sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


def check_and_notify_pending():
    """Check pending posts count and trigger notification if needed."""
    logger.info("Phase 4: Checking pending posts count for Telegram notification...")
    total_pending = count_pending_posts()
    if total_pending > 0:
        logger.info(f"Found {total_pending} pending posts. Sending Telegram reminder...")
        send_telegram_one_shot_notification(total_pending)
    else:
        logger.info("No pending posts found. Skipping Telegram notification.")


# ---------------------------------------------------------------------------
# Main Pipeline Runner
# ---------------------------------------------------------------------------

def main():
    logger.info("=== STARTING SOCIAL BATCH PIPELINE ===")
    initialize_social_db()

    platforms = ["mastodon", "facebook"]

    process_wordpress_ingestion()
    process_new_articles(platforms)

    for platform in platforms:
        process_scheduling(platform=platform)

    process_publishing()
    check_and_notify_pending()

    logger.info("=== SOCIAL BATCH PIPELINE COMPLETED ===")


if __name__ == "__main__":
    main()