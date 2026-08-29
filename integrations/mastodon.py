# src/integrations/mastodon.py
# Mastodon API client for publishing posts and uploading media.

import logging
import requests
from typing import Dict, Optional
from config.settings import MASTODON_API_BASE_URL, MASTODON_ACCESS_TOKEN

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Media Upload
# ---------------------------------------------------------------------------

def upload_media(file_path: str, description: Optional[str] = None) -> Optional[str]:
    """
    Upload an image to Mastodon and return the media ID.
    Returns None if upload fails or credentials are missing.
    """
    if not MASTODON_API_BASE_URL or not MASTODON_ACCESS_TOKEN:
        logger.error("Mastodon credentials not configured.")
        return None

    url = f"{MASTODON_API_BASE_URL.rstrip('/')}/api/v2/media"
    headers = {"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"}

    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"description": description} if description else {}
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            response.raise_for_status()

            media_id = response.json().get("id")
            logger.info(f"Media uploaded to Mastodon successfully (ID: {media_id}).")
            return media_id

    except Exception as e:
        logger.error(f"Failed to upload media to Mastodon: {e}")
        return None


# ---------------------------------------------------------------------------
# Status Publishing
# ---------------------------------------------------------------------------

def post_to_mastodon(status_text: str, media_ids: Optional[list] = None) -> Optional[Dict]:
    """
    Publish a text status update (with optional media attachments) to Mastodon.
    Returns the created status payload or None on failure.
    """
    if not MASTODON_API_BASE_URL or not MASTODON_ACCESS_TOKEN:
        logger.error("Mastodon credentials not configured.")
        return None

    url = f"{MASTODON_API_BASE_URL.rstrip('/')}/api/v1/statuses"
    headers = {
        "Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "status": status_text,
        "visibility": "public"
    }

    if media_ids:
        payload["media_ids"] = media_ids

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Post successfully published on Mastodon: {data.get('url')}")
        return data

    except Exception as e:
        logger.error(f"Failed to post status to Mastodon: {e}")
        return None