# social_dashboard/dashboard_social.py
# Operational dashboard for social content entities, relationships, review, and planning.

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import APP_TIMEZONE
from database.articles import get_blog_article_by_id
from database.connections import get_social_connection
from database.posts import (
    get_next_variation_number,
    get_social_post_by_id,
    insert_social_post,
    mark_post_as_published,
    update_post_schedule_date,
    update_social_post_status,
)
from integrations.facebook import post_to_facebook
from integrations.mastodon import post_to_mastodon
from social.copywriter import generate_custom_social_post, generate_social_post, rewrite_social_post
from social.scheduling import process_scheduling

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SmartCartLab Social Dashboard")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR))

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
UTC = timezone.utc

# image-generator is a sibling project; images are only served from its output folder.
IMAGE_OUTPUT_ROOT = (BASE_DIR.parent.parent / "image-generator" / "output").resolve()

ENTITY_TYPES = {
    "articles": "Articles",
    "topics": "Topics",
    "posts": "Posts",
    "prompts": "Image prompts",
    "images": "Images",
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(LOCAL_TIMEZONE)


def _display_datetime(value: str | None) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%d/%m/%Y %H:%M") if parsed else ""


def _form_datetime(value: str | None) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%Y-%m-%dT%H:%M") if parsed else ""


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_social_connection() as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def _row(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_social_connection() as connection:
        row = connection.execute(sql, params).fetchone()
    return dict(row) if row else None


def _decorate_post(post: dict[str, Any]) -> dict[str, Any]:
    post["scheduled_at_display"] = _display_datetime(post.get("scheduled_at"))
    post["published_at_display"] = _display_datetime(post.get("published_at"))
    post["scheduled_at_form"] = _form_datetime(post.get("scheduled_at"))
    return post


def _load_entities(entity: str, search: str = "") -> tuple[list[str], list[dict[str, Any]]]:
    if entity not in ENTITY_TYPES:
        entity = "articles"

    term = f"%{search.strip()}%"

    if entity == "articles":
        rows = _rows(
            """
            SELECT
                a.id,
                a.title,
                a.slug,
                a.link,
                a.pub_date,
                a.lang,
                a.processing_status,
                a.created_at,
                (SELECT COUNT(*) FROM article_topics t WHERE t.article_id = a.id) AS topic_count,
                (SELECT COUNT(*) FROM social_posts p WHERE p.article_id = a.id) AS post_count,
                (SELECT COUNT(*) FROM image_prompts ip WHERE ip.article_id = a.id) AS prompt_count
            FROM blog_articles a
            WHERE a.title LIKE ? OR a.id LIKE ? OR a.slug LIKE ?
            ORDER BY COALESCE(a.pub_date, a.created_at) DESC
            """,
            (term, term, term),
        )
        columns = ["id", "title", "pub_date", "topics", "posts", "prompts"]
        for row in rows:
            row["pub_date_display"] = _display_datetime(row.get("pub_date"))
        return columns, rows

    if entity == "topics":
        rows = _rows(
            """
            SELECT
                t.id,
                t.article_id,
                a.title AS article_title,
                t.topic,
                t.created_at,
                (SELECT COUNT(*) FROM social_posts p WHERE p.topic_id = t.id) AS post_count,
                (SELECT COUNT(*) FROM image_prompts ip WHERE ip.topic_id = t.id) AS prompt_count,
                (SELECT COUNT(*) FROM image_prompts ip JOIN generated_images gi ON gi.prompt_id = ip.id WHERE ip.topic_id = t.id) AS image_count
            FROM article_topics t
            JOIN blog_articles a ON a.id = t.article_id
            WHERE t.topic LIKE ? OR a.title LIKE ?
            ORDER BY t.id DESC
            """,
            (term, term),
        )
        return ["id", "article_title", "topic", "posts", "prompts", "images"], rows

    if entity == "posts":
        rows = _rows(
            """
            SELECT
                p.id,
                p.article_id,
                a.title AS article_title,
                p.topic_id,
                t.topic,
                p.platform,
                p.variation_number,
                p.status,
                p.content,
                p.media_url,
                p.scheduled_at,
                p.published_at,
                p.created_at,
                p.updated_at
            FROM social_posts p
            JOIN blog_articles a ON a.id = p.article_id
            LEFT JOIN article_topics t ON t.id = p.topic_id
            WHERE p.content LIKE ? OR a.title LIKE ? OR COALESCE(t.topic, '') LIKE ? OR p.platform LIKE ?
            ORDER BY p.created_at DESC, p.id DESC
            """,
            (term, term, term, term),
        )
        for row in rows:
            _decorate_post(row)
        return ["id", "platform", "article_title", "topic", "status", "scheduled_at", "content"], rows

    if entity == "prompts":
        rows = _rows(
            """
            SELECT
                ip.id,
                ip.article_id,
                a.title AS article_title,
                ip.topic_id,
                t.topic,
                ip.prompt,
                ip.created_at,
                (SELECT COUNT(*) FROM generated_images gi WHERE gi.prompt_id = ip.id) AS image_count
            FROM image_prompts ip
            JOIN blog_articles a ON a.id = ip.article_id
            JOIN article_topics t ON t.id = ip.topic_id
            WHERE ip.prompt LIKE ? OR a.title LIKE ? OR t.topic LIKE ?
            ORDER BY ip.created_at DESC, ip.id DESC
            """,
            (term, term, term),
        )
        return ["id", "article_title", "topic", "image_count", "created_at", "prompt"], rows

    rows = _rows(
        """
        SELECT
            gi.id,
            gi.article_id,
            a.title AS article_title,
            gi.topic_id,
            t.topic,
            gi.prompt_id,
            ip.prompt,
            gi.provider,
            gi.model,
            gi.width,
            gi.height,
            gi.file_path,
            gi.created_at
        FROM generated_images gi
        JOIN blog_articles a ON a.id = gi.article_id
        JOIN article_topics t ON t.id = gi.topic_id
        JOIN image_prompts ip ON ip.id = gi.prompt_id
        WHERE a.title LIKE ? OR t.topic LIKE ? OR ip.prompt LIKE ? OR gi.file_path LIKE ?
        ORDER BY gi.created_at DESC, gi.id DESC
        """,
        (term, term, term, term),
    )
    return ["id", "article_title", "topic", "prompt_id", "provider", "model", "size", "file_path", "created_at"], rows


def _load_article_map() -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT id, title, pub_date
        FROM blog_articles
        ORDER BY COALESCE(pub_date, created_at) DESC
        """
    )


def _load_article_graph(article_id: str | None) -> dict[str, Any] | None:
    if not article_id:
        articles = _load_article_map()
        if not articles:
            return None
        article_id = str(articles[0]["id"])

    article = _row("SELECT * FROM blog_articles WHERE id = ?", (article_id,))
    if not article:
        return None

    topics = _rows(
        "SELECT * FROM article_topics WHERE article_id = ? ORDER BY id",
        (article_id,),
    )
    posts = _rows(
        """
        SELECT p.*, t.topic
        FROM social_posts p
        LEFT JOIN article_topics t ON t.id = p.topic_id
        WHERE p.article_id = ?
        ORDER BY p.topic_id IS NULL, p.topic_id, p.platform, p.id
        """,
        (article_id,),
    )
    prompts = _rows(
        """
        SELECT ip.*, t.topic
        FROM image_prompts ip
        JOIN article_topics t ON t.id = ip.topic_id
        WHERE ip.article_id = ?
        ORDER BY ip.topic_id
        """,
        (article_id,),
    )
    images = _rows(
        """
        SELECT gi.*, ip.prompt
        FROM generated_images gi
        JOIN image_prompts ip ON ip.id = gi.prompt_id
        WHERE gi.article_id = ?
        ORDER BY gi.topic_id, gi.prompt_id, gi.id
        """,
        (article_id,),
    )

    for post in posts:
        _decorate_post(post)

    prompt_by_topic: dict[int, dict[str, Any]] = {int(p["topic_id"]): p for p in prompts}
    images_by_prompt: dict[int, list[dict[str, Any]]] = {}
    for image in images:
        images_by_prompt.setdefault(int(image["prompt_id"]), []).append(image)

    topic_nodes = []
    topic_ids = {int(topic["id"]) for topic in topics}
    for topic in topics:
        topic_id = int(topic["id"])
        topic_posts = [p for p in posts if p.get("topic_id") == topic_id]
        prompt = prompt_by_topic.get(topic_id)
        prompt_images = images_by_prompt.get(int(prompt["id"]), []) if prompt else []
        topic_nodes.append(
            {
                "topic": topic,
                "posts": topic_posts,
                "prompt": prompt,
                "images": prompt_images,
            }
        )

    direct_posts = [p for p in posts if p.get("topic_id") is None or int(p.get("topic_id")) not in topic_ids]

    return {
        "article": article,
        "topics": topic_nodes,
        "direct_posts": direct_posts,
        "all_posts": posts,
        "all_prompts": prompts,
        "all_images": images,
    }


@app.get("/")
def render_dashboard(
    request: Request,
    tab: str = Query(default="entities"),
    entity: str = Query(default="articles"),
    search: str = Query(default=""),
    article_id: str | None = Query(default=None),
    selected_articles: list[str] = Query(default=[]),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    platform: str = Query(default="all"),
):
    if tab not in {"entities", "graph", "review", "calendar"}:
        tab = "entities"

    entity_columns, entity_rows = _load_entities(entity, search)
    articles = _load_article_map()
    graph = _load_article_graph(article_id) if tab == "graph" else None

    posts = _load_entities("posts")[1]
    review_posts = [p for p in posts if p.get("status") in {"PENDING", "APPROVED", "REJECTED"}]

    if platform != "all":
        review_posts = [p for p in review_posts if p.get("platform") == platform]

    calendar_start = _parse_datetime(start) if start else None
    calendar_end = _parse_datetime(end) if end else None
    today = datetime.now(LOCAL_TIMEZONE).date()
    window_start = calendar_start.date() if calendar_start else today - timedelta(days=7)
    window_end = calendar_end.date() if calendar_end else window_start + timedelta(days=27)
    if window_end < window_start:
        window_start, window_end = window_end, window_start
    if (window_end - window_start).days > 90:
        window_end = window_start + timedelta(days=90)

    selected = {str(value) for value in selected_articles}
    calendar_posts = posts
    if selected:
        calendar_posts = [p for p in calendar_posts if str(p["article_id"]) in selected]
    if platform != "all":
        calendar_posts = [p for p in calendar_posts if p.get("platform") == platform]

    calendar_articles = [a for a in articles if not selected or str(a["id"]) in selected]
    days = [window_start + timedelta(days=i) for i in range((window_end - window_start).days + 1)]

    response = templates.TemplateResponse(
        request=request,
        name="dashboard_social.html",
        context={
            "tab": tab,
            "entity": entity,
            "entity_types": ENTITY_TYPES,
            "entity_columns": entity_columns,
            "entity_rows": entity_rows,
            "search": search,
            "articles": articles,
            "graph": graph,
            "review_posts": review_posts,
            "platforms": sorted({str(p["platform"]) for p in posts}),
            "platform": platform,
            "selected_articles": selected,
            "calendar_articles": calendar_articles,
            "calendar_posts": calendar_posts,
            "calendar_days": days,
            "window_start": window_start,
            "window_end": window_end,
            "today": today,
        },
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/images/{image_id}/file")
def serve_generated_image(image_id: int):
    # The client sends only the id: the path always comes from the DB, never from the request.
    row = _row("SELECT file_path FROM generated_images WHERE id = ?", (image_id,))
    if not row or not row.get("file_path"):
        raise HTTPException(status_code=404)

    image_path = Path(row["file_path"]).resolve()
    # Resolving first neutralizes ".." and symlinks before the containment check.
    if not image_path.is_relative_to(IMAGE_OUTPUT_ROOT) or not image_path.is_file():
        logger.warning("Image #%s not served: %s", image_id, image_path)
        raise HTTPException(status_code=404)

    return FileResponse(image_path)


@app.post("/posts/create")
def create_custom_post(
    article_id: str = Form(...),
    platform: str = Form(...),
    prompt: str = Form(""),
    content: str = Form(""),
):
    article = get_blog_article_by_id(article_id)
    if not article:
        return RedirectResponse(url="/?tab=review&error=article-not-found", status_code=303)

    article_data = dict(article)
    platform = platform.strip().lower()
    if platform not in {"facebook", "mastodon"}:
        return RedirectResponse(url="/?tab=review&error=unsupported-platform", status_code=303)

    manual_content = content.strip()
    custom_prompt = prompt.strip()
    if manual_content:
        post_content = manual_content
    elif custom_prompt:
        post_content = generate_custom_social_post(
            article_title=article_data["title"],
            article_content=article_data["content"],
            article_link=article_data["link"],
            platform=platform,
            user_prompt=custom_prompt,
            language=article_data.get("lang") or "it",
        )
    else:
        post_content = None

    if not post_content:
        return RedirectResponse(url="/?tab=review&error=generation-failed", status_code=303)

    post_id = insert_social_post(
        article_id=article_id,
        platform=platform,
        content=post_content,
        variation_number=get_next_variation_number(article_id, platform),
        media_url=None,
    )
    logger.info("Created custom PENDING post #%s for article %s.", post_id, article_id)
    return RedirectResponse(url="/?tab=review&saved=1", status_code=303)


@app.post("/posts/{post_id}/approve")
def approve_post(post_id: int):
    update_social_post_status(post_id, status="APPROVED")
    return RedirectResponse(url="/?tab=review", status_code=303)


@app.post("/posts/{post_id}/reject")
def reject_post(post_id: int):
    update_social_post_status(post_id, status="REJECTED")
    return RedirectResponse(url="/?tab=review", status_code=303)


@app.post("/posts/{post_id}/restore")
def restore_rejected_post(post_id: int):
    update_social_post_status(post_id, status="PENDING")
    return RedirectResponse(url="/?tab=review", status_code=303)


@app.post("/posts/{post_id}/update")
def update_post_content(post_id: int, content: str = Form(...)):
    update_social_post_status(post_id, status="PENDING", content=content)
    return RedirectResponse(url="/?tab=review", status_code=303)


@app.post("/posts/{post_id}/regenerate-topic")
def regenerate_post_from_topic(post_id: int):
    post = get_social_post_by_id(post_id)
    if not post:
        return RedirectResponse(url="/?tab=review", status_code=303)

    data = dict(post)
    topic_id = data.get("topic_id")
    if not topic_id:
        return RedirectResponse(url="/?tab=review&error=no-topic", status_code=303)

    topic_row = _row("SELECT * FROM article_topics WHERE id = ?", (topic_id,))
    article = get_blog_article_by_id(str(data["article_id"]))
    if not topic_row or not article:
        return RedirectResponse(url="/?tab=review&error=topic-context-missing", status_code=303)

    article_data = dict(article)
    generated = generate_social_post(
        article_title=article_data["title"],
        article_content=article_data["content"],
        article_link=article_data["link"],
        topic=topic_row["topic"],
        platform=data["platform"],
        language=article_data.get("lang") or "it",
    )
    update_social_post_status(
        post_id,
        status="PENDING",
        content=generated["content"],
    )
    return RedirectResponse(url="/?tab=review&saved=1", status_code=303)


@app.post("/posts/{post_id}/regenerate-custom")
def regenerate_post_with_prompt(post_id: int, prompt: str = Form(...)):
    post = get_social_post_by_id(post_id)
    if not post:
        return RedirectResponse(url="/?tab=review", status_code=303)

    article = get_blog_article_by_id(str(post["article_id"]))
    if not article or not prompt.strip():
        return RedirectResponse(url="/?tab=review&error=missing-context", status_code=303)

    article_data = dict(article)
    generated = generate_custom_social_post(
        article_title=article_data["title"],
        article_content=article_data["content"],
        article_link=article_data["link"],
        platform=post["platform"],
        user_prompt=prompt.strip(),
        language=article_data.get("lang") or "it",
    )
    if not generated:
        return RedirectResponse(url="/?tab=review&error=generation-failed", status_code=303)

    update_social_post_status(post_id, status="PENDING", content=generated)
    return RedirectResponse(url="/?tab=review&saved=1", status_code=303)


@app.post("/posts/{post_id}/rewrite")
def rewrite_post(post_id: int):
    post = get_social_post_by_id(post_id)
    if post:
        data = dict(post)
        new_content = rewrite_social_post(data.get("content", ""), data.get("platform", "mastodon"))
        if new_content:
            update_social_post_status(post_id, status="PENDING", content=new_content)
    return RedirectResponse(url="/?tab=review", status_code=303)


@app.post("/posts/{post_id}/reschedule")
def reschedule_post(post_id: int, scheduled_at: str = Form(...)):
    update_post_schedule_date(post_id, scheduled_at)
    return RedirectResponse(url="/?tab=calendar", status_code=303)


@app.post("/posts/schedule-approved")
def schedule_approved_posts():
    for platform_name in ("mastodon", "facebook"):
        process_scheduling(platform=platform_name)
    return RedirectResponse(url="/?tab=calendar", status_code=303)


@app.post("/posts/{post_id}/publish-now")
def publish_post_now(post_id: int):
    post = get_social_post_by_id(post_id)
    if not post:
        return RedirectResponse(url="/?tab=review", status_code=303)

    data = dict(post)
    platform_name = str(data.get("platform", "")).lower()
    content = data.get("content", "")
    media_url = data.get("media_url")
    success = False

    if platform_name == "facebook":
        success = post_to_facebook(content)
    elif platform_name == "mastodon":
        result = post_to_mastodon(content, media_ids=[media_url] if media_url else None)
        success = result is not None

    if success:
        mark_post_as_published(post_id)

    return RedirectResponse(url="/?tab=review", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "social_dashboard.dashboard_social:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )