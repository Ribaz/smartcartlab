# tasks/image_generation.py
# Executes queued image generation tasks.

from __future__ import annotations

from database.images import save_generated_image
from integrations.local_image_generator import generate_image


def execute_image_generation(payload: dict) -> dict:
    """Generate and persist one image."""
    generated = generate_image(
        prompt=payload["prompt"],
        width=payload["width"],
        height=payload["height"],
        quality=payload["quality"],
    )

    image_id = save_generated_image(
        article_id=payload["article_id"],
        topic_id=payload["topic_id"],
        prompt_id=payload["prompt_id"],
        provider=generated["provider"],
        model=generated["model"],
        width=generated["width"],
        height=generated["height"],
        file_path=generated["file_path"],
    )

    return {
        "article_id": payload["article_id"],
        "topic_id": payload["topic_id"],
        "prompt_id": payload["prompt_id"],
        "image_id": image_id,
        "file_path": generated["file_path"],
    }