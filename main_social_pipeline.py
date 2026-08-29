# main_social_pipeline.py
# Periodic batch pipeline: RSS ingestion, AI generation, scheduling, publishing, and one-shot notification.

import os
import logging
import requests
from datetime import datetime, timedelta
from utils.db_helpers import (
    initialize_social_db,
    save_blog_article,
    get_variations_count,
    insert_social_post,
    get_next_approved_post,
    set_post_scheduled,
    get_due_scheduled_posts,
    mark_post_as_published,
    get_latest_scheduled_time,
    count_pending_posts,
    get_blog_articles_by_status,
    update_blog_article_status,
    is_scheduling_slot_taken
)
from src.integrations.wordpress import get_latest_posts
from src.integrations.mastodon import post_to_mastodon
from src.integrations.facebook import post_to_facebook
from src.ai.generator import generate_social_posts
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
# 1. Ingestion & Multi-Angle Post Generation
# ---------------------------------------------------------------------------

def process_wordpress_ingestion():
    """Fetch WordPress once and save newly discovered articles."""
    logger.info("Phase 1: Checking WordPress for new articles...")

    articles = get_latest_posts(limit=3, lang="it")

    if not articles:
        logger.info("No articles returned from WordPress.")
        return

    new_articles = 0

    for article in articles:
        if save_blog_article(article):
            new_articles += 1
            logger.info("Saved new article: %s", article["title"])

    logger.info("WordPress ingestion completed: %d new articles.", new_articles)


def process_new_articles(platforms: list[str]):
    """Generate all platform variations for articles marked as NEW."""
    articles = get_blog_articles_by_status("NEW")

    if not articles:
        logger.info("No NEW articles waiting for content generation.")
        return

    for article_row in articles:
        article = dict(article_row)
        article_id = article["id"]

        logger.info("Processing NEW article: %s", article["title"])

        try:
            for platform in platforms:
                existing_count = get_variations_count(article_id, platform)

                if existing_count == 3:
                    logger.info(
                        "[%s] Article already has 3 variations.",
                        platform,
                    )
                    continue

                if existing_count != 0:
                    raise RuntimeError(
                        f"Article {article_id} has {existing_count} "
                        f"variations for {platform}; expected 0 or 3."
                    )

                generated_posts = generate_social_posts(
                    article_title=article["title"],
                    article_content=article["content"],
                    article_link=article["link"],
                    platform=platform,
                    language=article.get("lang") or "it",
                )

                for post_data in generated_posts:
                    insert_social_post(
                        article_id=article_id,
                        platform=platform,
                        content=post_data["content"],
                        variation_number=post_data["variation_number"],
                        media_url=article.get("media_url"),
                    )

            update_blog_article_status(article_id, "GENERATED")
            logger.info("Article %s marked as GENERATED.", article_id)

        except Exception:
            update_blog_article_status(article_id, "FAILED")
            logger.exception("Generation failed for article %s.", article_id)
            

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

    now = datetime.now()
    
    # Check if there are already scheduled posts for this platform
    latest_slot_str = get_latest_scheduled_time(platform)
    
    if latest_slot_str:
        try:
            latest_slot = datetime.strptime(latest_slot_str, "%Y-%m-%d %H:%M:%S")
            base_time = max(latest_slot, now)
            target_slot = base_time + timedelta(days=1)
        except ValueError:
            target_slot = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    else:
        target_slot = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)

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
# 3. Publishing Engine
# ---------------------------------------------------------------------------

def process_publishing():
    """
    Check for posts with APPROVED status whose scheduled_at <= NOW.
    Publish payload to destination platforms and update state to PUBLISHED.
    """
    logger.info("Phase 3: Checking due scheduled posts for immediate publishing...")
    due_posts = get_due_scheduled_posts()

    if not due_posts:
        logger.info("No posts due for publication at this time.")
        return

    for post in due_posts:
        post_id = post["id"]
        platform = post["platform"]
        content = post["content"]

        logger.info(f"Dispatching publication for Post #{post_id} to platform '{platform}'...")

        success = False
        if platform == "mastodon":
            success = post_to_mastodon(status_text=content)
        elif platform == "facebook":
            success = post_to_facebook(text=content)
        else:
            logger.warning(f"Platform '{platform}' publishing adapter not implemented.")
            continue

        if success:
            mark_post_as_published(post_id)
            logger.info(f"Post #{post_id} published and marked as PUBLISHED successfully on {platform}.")
        else:
            logger.error(f"Failed to publish Post #{post_id} on {platform}.")


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