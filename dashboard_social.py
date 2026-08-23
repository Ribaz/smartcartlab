# dashboard_social.py
# Local web dashboard for managing social post approvals and timeline.

import logging
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from utils.db_helpers import (
    get_pending_posts,
    get_approved_and_scheduled_posts,
    update_post_status,
    update_social_post_status,
    get_social_post_by_id,
    mark_post_as_published,
    update_post_schedule_date,
)
from src.ai.generator import rewrite_social_post
from src.integrations.facebook import post_to_facebook
from src.integrations.mastodon import post_to_mastodon


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SmartCartLab Social Dashboard")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Dashboard Main Routes
# ---------------------------------------------------------------------------

@app.get("/")
def render_dashboard(request: Request):
    pending = get_pending_posts()
    active_queue = get_approved_and_scheduled_posts()
    
    return templates.TemplateResponse(
        request,
        "dashboard_social.html",
        context={
            "pending_posts": pending,
            "scheduled_posts": active_queue
        }
    )


# ---------------------------------------------------------------------------
# Post Action Endpoints
# ---------------------------------------------------------------------------

@app.post("/posts/{post_id}/approve")
def approve_post(post_id: int):
    update_post_status(post_id, "APPROVED")
    logger.info(f"Post #{post_id} approved via web dashboard.")
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/reject")
def reject_post(post_id: int):
    update_post_status(post_id, "REJECTED")
    logger.info(f"Post #{post_id} rejected via web dashboard.")
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/cancel")
def cancel_scheduled_post(post_id: int):
    update_post_status(post_id, "PENDING")
    logger.info(f"Post #{post_id} reset to PENDING.")
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/update")
def update_post_content(post_id: int, content: str = Form(...)):
    update_social_post_status(post_id, status="PENDING", content=content)
    logger.info(f"Post #{post_id} content updated.")
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/rewrite")
def rewrite_post(post_id: int):
    post = get_social_post_by_id(post_id)
    if post:
        post_dict = dict(post)
        platform = post_dict.get("platform")
        current_content = post_dict.get("content")
        
        new_content = rewrite_social_post(current_content, platform)
        if new_content:
            update_social_post_status(post_id, status="PENDING", content=new_content)
            logger.info(f"Post #{post_id} successfully rewritten by AI.")
        else:
            logger.error(f"AI rewrite failed for post #{post_id}.")
            
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/publish-now")
def publish_post_now(post_id: int):
    post = get_social_post_by_id(post_id)
    if post:
        post_dict = dict(post)
        platform = post_dict.get("platform", "").lower()
        content = post_dict.get("content", "")
        media_url = post_dict.get("media_url")
        
        success = False
        if "facebook" in platform:
            success = post_to_facebook(content)
        elif "mastodon" in platform:
            media_ids = [media_url] if media_url else None
            result = post_to_mastodon(content, media_ids=media_ids)
            success = result is not None
        else:
            logger.warning(f"Unsupported platform '{platform}' for post #{post_id}.")

        if success:
            mark_post_as_published(post_id)
            logger.info(f"Post #{post_id} successfully published immediately to {platform}.")
        else:
            logger.error(f"Failed to immediately publish post #{post_id} to {platform}.")
        
    return RedirectResponse(url="/", status_code=303)


@app.post("/posts/{post_id}/reschedule")
def reschedule_post(post_id: int, scheduled_at: str = Form(...)):
    update_post_schedule_date(post_id, scheduled_at)
    logger.info(f"Post #{post_id} rescheduled to {scheduled_at}.")
    return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_social:app", host="0.0.0.0", port=8000, reload=True)