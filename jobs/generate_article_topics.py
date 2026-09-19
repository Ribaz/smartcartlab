# jobs/generate_article_topics.py
# Queues missing article topic generation tasks.

import logging

from database.articles import get_blog_articles
from database.schema_social import initialize_social_db
from database.schema_tasks import initialize_task_db
from database.task_queue import has_active_task
from database.topics import get_article_topics
from social.topic_generation import ARTICLE_TOPIC_TASK_TYPE, queue_article_topic

TARGET_TOPICS_PER_ARTICLE = 3

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting article topic generation job.")

    initialize_social_db()
    initialize_task_db()

    queued_tasks = 0

    for article_row in get_blog_articles():
        article = dict(article_row)
        article_id = article["id"]

        article_content = article.get("content")

        if not article_content or not article_content.strip():
            logger.warning(
                "Skipping article %s because it has no content.",
                article_id,
            )
            continue


        topics = get_article_topics(article_id)

        if len(topics) >= TARGET_TOPICS_PER_ARTICLE:
            continue

        if has_active_task(
            ARTICLE_TOPIC_TASK_TYPE,
            payload_key="article_id",
            payload_value=article_id,
        ):
            continue

        task_id = queue_article_topic(article_id)
        queued_tasks += 1

        logger.info(
            "Queued topic task #%s for article %s (%d/%d topics).",
            task_id,
            article_id,
            len(topics),
            TARGET_TOPICS_PER_ARTICLE,
        )

    logger.info(
        "Article topic generation job completed: %d tasks queued.",
        queued_tasks,
    )


if __name__ == "__main__":
    main()