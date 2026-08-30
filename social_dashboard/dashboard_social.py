# dashboard_social.py
# Local web dashboard for reviewing, scheduling, and publishing social content.

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from social.copywriter import rewrite_social_post
from integrations.facebook import post_to_facebook
from integrations.mastodon import post_to_mastodon
from database.posts import (
    get_all_posts_with_articles,
    get_pending_posts_with_articles,
    get_social_post_by_id,
    mark_post_as_published,
    update_post_schedule_date,
    update_social_post_status,
)

from config.settings import APP_TIMEZONE


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SmartCartLab Social Dashboard")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR))

TIMELINE_DAYS = 28
TIMELINE_PAST_DAYS = 7
ARTICLE_COLOR_COUNT = 8
MAX_TIMELINE_DAYS = 90

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
UTC = timezone.utc



def _parse_db_datetime(value: str | None) -> datetime | None:
    """Parse timestamps stored by SQLite and HTML datetime-local fields."""
    if not value:
        return None

    normalized = value.strip().replace("T", " ")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.replace(tzinfo=UTC).astimezone(LOCAL_TIMEZONE)
        except ValueError:
            continue

    return None


def _format_local_datetime(value: str | None) -> str:
    """Format a stored UTC timestamp for display in the local timezone."""
    parsed = _parse_db_datetime(value)
    return parsed.strftime("%d/%m/%Y %H:%M") if parsed else ""


def _format_local_datetime_for_form(value: str | None) -> str:
    """Format a stored UTC timestamp for an HTML datetime-local input."""
    parsed = _parse_db_datetime(value)
    return parsed.strftime("%Y-%m-%dT%H:%M") if parsed else ""


def _as_dict(row: Any) -> dict[str, Any]:
    """Convert a database row and add local-time values used by the dashboard."""
    post = dict(row)
    post["scheduled_at_display"] = _format_local_datetime(post.get("scheduled_at"))
    post["published_at_display"] = _format_local_datetime(post.get("published_at"))
    post["scheduled_at_form"] = _format_local_datetime_for_form(
        post.get("scheduled_at")
    )
    return post


def _event_datetime(post: dict[str, Any]) -> datetime | None:
    """
    Return the timestamp that should position the post on the timeline.

    Published posts use their actual publication time. Approved posts use their
    planned schedule. Pending and rejected posts remain outside the dated grid.
    """
    if post["status"] == "PUBLISHED":
        return _parse_db_datetime(post.get("published_at")) or _parse_db_datetime(
            post.get("scheduled_at")
        )
    if post["status"] == "APPROVED":
        return _parse_db_datetime(post.get("scheduled_at"))
    return None



def _resolve_window(start: str | None, end: str | None, today: date) -> tuple[date, date, bool]:
    """Resolve the requested timeline period and identify the default operational view."""
    default_start = today - timedelta(days=TIMELINE_PAST_DAYS)
    default_end = default_start + timedelta(days=TIMELINE_DAYS - 1)

    if not start and not end:
        return default_start, default_end, True

    try:
        window_start = date.fromisoformat(start) if start else default_start
        window_end = date.fromisoformat(end) if end else window_start + timedelta(days=TIMELINE_DAYS - 1)
    except ValueError:
        return default_start, default_end, True

    if window_end < window_start:
        window_start, window_end = window_end, window_start

    # Keep an accidental huge range from rendering thousands of grid columns.
    if (window_end - window_start).days + 1 > MAX_TIMELINE_DAYS:
        window_end = window_start + timedelta(days=MAX_TIMELINE_DAYS - 1)

    is_default = window_start == default_start and window_end == default_end
    return window_start, window_end, is_default


def _filter_timeline_rows(
    rows: list[Any],
    window_start: date,
    window_end: date,
    include_undated_operational: bool,
) -> list[Any]:
    """Keep complete article groups only when they have activity in the selected period."""
    visible_article_ids: set[str] = set()

    for raw_row in rows:
        post = _as_dict(raw_row)
        event_dt = _event_datetime(post)
        has_dated_activity = bool(
            event_dt and window_start <= event_dt.date() <= window_end
        )
        is_undated_operational = include_undated_operational and (
            post.get("status") == "PENDING"
            or (post.get("status") == "APPROVED" and not post.get("scheduled_at"))
        )

        if has_dated_activity or is_undated_operational:
            visible_article_ids.add(str(post["article_id"]))

    return [
        row for row in rows
        if str(row["article_id"]) in visible_article_ids
    ]

def _build_timeline(
    rows: list[Any],
    window_start: date,
    window_end: date,
) -> tuple[list[date], list[dict[str, Any]]]:
    """Group social posts by article and prepare a date-indexed timeline."""
    window_days = (window_end - window_start).days + 1
    days = [window_start + timedelta(days=offset) for offset in range(window_days)]
    articles: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for raw_row in rows:
        post = _as_dict(raw_row)
        article_id = str(post["article_id"])

        if article_id not in articles:
            articles[article_id] = {
                "id": article_id,
                "title": post.get("article_title") or f"Article {article_id}",
                "link": post.get("article_link"),
                "pub_date": post.get("article_pub_date"),
                "media_url": post.get("article_media_url") or post.get("media_url"),
                "color_index": len(articles) % ARTICLE_COLOR_COUNT,
                "posts": [],
                "posts_by_day": {day.isoformat(): [] for day in days},
                "pending": [],
                "unscheduled": [],
                "rejected": [],
                "outside_window": [],
                "counts": {
                    "PENDING": 0,
                    "APPROVED": 0,
                    "PUBLISHED": 0,
                    "REJECTED": 0,
                },
            }

        article = articles[article_id]
        article["posts"].append(post)
        article["counts"][post["status"]] = article["counts"].get(post["status"], 0) + 1

        event_dt = _event_datetime(post)
        post["event_at"] = event_dt
        post["event_time"] = event_dt.strftime("%H:%M") if event_dt else None
        post["event_date"] = event_dt.date().isoformat() if event_dt else None

        if post["status"] == "PENDING":
            article["pending"].append(post)
        elif post["status"] == "REJECTED":
            article["rejected"].append(post)
        elif event_dt is None:
            article["unscheduled"].append(post)
        elif window_start <= event_dt.date() <= window_end:
            article["posts_by_day"][event_dt.date().isoformat()].append(post)
        else:
            article["outside_window"].append(post)

    for article in articles.values():
        for posts in article["posts_by_day"].values():
            posts.sort(
                key=lambda post: (
                    post.get("event_at") or datetime.max.replace(tzinfo=LOCAL_TIMEZONE),
                    post.get("id", 0),
                )
            )

    # Most recently published articles first. Unknown dates fall to the bottom.
    def article_sort_key(article: dict[str, Any]) -> tuple[int, str]:
        parsed = _parse_db_datetime(article.get("pub_date"))
        if parsed:
            return (0, parsed.isoformat())
        return (1, article["id"])

    grouped = sorted(articles.values(), key=article_sort_key, reverse=True)
    return days, grouped


# ---------------------------------------------------------------------------
# Dashboard main route
# ---------------------------------------------------------------------------


@app.get("/")
def render_dashboard(
    request: Request,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    today = datetime.now(LOCAL_TIMEZONE).date()
    window_start, window_end, is_default_window = _resolve_window(start, end, today)

    pending = [
        _as_dict(row)
        for row in get_pending_posts_with_articles()
    ]
    all_posts = [
        _as_dict(row)
        for row in get_all_posts_with_articles()
    ]

    timeline_rows = _filter_timeline_rows(
        rows=all_posts,
        window_start=window_start,
        window_end=window_end,
        include_undated_operational=is_default_window,
    )
    timeline_days, article_groups = _build_timeline(
        rows=timeline_rows,
        window_start=window_start,
        window_end=window_end,
    )

    window_length = (window_end - window_start).days + 1
    previous_start = window_start - timedelta(days=window_length)
    previous_end = window_end - timedelta(days=window_length)
    next_start = window_start + timedelta(days=window_length)
    next_end = window_end + timedelta(days=window_length)
    today_start = today - timedelta(days=TIMELINE_PAST_DAYS)
    today_end = today_start + timedelta(days=TIMELINE_DAYS - 1)

    platforms = sorted({row["platform"] for row in all_posts})
    articles = sorted(
        {
            (str(row["article_id"]), row["article_title"] or str(row["article_id"]))
            for row in all_posts
        },
        key=lambda item: item[1].lower(),
    )

    response = templates.TemplateResponse(
        request=request,
        name="dashboard_social.html",
        context={
            "pending_posts": pending,
            "all_posts": all_posts,
            "article_groups": article_groups,
            "timeline_days": timeline_days,
            "window_start": window_start,
            "window_end": window_end,
            "previous_start": previous_start.isoformat(),
            "previous_end": previous_end.isoformat(),
            "next_start": next_start.isoformat(),
            "next_end": next_end.isoformat(),
            "today_start": today_start.isoformat(),
            "today_end": today_end.isoformat(),
            "today": today,
            "platforms": platforms,
            "articles": articles,
            "is_default_window": is_default_window,
        },
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


# ---------------------------------------------------------------------------
# Post action endpoints
# ---------------------------------------------------------------------------


@app.post("/posts/{post_id}/approve")
def approve_post(post_id: int):
    # Approval and scheduling intentionally remain separate responsibilities.
    update_social_post_status(post_id, status="APPROVED")
    logger.info("Post #%s approved via web dashboard.", post_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/reject")
def reject_post(post_id: int):
    update_social_post_status(post_id, status="REJECTED")
    logger.info("Post #%s rejected via web dashboard.", post_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/restore")
def restore_rejected_post(post_id: int):
    """Administrative escape hatch: return a rejected post to human review."""
    update_social_post_status(post_id, status="PENDING")
    logger.info("Rejected post #%s restored to PENDING.", post_id)
    return RedirectResponse(url="/#all-posts", status_code=303)


@app.post("/posts/{post_id}/cancel")
def cancel_scheduled_post(post_id: int):
    """Return an approved post to the review queue and clear its schedule."""
    update_social_post_status(
        post_id,
        status="PENDING",
        clear_schedule=True,
    )
    logger.info("Post #%s returned to PENDING and unscheduled.", post_id)
    return RedirectResponse(url="/#all-posts", status_code=303)


@app.post("/posts/{post_id}/update")
def update_post_content(post_id: int, content: str = Form(...)):
    update_social_post_status(post_id, status="PENDING", content=content)
    logger.info("Post #%s content updated.", post_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/rewrite")
def rewrite_post(post_id: int):
    post = get_social_post_by_id(post_id)
    if not post:
        logger.warning("Cannot rewrite missing post #%s.", post_id)
        return RedirectResponse(url="/", status_code=303)

    post_dict = dict(post)
    platform = post_dict.get("platform")
    current_content = post_dict.get("content")

    new_content = rewrite_social_post(current_content, platform)
    if new_content:
        update_social_post_status(post_id, status="PENDING", content=new_content)
        logger.info("Post #%s successfully rewritten by AI.", post_id)
    else:
        logger.error("AI rewrite failed for post #%s.", post_id)

    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/publish-now")
def publish_post_now(post_id: int):
    post = get_social_post_by_id(post_id)
    if not post:
        logger.warning("Cannot publish missing post #%s.", post_id)
        return RedirectResponse(url="/#all-posts", status_code=303)

    post_dict = dict(post)
    platform = post_dict.get("platform", "").lower()
    content = post_dict.get("content", "")
    media_url = post_dict.get("media_url")

    success = False
    if platform == "facebook":
        # Keep the integration call compatible with the existing dashboard.
        success = post_to_facebook(content)
    elif platform == "mastodon":
        media_ids = [media_url] if media_url else None
        result = post_to_mastodon(content, media_ids=media_ids)
        success = result is not None
    else:
        logger.warning("Unsupported platform '%s' for post #%s.", platform, post_id)

    if success:
        mark_post_as_published(post_id)
        logger.info("Post #%s successfully published immediately to %s.", post_id, platform)
    else:
        logger.error("Failed to immediately publish post #%s to %s.", post_id, platform)

    return RedirectResponse(url="/#all-posts", status_code=303)


@app.post("/posts/{post_id}/reschedule")
def reschedule_post(post_id: int, scheduled_at: str = Form(...)):
    update_post_schedule_date(post_id, scheduled_at)
    logger.info("Post #%s scheduled for %s.", post_id, scheduled_at)
    return RedirectResponse(url="/#timeline", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "social_dashboard.dashboard_social:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
