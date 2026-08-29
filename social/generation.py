import logging

from src.ai.generator import generate_social_posts
from src.integrations.telegram import send_telegram_notification
from utils.db_helpers import (
    get_blog_articles_by_status,
    get_variations_count,
    insert_social_post,
    update_blog_article_status,
)


logger = logging.getLogger(__name__)


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
            logger.info("Article %s marked as GENERATED.", article_id)
            send_telegram_notification(
                "📢 *Nuovi contenuti social disponibili*\n"
                f"Generati *{created_posts} post* per:\n"
                f"*{article['title']}*\n\n"
                "Sono pronti per la revisione nella dashboard."
            )

        except Exception:
            update_blog_article_status(article_id, "FAILED")
            logger.exception("Generation failed for article %s.", article_id)


            