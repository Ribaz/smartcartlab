# main_social_pipeline.py
# Periodic batch pipeline: RSS ingestion, AI generation, scheduling, publishing, and one-shot notification.

import logging
from utils.db_helpers import (
    initialize_social_db,
    count_pending_posts,
)
from social.ingestion import process_wordpress_ingestion
from social.generation import process_new_articles
from social.scheduling import process_scheduling
from social.publishing import process_publishing
from src.integrations.telegram import send_telegram_notification


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Telegram One-Shot Notification
# ---------------------------------------------------------------------------

def check_and_notify_pending() -> None:
    """Notify the admin when posts are waiting for review."""
    logger.info("Checking pending posts for notification...")

    total_pending = count_pending_posts()

    if total_pending <= 0:
        logger.info("No pending posts found. Skipping notification.")
        return

    message = (
        "📢 *SmartCartLab Social*\n"
        f"Ci sono *{total_pending} post* in attesa di approvazione "
        "nella dashboard."
    )

    send_telegram_notification(message)


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