# social/generation.py
# Queues and processes social content generation for blog articles.

import logging
from typing import Any

from config.settings import TELEGRAM_ADMIN_CHAT_ID
from database.articles import (
    get_blog_article_by_id,
    get_blog_articles_by_status,
    update_blog_article_status,
)
from database.posts import get_variations_count, insert_social_post
from database.task_queue import enqueue_task
from integrations.telegram import send_telegram_message
from social.copywriter import generate_social_posts

logger = logging.getLogger(__name__)

SOCIAL_TEXT_TASK_TYPE = "GENERATE_SOCIAL_TEXT"


def queue_new_articles(platforms: list[str]) -> None:
    """Queue social text generation for articles marked as NEW."""
    articles = get_blog_articles_by_status("NEW")

    if not articles:
        logger.info("No NEW articles waiting for content generation.")
        return

    for article_row in articles:
        article = dict(article_row)
        article_id = article["id"]

        task_id = enqueue_task(
            task_type=SOCIAL_TEXT_TASK_TYPE,
            payload={
                "article_id": article_id,
                "platforms": platforms,
            },
        )

        update_blog_article_status(article_id, "QUEUED")

        logger.info(
            "Queued social generation task #%s for article %s.",
            task_id,
            article_id,
        )


def generate_article_social_posts(
    article_id: int,
    platforms: list[str],
) -> dict[str, Any]:
    """Generate and store social post variations for one article."""
    article_row = get_blog_article_by_id(article_id)

    if article_row is None:
        raise ValueError(f"Article {article_id} not found.")

    article = dict(article_row)

    if article["processing_status"] == "GENERATED":
        logger.info(
            "Article %s is already GENERATED. Skipping generation.",
            article_id,
        )
        return {
            "article_id": article_id,
            "created_posts": 0,
            "skipped": True,
        }

    logger.info("Generating social content for article: %s", article["title"])

    try:
        created_posts = 0

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

            if len(generated_posts) != 3:
                raise RuntimeError(
                    f"Expected 3 generated posts for {platform}, "
                    f"received {len(generated_posts)}."
                )

            for post_data in generated_posts:
                insert_social_post(
                    article_id=article_id,
                    platform=platform,
                    content=post_data["content"],
                    variation_number=post_data["variation_number"],
                    media_url=article.get("media_url"),
                )
                created_posts += 1

        update_blog_article_status(article_id, "GENERATED")

        logger.info(
            "Article %s marked as GENERATED.",
            article_id,
        )

    except Exception:
        update_blog_article_status(article_id, "FAILED")
        raise

    try:
        notification_sent = send_telegram_message(
            "📢 *Nuovi contenuti social disponibili*\n"
            f"Generati *{created_posts} post* per:\n"
            f"*{article['title']}*\n\n"
            "Sono pronti per la revisione nella dashboard.",
            TELEGRAM_ADMIN_CHAT_ID,
            parse_mode="Markdown",
        )

        if not notification_sent:
            logger.warning(
                "Generation notification failed for article %s.",
                article_id,
            )

    except Exception:
        logger.exception(
            "Generation notification failed for article %s.",
            article_id,
        )

    return {
        "article_id": article_id,
        "created_posts": created_posts,
        "platforms": platforms,
        "skipped": False,
    }