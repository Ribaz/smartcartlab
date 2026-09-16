# jobs/process_task_queue.py
# Processes one queued background task at a time.

import logging
from typing import Any

from database.schema_tasks import initialize_task_db
from database.task_queue import (
    claim_next_task,
    mark_task_completed,
    mark_task_failed,
)
from tasks.social_text_generation import execute_social_text_generation
from tasks.article_topic_generation import execute_article_topic_generation
from tasks.social_post_generation import execute_social_post_generation


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)




def _execute_task(task: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a queued task to the appropriate handler."""
    task_type = task["task_type"]
    payload = task["payload"]

    if task_type == "GENERATE_ARTICLE_TOPIC":
        return execute_article_topic_generation(payload)

    if task_type == "GENERATE_SOCIAL_TEXT":
        return execute_social_text_generation(payload)
    
    if task_type == "GENERATE_SOCIAL_POST":
        return execute_social_post_generation(payload)

    raise ValueError(f"Unsupported task type: {task_type}")


def main() -> None:
    logger.info("Starting task queue worker.")

    initialize_task_db()

    task = claim_next_task()

    if task is None:
        logger.info("No queued tasks available.")
        return

    task_id = task["id"]
    task_type = task["task_type"]

    logger.info(
        "Processing task #%s of type '%s'.",
        task_id,
        task_type,
    )

    try:
        result = _execute_task(task)

    except Exception as exc:
        mark_task_failed(
            task_id,
            str(exc),
        )

        logger.exception(
            "Task #%s failed.",
            task_id,
        )
        return

    mark_task_completed(
        task_id,
        result,
    )

    logger.info(
        "Task #%s completed successfully.",
        task_id,
    )


if __name__ == "__main__":
    main()