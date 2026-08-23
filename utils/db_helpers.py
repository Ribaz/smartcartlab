# utils/db_helpers.py
# Shared database utilities.
# All database access goes through these functions.

import os
import sqlite3
from typing import Dict, List, Optional
from config.settings import DB_PATH, SOCIAL_DB_PATH


# ---------------------------------------------------------------------------
# SmartCartLab Core DB
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Open and return a connection to the primary SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create primary tables if they do not exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            asin          TEXT NOT NULL,
            title         TEXT,
            category      TEXT,
            current_price REAL,
            avg_price_90d REAL,
            avg_price_1y  REAL,
            review_score  REAL,
            review_count  INTEGER,
            final_score   REAL,
            analyzed_at   TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_products(products: List[Dict]):
    """
    Insert a list of scored products into the products table.
    Each product dict must already contain final_score.
    """
    conn = get_connection()
    conn.executemany("""
        INSERT INTO products
            (asin, title, category, current_price, avg_price_90d,
             avg_price_1y, review_score, review_count, final_score, analyzed_at)
        VALUES
            (:asin, :title, :category, :current_price, :avg_price_90d,
             :avg_price_1y, :review_score, :review_count, :final_score, datetime('now'))
    """, products)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Social Manager DB
# ---------------------------------------------------------------------------

def get_social_connection() -> sqlite3.Connection:
    """Open and return a connection to the Social Manager SQLite database."""
    os.makedirs(os.path.dirname(SOCIAL_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SOCIAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_social_db():
    """Create social manager tables if they do not exist."""
    conn = get_social_connection()
    
    # 1. Tracked WordPress blog articles
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blog_articles (
            id         TEXT PRIMARY KEY,
            slug       TEXT,
            title      TEXT NOT NULL,
            link       TEXT NOT NULL,
            pub_date   TEXT,
            media_url  TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 2. Multi-variant social posts with lifecycle management
    conn.execute("""
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
    """)
    conn.commit()
    conn.close()


def save_blog_article(article: Dict) -> bool:
    """
    Insert a blog article if not present.
    Returns True if newly inserted, False if already exists.
    """
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM blog_articles WHERE id = ?", (article["id"],))
    if cursor.fetchone():
        conn.close()
        return False

    cursor.execute("""
        INSERT INTO blog_articles (id, slug, title, link, pub_date, media_url)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        article["id"],
        article.get("slug", ""),
        article["title"],
        article["link"],
        article.get("date_gmt", ""),
        article.get("media_url")
    ))
    conn.commit()
    conn.close()
    return True


def get_variations_count(article_id: str, platform: str) -> int:
    """Count how many variations already exist for a given article and platform."""
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM social_posts
        WHERE article_id = ? AND platform = ?
    """, (article_id, platform))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Social Manager DB - Posts CRUD & Lifecycle
# ---------------------------------------------------------------------------

def insert_social_post(
    article_id: str,
    platform: str,
    content: str,
    variation_number: int = 1,
    media_url: Optional[str] = None,
    scheduled_at: Optional[str] = None
) -> int:
    """Insert a new draft social post with PENDING status and return its ID."""
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO social_posts
            (article_id, platform, variation_number, content, media_url, status, scheduled_at)
        VALUES
            (?, ?, ?, ?, ?, 'PENDING', ?)
    """, (article_id, platform, variation_number, content, media_url, scheduled_at))
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return post_id


def update_social_post_status(post_id: int, status: str, content: Optional[str] = None):
    """Update post status (e.g. APPROVED, SCHEDULED, PUBLISHED, REJECTED) and optionally content."""
    conn = get_social_connection()
    if content:
        conn.execute("""
            UPDATE social_posts
            SET status = ?, content = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (status, content, post_id))
    else:
        conn.execute("""
            UPDATE social_posts
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (status, post_id))
    conn.commit()
    conn.close()


def update_post_telegram_id(post_id: int, message_id: int):
    """Associate Telegram message ID with a social post for callback routing."""
    conn = get_social_connection()
    conn.execute("""
        UPDATE social_posts
        SET telegram_message_id = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (message_id, post_id))
    conn.commit()
    conn.close()


def get_social_post_by_id(post_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single social post record by primary ID."""
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM social_posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_social_post_by_telegram_id(message_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single social post record using its associated Telegram message ID."""
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM social_posts WHERE telegram_message_id = ?", (message_id,))
    row = cursor.fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Social Manager DB - Scheduling & Publishing Queries
# ---------------------------------------------------------------------------

def get_next_approved_post(platform: str) -> Optional[sqlite3.Row]:
    """Retrieve the oldest APPROVED post waiting to be scheduled for a given platform."""
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM social_posts
        WHERE status = 'APPROVED' AND platform = ?
        ORDER BY id ASC
        LIMIT 1
    """, (platform,))
    row = cursor.fetchone()
    conn.close()
    return row


def set_post_scheduled(post_id: int, scheduled_at: str):
    """Assign a scheduled publication timestamp and update status to SCHEDULED."""
    conn = get_social_connection()
    conn.execute("""
        UPDATE social_posts
        SET status = 'SCHEDULED', scheduled_at = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (scheduled_at, post_id))
    conn.commit()
    conn.close()


def get_due_scheduled_posts() -> List[sqlite3.Row]:
    """Retrieve all SCHEDULED posts whose publication timestamp has arrived."""
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM social_posts
        WHERE status = 'SCHEDULED'
          AND scheduled_at <= datetime('now')
        ORDER BY scheduled_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_post_as_published(post_id: int):
    """Mark a post as PUBLISHED and track publication timestamp."""
    conn = get_social_connection()
    conn.execute("""
        UPDATE social_posts
        SET status = 'PUBLISHED', published_at = datetime('now'), updated_at = datetime('now')
        WHERE id = ?
    """, (post_id,))
    conn.commit()
    conn.close()


def get_latest_scheduled_time(platform: str) -> Optional[str]:
    """
    Returns the latest scheduled_at timestamp among all SCHEDULED posts for a given platform.
    """
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT MAX(scheduled_at) FROM social_posts 
        WHERE platform = ? AND status = 'SCHEDULED'
        """,
        (platform,)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None


def count_pending_posts() -> int:
    """
    Returns the total number of PENDING posts waiting for review.
    """
    conn = get_social_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM social_posts WHERE status = 'PENDING'")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0