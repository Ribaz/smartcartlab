# tasks/image_prompt_generation.py
# Executes queued image prompt generation tasks.

from __future__ import annotations

from database.image_prompts import save_image_prompt
from social.image_prompts import generate_image_prompt


def execute_image_prompt_generation(payload: dict) -> dict:
    """Generate and persist one image prompt."""
    prompt = generate_image_prompt(
        article_title=payload["article_title"],
        article_content=payload["article_content"],
        topic=payload["topic"],
        language=payload["language"],
    )

    prompt_id = save_image_prompt(
        article_id=payload["article_id"],
        topic_id=payload["topic_id"],
        prompt=prompt,
    )

    return {
        "article_id": payload["article_id"],
        "topic_id": payload["topic_id"],
        "prompt_id": prompt_id,
    }