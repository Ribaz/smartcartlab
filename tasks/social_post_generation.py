# tasks/social_post_generation.py
# Executes queued social post generation tasks.

from typing import Any

from database.posts import get_next_variation_number, insert_social_post
from social.copywriter import generate_social_post


def execute_social_post_generation(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Generate and persist one social post from a queued task payload."""
    generated_post = generate_social_post(
        article_title=payload["article_title"],
        article_content=payload["article_content"],
        article_link=payload["article_link"],
        topic=payload["topic"],
        platform=payload["platform"],
        language=payload["language"],
    )

    variation_number = get_next_variation_number(
        payload["article_id"],
        payload["platform"],
    )

    post_id = insert_social_post(
        article_id=payload["article_id"],
        platform=payload["platform"],
        content=generated_post["content"],
        variation_number=variation_number,
        topic_id=payload["topic_id"],
    )

    return {
        "article_id": payload["article_id"],
        "topic_id": payload["topic_id"],
        "post_id": post_id,
        "platform": payload["platform"],
    }