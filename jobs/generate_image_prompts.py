# jobs/generate_image_prompts.py
# Queues missing image prompt generation tasks.

import logging

from database.image_prompts import image_prompt_exists
from database.schema_social import initialize_social_db
from database.schema_tasks import initialize_task_db
from database.task_queue import has_active_task
from database.topics import get_all_article_topics
from social.image_prompt_generation import (
    IMAGE_PROMPT_TASK_TYPE,
    queue_image_prompt,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting image prompt generation job.")

    initialize_social_db()
    initialize_task_db()

    queued_tasks = 0

    for topic_row in get_all_article_topics():
        topic = dict(topic_row)
        topic_id = topic["id"]

        if image_prompt_exists(topic_id):
            continue

        if has_active_task(
            IMAGE_PROMPT_TASK_TYPE,
            payload_values={
                "topic_id": topic_id,
            },
        ):
            continue

        task_id = queue_image_prompt(topic_id)
        queued_tasks += 1

        logger.info(
            "Queued image prompt task #%s for topic %s.",
            task_id,
            topic_id,
        )

    logger.info(
        "Image prompt generation job completed: %d tasks queued.",
        queued_tasks,
    )


if __name__ == "__main__":
    main()