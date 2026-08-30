from __future__ import annotations

import sqlite3
from typing import List, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config.settings import APP_TIMEZONE

from database.connections import get_social_connection


VALID_SOCIAL_STATUSES = {"PENDING", "APPROVED", "PUBLISHED", "REJECTED"}

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
UTC = timezone.utc
DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"



def _validate_social_status(status: str) -> None:
    if status not in VALID_SOCIAL_STATUSES:
        allowed = ", ".join(sorted(VALID_SOCIAL_STATUSES))
        raise ValueError(f"Unsupported social post status '{status}'. Allowed: {allowed}")


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


def get_social_post_by_id(post_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single social post by primary ID."""
    with get_social_connection() as conn:
        return conn.execute(
            "SELECT * FROM social_posts WHERE id = ?",
            (post_id,),
        ).fetchone()


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
    now_str = datetime.now(UTC).strftime(DB_DATETIME_FORMAT)
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


def update_post_schedule_date (post_id: int, scheduled_at: str) -> None:
    """Interpret a dashboard datetime as local time and store it as UTC."""
    normalized = scheduled_at.strip().replace("T", " ")

    if len(normalized) == 16:
        normalized += ":00"

    local_datetime = datetime.strptime(
        normalized,
        DB_DATETIME_FORMAT,
    ).replace(tzinfo=LOCAL_TIMEZONE)

    utc_datetime = local_datetime.astimezone(UTC)
    utc_value = utc_datetime.strftime(DB_DATETIME_FORMAT)

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
            (utc_value, post_id),
        )


def is_scheduling_slot_taken(
    platform: str,
    scheduled_at: str,
) -> bool:
    """Return True when the platform already has a post in the supplied slot."""
    with get_social_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM social_posts
            WHERE platform = ?
              AND status = 'APPROVED'
              AND scheduled_at = ?
            LIMIT 1
            """,
            (platform, scheduled_at),
        ).fetchone()

    return row is not None


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