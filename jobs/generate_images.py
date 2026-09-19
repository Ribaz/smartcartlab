# jobs/generate_images.py
# Queues missing image generation tasks.

import logging

from database.image_prompts import get_all_image_prompts
from database.images import generated_image_exists
from database.schema_social import initialize_social_db
from database.schema_tasks import initialize_task_db
from database.task_queue import has_active_task, has_active_task_type
from social.image_generation import IMAGE_TASK_TYPE, queue_image

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting image generation job.")

    initialize_social_db()
    initialize_task_db()

    if has_active_task_type(IMAGE_TASK_TYPE):
        logger.info(
            "Image generation task already active; nothing queued."
        )
        return

    for prompt_row in get_all_image_prompts():
        image_prompt = dict(prompt_row)
        prompt_id = image_prompt["id"]
        topic_id = image_prompt["topic_id"]

        if generated_image_exists(prompt_id):
            continue

        if has_active_task(
            IMAGE_TASK_TYPE,
            payload_values={"prompt_id": prompt_id},
        ):
            continue

        task_id = queue_image(topic_id)

        logger.info(
            "Queued image generation task #%s for prompt %s.",
            task_id,
            prompt_id,
        )

        # Image generation is expensive: enqueue at most one per run.
        break

    logger.info("Image generation job completed.")


if __name__ == "__main__":
    main()