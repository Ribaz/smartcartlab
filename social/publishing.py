# social/publishing.py
# Publishes due scheduled posts, with their linked image, to the social platforms.

import logging
from collections.abc import Mapping
from typing import Any

from config.settings import TELEGRAM_ADMIN_CHAT_ID
from database.posts import (
    get_due_scheduled_posts,
    mark_post_as_published,
)
from integrations.facebook import post_to_facebook
from integrations.mastodon import post_to_mastodon, upload_media
from integrations.telegram import send_telegram_message
from social.post_images import resolve_generated_image_path

logger = logging.getLogger(__name__)


def publish_post(post: Mapping[str, Any]) -> bool:
    """Publish one post, attaching its image if it has one. Return True on success."""
    post_id = post["id"]
    platform = post["platform"]
    content = post["content"]
    image_id = post["image_id"]

    image_path = None
    if image_id:
        image_path = resolve_generated_image_path(image_id)
        # Publishing without the chosen image would silently change the post, so retry later.
        if image_path is None:
            logger.error("Image #%s of post #%s is not available.", image_id, post_id)
            return False

    if platform == "mastodon":
        media_ids = None
        if image_path:
            media_id = upload_media(str(image_path))
            if not media_id:
                return False
            media_ids = [media_id]
        return post_to_mastodon(status_text=content, media_ids=media_ids) is not None

    if platform == "facebook":
        return post_to_facebook(
            text=content,
            image_path=str(image_path) if image_path else None,
        )

    logger.warning("Platform '%s' is not supported for post #%s.", platform, post_id)
    return False


def process_publishing() -> None:
    """
    Publish due scheduled posts and mark successful publications as PUBLISHED.
    Failed posts stay APPROVED, so the next run tries them again.
    """
    logger.info("Checking due scheduled posts for publication...")

    due_posts = get_due_scheduled_posts()

    if not due_posts:
        logger.info("No posts due for publication.")
        return

    for post in due_posts:
        post_id = post["id"]
        platform = post["platform"]
        content = post["content"]

        try:
            logger.info(
                "Publishing post #%s to platform '%s'...",
                post_id,
                platform,
            )

            if not publish_post(post):
                logger.error(
                    "Failed to publish post #%s on %s.",
                    post_id,
                    platform,
                )
                continue

            mark_post_as_published(post_id)

            logger.info(
                "Post #%s published successfully on %s.",
                post_id,
                platform,
            )

            send_telegram_message(
                "✅ *Post pubblicato*\n"
                f"Piattaforma: *{platform}*\n\n"
                f"{content}",
                TELEGRAM_ADMIN_CHAT_ID,
                "Markdown",
            )

        except Exception:
            logger.exception(
                "Unexpected error while publishing post #%s on %s.",
                post_id,
                platform,
            )