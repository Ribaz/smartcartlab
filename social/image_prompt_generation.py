# social/image_prompt_generation.py
# Queues image prompt generation tasks.

from __future__ import annotations

from database.articles import get_blog_article_by_id
from database.task_queue import enqueue_task
from database.topics import get_article_topic

IMAGE_PROMPT_TASK_TYPE = "GENERATE_IMAGE_PROMPT"


def queue_image_prompt(topic_id: int) -> int:
    """Queue image prompt generation for an article topic."""
    topic_row = get_article_topic(topic_id)

    if topic_row is None:
        raise ValueError(f"Topic {topic_id} does not exist.")

    topic = dict(topic_row)

    article_row = get_blog_article_by_id(topic["article_id"])

    if article_row is None:
        raise ValueError(f"Article {topic['article_id']} does not exist.")

    article = dict(article_row)
    article_content = article.get("content")

    if not article_content or not article_content.strip():
        raise ValueError(
            f"Article {article['id']} has no content available "
            "for image prompt generation."
        )

    return enqueue_task(
        task_type=IMAGE_PROMPT_TASK_TYPE,
        payload={
            "article_id": article["id"],
            "topic_id": topic["id"],
            "article_title": article["title"],
            "article_content": article_content,
            "topic": topic["topic"],
            "language": article.get("lang") or "it",
        },
    )