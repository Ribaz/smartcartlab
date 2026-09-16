# social/post_generation.py
# Prepares social post generation tasks.

from database.articles import get_blog_article_by_id
from database.task_queue import enqueue_task
from database.topics import get_article_topic

SOCIAL_POST_TASK_TYPE = "GENERATE_SOCIAL_POST"


def queue_social_post(topic_id: int, platform: str) -> int:
    """Queue one platform-specific social post for an article topic."""
    topic_row = get_article_topic(topic_id)

    if topic_row is None:
        raise ValueError(f"Topic {topic_id} not found.")

    topic = dict(topic_row)
    article_row = get_blog_article_by_id(topic["article_id"])

    if article_row is None:
        raise ValueError(f"Article {topic['article_id']} not found.")

    article = dict(article_row)
    article_content = article.get("content")

    if not article_content or not article_content.strip():
        raise ValueError(
            f"Article {article['id']} has no content available for post generation."
        )

    return enqueue_task(
        task_type=SOCIAL_POST_TASK_TYPE,
        payload={
            "article_id": article["id"],
            "topic_id": topic["id"],
            "article_title": article["title"],
            "article_content": article_content,
            "article_link": article["link"],
            "topic": topic["topic"],
            "platform": platform.lower(),
            "language": article.get("lang") or "it",
        },
    )