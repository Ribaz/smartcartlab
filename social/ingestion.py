import logging

from src.integrations.wordpress import get_latest_posts
from utils.db_helpers import save_blog_article


logger = logging.getLogger(__name__)


def process_wordpress_ingestion() -> None:
    """Fetch WordPress once and save newly discovered articles."""
    logger.info("Checking WordPress for new articles...")

    articles = get_latest_posts(limit=3, lang="it")

    if not articles:
        logger.info("No articles returned from WordPress.")
        return

    new_articles = 0

    for article in articles:
        if save_blog_article(article):
            new_articles += 1
            logger.info("Saved new article: %s", article["title"])

    logger.info(
        "WordPress ingestion completed: %d new articles.",
        new_articles,
    )