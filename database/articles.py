from __future__ import annotations

import sqlite3
from typing import Dict, List

from database.connections import get_social_connection


VALID_ARTICLE_STATUSES = {"NEW", "GENERATED", "FAILED"}



def save_blog_article(article: Dict) -> bool:
    """Insert a blog article if not present. Return True when newly inserted."""
    with get_social_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM blog_articles WHERE id = ?",
            (article["id"],),
        ).fetchone()
        if existing:
            return False

        conn.execute(
            """
            INSERT INTO blog_articles (
                id,
                slug,
                title,
                content,
                link,
                pub_date,
                media_url,
                lang
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article["id"],
                article.get("slug", ""),
                article["title"],
                article["content"],
                article["link"],
                article.get("date_gmt", ""),
                article.get("media_url"),
                article.get("lang", "it"),
            ),
        )
    return True


def get_blog_articles_by_status(status: str) -> List[sqlite3.Row]:
    """Return blog articles having the requested processing status."""
    if status not in VALID_ARTICLE_STATUSES:
        allowed = ", ".join(sorted(VALID_ARTICLE_STATUSES))
        raise ValueError(
            f"Unsupported article status '{status}'. Allowed: {allowed}"
        )

    with get_social_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM blog_articles
            WHERE processing_status = ?
            ORDER BY pub_date ASC, created_at ASC
            """,
            (status,),
        ).fetchall()


def update_blog_article_status(article_id: str, status: str) -> None:
    """Update the processing status of a blog article."""
    if status not in VALID_ARTICLE_STATUSES:
        allowed = ", ".join(sorted(VALID_ARTICLE_STATUSES))
        raise ValueError(
            f"Unsupported article status '{status}'. Allowed: {allowed}"
        )

    with get_social_connection() as conn:
        conn.execute(
            """
            UPDATE blog_articles
            SET processing_status = ?
            WHERE id = ?
            """,
            (status, article_id),
        )