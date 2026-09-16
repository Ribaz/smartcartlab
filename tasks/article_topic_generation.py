# tasks/article_topic_generation.py
# Executes queued article topic generation tasks.

from typing import Any

from social.topic_generation import generate_and_save_article_topic


def execute_article_topic_generation(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute article topic generation from a queued task payload."""
    return generate_and_save_article_topic(payload)