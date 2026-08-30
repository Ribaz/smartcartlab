from __future__ import annotations

from database.connections import get_social_connection

# ---------------------------------------------------------------------------
# Social Manager DB - Setup
# ---------------------------------------------------------------------------


def initialize_social_db():
    """Create social manager tables and useful indexes if they do not exist."""
    with get_social_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blog_articles (
                id                TEXT PRIMARY KEY,
                slug              TEXT,
                title             TEXT NOT NULL,
                content           TEXT NOT NULL,
                link              TEXT NOT NULL,
                pub_date          TEXT,
                media_url         TEXT,
                lang              TEXT NOT NULL DEFAULT 'it',
                processing_status TEXT NOT NULL DEFAULT 'NEW',
                created_at        TEXT DEFAULT (datetime('now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS social_posts (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id           TEXT NOT NULL,
                platform             TEXT NOT NULL,
                variation_number     INTEGER DEFAULT 1,
                content              TEXT NOT NULL,
                media_url            TEXT,
                status               TEXT NOT NULL DEFAULT 'PENDING',
                telegram_message_id  INTEGER,
                scheduled_at         TEXT,
                published_at         TEXT,
                created_at           TEXT DEFAULT (datetime('now')),
                updated_at           TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (article_id) REFERENCES blog_articles (id)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_social_posts_status_schedule
            ON social_posts (status, scheduled_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_social_posts_article_platform
            ON social_posts (article_id, platform)
            """
        )


