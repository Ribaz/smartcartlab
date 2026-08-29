# main_social_pipeline.py
# Periodic batch pipeline: RSS ingestion, AI generation, scheduling, publishing, and one-shot notification.

import os
import logging
import requests
from datetime import datetime, timedelta
from utils.db_helpers import (
    initialize_social_db,
    save_blog_article,
    get_next_approved_post,
    set_post_scheduled,
    get_latest_scheduled_time,
    count_pending_posts,
    is_scheduling_slot_taken
)
from social.ingestion import process_wordpress_ingestion
from social.generation import process_new_articles
from social.publishing import process_publishing
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID


WEEKLY_SLOTS = {
    0: ["08:45", "12:45", "18:15"],  # monday
    1: ["08:45", "12:45", "18:15"],  # tuesday
    2: ["08:45", "12:45", "18:15"],  # wednesday
    3: ["08:45", "12:45", "18:15"],  # thursday
    4: ["08:45", "12:45"],           # friday
}


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# 2. Scheduling Logic (Next Slot Assignment)
# ---------------------------------------------------------------------------

def process_scheduling(platform: str = "mastodon"):
    """
    Select the oldest APPROVED post and assign a publication timestamp.
    Calculates the next available slot based on the last scheduled post for this platform.
    """
    logger.info(f"Phase 2 [{platform}]: Assigning publication slots to approved posts...")
    approved_post = get_next_approved_post(platform=platform)

    if not approved_post:
        logger.info(f"No APPROVED posts waiting for scheduling on platform: {platform}.")
        return

    target_slot = get_next_available_slot(
        platform=platform,
        after=datetime.now(),
    )

    slot_str = target_slot.strftime("%Y-%m-%d %H:%M:%S")

    set_post_scheduled(approved_post["id"], slot_str)
    logger.info(f"[{platform}] Post #{approved_post['id']} successfully scheduled for {slot_str}.")


def get_next_candidate_slot(after: datetime) -> datetime:
    """Return the first configured publication slot after the supplied datetime."""
    current_day = after.date()

    while True:
        weekday = current_day.weekday()
        day_slots = WEEKLY_SLOTS.get(weekday, [])

        for slot_time in day_slots:
            hour, minute = map(int, slot_time.split(":"))

            candidate = datetime.combine(
                current_day,
                datetime.min.time(),
            ).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            if candidate > after:
                return candidate

        current_day += timedelta(days=1)


def get_next_available_slot(
    platform: str,
    after: datetime,
) -> datetime:
    """Return the first configured slot not already used by the platform."""
    candidate = get_next_candidate_slot(after)

    while True:
        candidate_str = candidate.strftime("%Y-%m-%d %H:%M:%S")

        if not is_scheduling_slot_taken(platform, candidate_str):
            return candidate

        candidate = get_next_candidate_slot(candidate)


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