# social/image_generation.py
# Queues image generation tasks.

from __future__ import annotations

from database.image_prompts import get_image_prompt_by_topic
from database.task_queue import enqueue_task

IMAGE_TASK_TYPE = "GENERATE_IMAGE"

DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_QUALITY = "standard"


def queue_image(
    topic_id: int,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    quality: str = DEFAULT_QUALITY,
) -> int:
    """Queue image generation for a topic."""
    prompt_row = get_image_prompt_by_topic(topic_id)

    if prompt_row is None:
        raise ValueError(
            f"No image prompt found for topic {topic_id}."
        )

    image_prompt = dict(prompt_row)

    return enqueue_task(
        task_type=IMAGE_TASK_TYPE,
        payload={
            "article_id": image_prompt["article_id"],
            "topic_id": image_prompt["topic_id"],
            "prompt_id": image_prompt["id"],
            "prompt": image_prompt["prompt"],
            "width": width,
            "height": height,
            "quality": quality,
        },
    )