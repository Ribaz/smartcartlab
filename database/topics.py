# database/topics.py
# Provides persistence helpers for article topics.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from database.connections import get_social_connection

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _utc_now() -> str:
    return datetime.now(UTC).strftime(DB_DATETIME_FORMAT)


def save_article_topic(
    article_id: str,
    topic: str,
) -> int:
    """Save a topic for an article and return its ID."""
    with get_social_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO article_topics (
                article_id,
                topic,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                article_id,
                topic.strip(),
                _utc_now(),
            ),
        )

        topic_id = cursor.lastrowid

    if topic_id is None:
        raise RuntimeError("Failed to save article topic.")

    return topic_id


def get_article_topics(article_id: str) -> list[str]:
    """Return all topics already created for an article."""
    with get_social_connection() as connection:
        rows = connection.execute(
            """
            SELECT topic
            FROM article_topics
            WHERE article_id = ?
            ORDER BY id
            """,
            (article_id,),
        ).fetchall()

    return [row["topic"] for row in rows]


def get_all_article_topics() -> list[sqlite3.Row]:
    """Return all article topics ordered by ID."""
    with get_social_connection() as connection:
        return connection.execute(
            """
            SELECT id, article_id, topic, created_at
            FROM article_topics
            ORDER BY id
            """
        ).fetchall()


def get_article_topic(topic_id: int) -> sqlite3.Row | None:
    """Return one article topic by ID."""
    with get_social_connection() as connection:
        return connection.execute(
            """
            SELECT id, article_id, topic, created_at
            FROM article_topics
            WHERE id = ?
            """,
            (topic_id,),
        ).fetchone()


def get_article_topics_all() -> list[sqlite3.Row]:
    """Return all article topics ordered by ID."""
    with get_social_connection() as connection:
        return connection.execute(
            """
            SELECT id, article_id, topic, created_at
            FROM article_topics
            ORDER BY id
            """
        ).fetchall()


