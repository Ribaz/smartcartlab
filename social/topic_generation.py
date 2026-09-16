# social/topic_generation.py
# Prepares and processes article topic generation.

from __future__ import annotations

from typing import Any

from database.articles import get_blog_article_by_id
from database.task_queue import enqueue_task
from database.topics import get_article_topics, save_article_topic
from social.topics import generate_article_topic

ARTICLE_TOPIC_TASK_TYPE = "GENERATE_ARTICLE_TOPIC"


def queue_article_topic(article_id: int) -> int:
    """Queue the generation of one new topic for an article."""
    article_row = get_blog_article_by_id(article_id)

    if article_row is None:
        raise ValueError(f"Article {article_id} not found.")

    article = dict(article_row)
    article_content = article.get("content")

    if not article_content or not article_content.strip():
        raise ValueError(
            f"Article {article_id} has no content available for topic generation."
        )

    existing_topics = get_article_topics(article_id)

    return enqueue_task(
        task_type=ARTICLE_TOPIC_TASK_TYPE,
        payload={
            "article_id": article_id,
            "article_title": article["title"],
            "article_content": article_content,
            "existing_topics": existing_topics,
            "language": article.get("lang") or "it",
        },
    )


def generate_and_save_article_topic(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Generate and persist one article topic from a prepared task payload."""
    topic = generate_article_topic(
        article_title=payload["article_title"],
        article_content=payload["article_content"],
        existing_topics=payload["existing_topics"],
        language=payload["language"],
    )

    if topic is None:
        return {
            "article_id": payload["article_id"],
            "topic_id": None,
            "topic": None,
            "exhausted": True,
        }

    topic_id = save_article_topic(
        article_id=payload["article_id"],
        topic=topic,
    )

    return {
        "article_id": payload["article_id"],
        "topic_id": topic_id,
        "topic": topic,
        "exhausted": False,
    }