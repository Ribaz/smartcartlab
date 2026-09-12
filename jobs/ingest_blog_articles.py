# jobs/ingest_blog_articles.py
# Checks the blog and stores newly discovered articles.

import logging

from database.schema_social import initialize_social_db
from social.ingestion import process_wordpress_ingestion

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting blog ingestion job.")
    initialize_social_db()

    process_wordpress_ingestion()

    logger.info("Blog ingestion job completed.")


if __name__ == "__main__":
    main()