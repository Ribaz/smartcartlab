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
)
from src.integrations.wordpress import get_latest_posts
from src.integrations.mastodon import post_to_mastodon
from src.integrations.facebook import post_to_facebook
from src.ai.generator import generate_social_posts
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Ingestion & Multi-Angle Post Generation
# ---------------------------------------------------------------------------

def process_blog_ingestion(platform: str = "mastodon"):
    """
    Fetch the latest articles from WordPress RSS feed.
    If an article is newly registered or has < 3 posts generated,
    produce distinct variations using Gemma and store them as PENDING drafts.
    """
    logger.info(f"Phase 1 [{platform}]: Checking WordPress RSS feed for new articles...")
    articles = get_latest_posts(limit=3, lang="it")
    if not articles:
        logger.info("No articles returned from RSS feed.")
        return

    for article in articles:
        article_id = article["id"]
        is_new = save_blog_article(article)
        existing_count = get_variations_count(article_id, platform)
        
        if existing_count == 3:
            logger.info(
                "[%s] Article '%s' already processed.",
                platform,
                article["title"],
            )
            continue

        if existing_count != 0:
            logger.warning(
                "[%s] Article '%s' has %d generated posts. "
                "Expected exactly 3. Skipping automatic generation.",
                platform,
                article["title"],
                existing_count,
            )
            continue

        logger.info(f"[{platform}] Generating 3 social post variations for article: {article['title']}")
        generated_posts = generate_social_posts(
            article_title=article["title"],
            article_content=article["content"],
            article_link=article["link"],
            platform=platform,
            language=article.get("lang", "it"),
        )

        for post_data in generated_posts:
            var_num = post_data["variation_number"]
            content = post_data["content"]
            media_url = article.get("media_url")

            # Store draft post with PENDING status for local dashboard review
            insert_social_post(
                article_id=article_id,
                platform=platform,
                content=content,
                variation_number=var_num,
                media_url=media_url
            )
            logger.info(f"[{platform}] Created PENDING post variation #{var_num} for article ID {article_id}.")


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

    for platform in platforms:
        # 1. Fetch RSS feed and generate variations with Gemma for each platform
        process_blog_ingestion(platform=platform)

        # 2. Schedule user-approved posts into future slots for each platform
        process_scheduling(platform=platform)

    # 3. Dispatch posts whose scheduled time has arrived across all platforms
    process_publishing()

    # 4. Send one-shot Telegram notification if pending posts are waiting
    check_and_notify_pending()

    logger.info("=== SOCIAL BATCH PIPELINE COMPLETED ===")


if __name__ == "__main__":
    main()