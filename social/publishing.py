import logging

from integrations.facebook import post_to_facebook
from integrations.mastodon import post_to_mastodon
from integrations.telegram import send_telegram_notification
from database.db_helpers import (
    get_due_scheduled_posts,
    mark_post_as_published,
)


logger = logging.getLogger(__name__)


def process_publishing() -> None:
    """
    Publish due scheduled posts and mark successful publications as PUBLISHED.
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

        logger.info(
            "Publishing post #%s to platform '%s'...",
            post_id,
            platform,
        )

        success = False

        if platform == "mastodon":
            success = post_to_mastodon(status_text=content)
        elif platform == "facebook":
            success = post_to_facebook(text=content)
        else:
            logger.warning(
                "Platform '%s' is not supported for post #%s.",
                platform,
                post_id,
            )
            continue

        if success:
            mark_post_as_published(post_id)
            
            logger.info(
                "Post #%s published successfully on %s.",
                post_id,
                platform,
            )

            send_telegram_notification(
                "✅ *Post pubblicato*\n"
                f"Piattaforma: *{platform}*\n\n"
                f"{content}"
            )
        else:
            logger.error(
                "Failed to publish post #%s on %s.",
                post_id,
                platform,
            )