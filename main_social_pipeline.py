# main_social_pipeline.py
# Periodic batch pipeline: RSS ingestion, AI generation, scheduling, publishing, and one-shot notification.

import logging

from database.schema_social import initialize_social_db
from social.generation import process_new_articles
from social.ingestion import process_wordpress_ingestion
from social.publishing import process_publishing
from social.scheduling import process_scheduling

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)



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

    logger.info("=== SOCIAL BATCH PIPELINE COMPLETED ===")


if __name__ == "__main__":
    main()