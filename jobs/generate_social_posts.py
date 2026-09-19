# jobs/generate_social_posts.py
# Queues missing social post generation tasks.

import logging

from database.posts import social_post_exists
from database.schema_social import initialize_social_db
from database.schema_tasks import initialize_task_db
from database.task_queue import has_active_task
from database.topics import get_all_article_topics
from social.post_generation import SOCIAL_POST_TASK_TYPE, queue_social_post

PLATFORMS = ("facebook", "mastodon")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting social post generation job.")

    initialize_social_db()
    initialize_task_db()

    queued_tasks = 0

    for topic_row in get_all_article_topics():
        topic = dict(topic_row)
        topic_id = topic["id"]

        for platform in PLATFORMS:
            if social_post_exists(topic_id, platform):
                continue

            if has_active_task(
                SOCIAL_POST_TASK_TYPE,
                payload_values={
                    "topic_id": topic_id,
                    "platform": platform,
                },
            ):
                continue

            task_id = queue_social_post(topic_id, platform)
            queued_tasks += 1

            logger.info(
                "Queued social post task #%s for topic %s on %s.",
                task_id,
                topic_id,
                platform,
            )

    logger.info(
        "Social post generation job completed: %d tasks queued.",
        queued_tasks,
    )


if __name__ == "__main__":
    main()