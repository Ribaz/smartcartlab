# tasks/social_text_generation.py
# Executes queued social text generation tasks.

from typing import Any

from social.generation import generate_article_social_posts


def execute_social_text_generation(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute social text generation from a queued task payload."""
    article_id = payload["article_id"]
    platforms = payload["platforms"]

    return generate_article_social_posts(
        article_id=article_id,
        platforms=platforms,
    )