# jobs/publish_social_posts.py
# Publishes social posts whose scheduled time has arrived.

import logging

from database.schema_social import initialize_social_db
from social.publishing import process_publishing

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting social publishing job.")
    initialize_social_db()

    process_publishing()

    logger.info("Social publishing job completed.")


if __name__ == "__main__":
    main()