# jobs/schedule_social_posts.py
# Assigns publication slots to approved social posts.

import logging

from database.schema_social import initialize_social_db
from social.scheduling import process_scheduling

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

PLATFORMS = ["mastodon", "facebook"]


def main() -> None:
    logger.info("Starting social scheduling job.")
    initialize_social_db()

    for platform in PLATFORMS:
        process_scheduling(platform=platform)

    logger.info("Social scheduling job completed.")


if __name__ == "__main__":
    main()