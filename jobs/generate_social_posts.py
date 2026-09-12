# jobs/generate_social_posts.py
# Generates social content for newly discovered articles.

import logging

from database.schema_social import initialize_social_db
from social.generation import process_new_articles

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

PLATFORMS = ["mastodon", "facebook"]


def main() -> None:
    logger.info("Starting social generation job.")
    initialize_social_db()

    process_new_articles(PLATFORMS)

    logger.info("Social generation job completed.")


if __name__ == "__main__":
    main()