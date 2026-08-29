# utils/db_helpers.py
# Shared database utilities.
# All database access goes through these functions.

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import DB_PATH, SOCIAL_DB_PATH

VALID_SOCIAL_STATUSES = {"PENDING", "APPROVED", "PUBLISHED", "REJECTED"}
VALID_ARTICLE_STATUSES = {"NEW", "GENERATED", "FAILED"}


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _open_connection(path: str) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_connection() -> sqlite3.Connection:
    """Open and return a connection to the primary SQLite database."""
    return _open_connection(DB_PATH)


def get_social_connection() -> sqlite3.Connection:
    """Open and return a connection to the Social Manager SQLite database."""
    return _open_connection(SOCIAL_DB_PATH)


def _validate_social_status(status: str) -> None:
    if status not in VALID_SOCIAL_STATUSES:
        allowed = ", ".join(sorted(VALID_SOCIAL_STATUSES))
        raise ValueError(f"Unsupported social post status '{status}'. Allowed: {allowed}")


# ---------------------------------------------------------------------------
# SmartCartLab Core DB
# ---------------------------------------------------------------------------


def initialize_db():
    """Create primary tables if they do not exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                asin           TEXT NOT NULL,
                title          TEXT,
                category       TEXT,
                current_price  REAL,
                avg_price_90d  REAL,
                avg_price_1y   REAL,
                review_score   REAL,
                review_count   INTEGER,
                final_score    REAL,
                analyzed_at    TEXT
            )
            """
        )


def save_products(products: List[Dict]):
    """Insert scored products into the products table."""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO products
                (asin, title, category, current_price, avg_price_90d,
                 avg_price_1y, review_score, review_count, final_score, analyzed_at)
            VALUES
                (:asin, :title, :category, :current_price, :avg_price_90d,
                 :avg_price_1y, :review_score, :review_count, :final_score, datetime('now'))
            """,
            products,
        )


# ---------------------------------------------------------------------------
# Social Manager DB - Setup & ingestion
# ---------------------------------------------------------------------------


def initialize_social_db():
    """Create social manager tables and useful indexes if they do not exist."""
    with get_social_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blog_articles (
                id         TEXT PRIMARY KEY,
                slug       TEXT,
                title      TEXT NOT NULL,
                link       TEXT NOT NULL,
                pub_date   TEXT,
                media_url  TEXT,
                processing_status TEXT NOT NULL DEFAULT 'NEW',
                created_at TEXT DEFAULT (datetime('now'))
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
            INSERT INTO blog_articles (id, slug, title, link, pub_date, media_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                article["id"],
                article.get("slug", ""),
                article["title"],
                article["link"],
                article.get("date_gmt", ""),
                article.get("media_url"),
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
        

def get_variations_count(article_id: str, platform: str) -> int:
    """Count variations that already exist for an article/platform pair."""
    with get_social_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM social_posts
            WHERE article_id = ? AND platform = ?
            """,
            (article_id, platform),
        ).fetchone()
    return int(row["total"] if row else 0)


# ---------------------------------------------------------------------------
# Social Manager DB - Posts CRUD & lifecycle
# ---------------------------------------------------------------------------


def insert_social_post(
    article_id: str,
    platform: str,
    content: str,
    variation_number: int = 1,
    media_url: Optional[str] = None,
    scheduled_at: Optional[str] = None,
) -> int:
    """Insert a PENDING social post and return its generated ID."""
    with get_social_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO social_posts
                (article_id, platform, variation_number, content, media_url, status, scheduled_at)
            VALUES
                (?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (article_id, platform, variation_number, content, media_url, scheduled_at),
        )
        return int(cursor.lastrowid)


def update_social_post_status(
    post_id: int,
    status: str,
    content: Optional[str] = None,
    *,
    clear_schedule: bool = False,
):
    """
    Update lifecycle state and optionally content.

    `clear_schedule` is explicit so that returning a post to PENDING never leaves
    an obsolete publication date attached to it.
    """
    _validate_social_status(status)

    assignments = ["status = ?", "updated_at = datetime('now')"]
    values: list[object] = [status]

    if content is not None:
        assignments.append("content = ?")
        values.append(content)

    if clear_schedule:
        assignments.append("scheduled_at = NULL")

    # A non-published state must not retain an accidental publication timestamp.
    if status != "PUBLISHED":
        assignments.append("published_at = NULL")

    values.append(post_id)

    with get_social_connection() as conn:
        conn.execute(
            f"UPDATE social_posts SET {', '.join(assignments)} WHERE id = ?",
            values,
        )


def update_post_status(post_id: int, status: str):
    """Backward-compatible alias used by older code paths."""
    update_social_post_status(post_id, status)


def update_post_telegram_id(post_id: int, message_id: int):
    """Associate a Telegram message ID with a social post."""
    with get_social_connection() as conn:
        conn.execute(
            """
            UPDATE social_posts
            SET telegram_message_id = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (message_id, post_id),
        )


def get_social_post_by_id(post_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single social post by primary ID."""
    with get_social_connection() as conn:
        return conn.execute(
            "SELECT * FROM social_posts WHERE id = ?",
            (post_id,),
        ).fetchone()


# ---------------------------------------------------------------------------
# Social Manager DB - Scheduling & publishing
# ---------------------------------------------------------------------------


def get_next_approved_post(platform: str) -> Optional[sqlite3.Row]:
    """Return the oldest approved, not-yet-scheduled post for a platform."""
    with get_social_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM social_posts
            WHERE platform = ?
              AND status = 'APPROVED'
              AND (scheduled_at IS NULL OR scheduled_at = '')
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (platform,),
        ).fetchone()


def set_post_scheduled(post_id: int, scheduled_at: str):
    """Assign a schedule while keeping the editorial state APPROVED."""
    with get_social_connection() as conn:
        conn.execute(
            """
            UPDATE social_posts
            SET status = 'APPROVED',
                scheduled_at = ?,
                published_at = NULL,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (scheduled_at, post_id),
        )


def get_due_scheduled_posts() -> List[sqlite3.Row]:
    """Return approved posts whose scheduled publication time has arrived."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_social_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM social_posts
            WHERE status = 'APPROVED'
              AND scheduled_at IS NOT NULL
              AND scheduled_at != ''
              AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
            """,
            (now_str,),
        ).fetchall()


def mark_post_as_published(post_id: int):
    """Mark a post as published and record the actual publication timestamp."""
    with get_social_connection() as conn:
        conn.execute(
            """
            UPDATE social_posts
            SET status = 'PUBLISHED',
                published_at = datetime('now'),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (post_id,),
        )


def get_latest_scheduled_time(platform: str) -> Optional[str]:
    """Return the latest future/active schedule for the supplied platform."""
    with get_social_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(scheduled_at) AS latest
            FROM social_posts
            WHERE platform = ?
              AND status = 'APPROVED'
              AND scheduled_at IS NOT NULL
              AND scheduled_at != ''
            """,
            (platform,),
        ).fetchone()
    return row["latest"] if row and row["latest"] else None


def count_pending_posts() -> int:
    """Return the number of posts awaiting human review."""
    with get_social_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM social_posts WHERE status = 'PENDING'"
        ).fetchone()
    return int(row["total"] if row else 0)


def update_post_schedule_date(post_id: int, scheduled_at: str):
    """Update `scheduled_at` without touching `published_at`."""
    formatted_date = scheduled_at.strip().replace("T", " ")
    if len(formatted_date) == 16:
        formatted_date += ":00"

    # Validate before writing malformed values into a text-backed date column.
    datetime.strptime(formatted_date, "%Y-%m-%d %H:%M:%S")

    with get_social_connection() as conn:
        conn.execute(
            """
            UPDATE social_posts
            SET status = 'APPROVED',
                scheduled_at = ?,
                published_at = NULL,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (formatted_date, post_id),
        )


# ---------------------------------------------------------------------------
# Social Manager DB - Dashboard read models
# ---------------------------------------------------------------------------


_POST_WITH_ARTICLE_SELECT = """
    SELECT
        sp.*,
        ba.title AS article_title,
        ba.link AS article_link,
        ba.pub_date AS article_pub_date,
        ba.media_url AS article_media_url
    FROM social_posts AS sp
    JOIN blog_articles AS ba ON ba.id = sp.article_id
"""


def get_pending_posts_with_articles() -> List[sqlite3.Row]:
    """Return review items enriched with their source article."""
    with get_social_connection() as conn:
        return conn.execute(
            _POST_WITH_ARTICLE_SELECT
            + """
              WHERE sp.status = 'PENDING'
              ORDER BY ba.pub_date DESC, sp.platform ASC, sp.variation_number ASC
              """
        ).fetchall()


def get_all_posts_with_articles() -> List[sqlite3.Row]:
    """Return the complete administrative/timeline read model."""
    with get_social_connection() as conn:
        return conn.execute(
            _POST_WITH_ARTICLE_SELECT
            + """
              ORDER BY ba.pub_date DESC, sp.created_at DESC, sp.id DESC
              """
        ).fetchall()


# Backward-compatible dashboard helpers retained for existing callers.
def get_pending_posts() -> List[sqlite3.Row]:
    with get_social_connection() as conn:
        return conn.execute(
            "SELECT * FROM social_posts WHERE status = 'PENDING' ORDER BY created_at DESC"
        ).fetchall()


def get_scheduled_posts() -> List[sqlite3.Row]:
    with get_social_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM social_posts
            WHERE status = 'APPROVED'
            ORDER BY scheduled_at IS NULL, scheduled_at ASC
            """
        ).fetchall()


def get_approved_and_scheduled_posts() -> List[sqlite3.Row]:
    return get_scheduled_posts()