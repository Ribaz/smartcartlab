# src/integrations/facebook.py
# Facebook API client for publishing posts and uploading media.

import logging

import requests

from typing import Optional
from config.settings import FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID

logger = logging.getLogger(__name__)

def post_to_facebook(text: str, image_path: Optional[str] = None) -> bool:
    """
    Publishes a post to the configured Facebook Page using the Graph API.
    With image_path the post is a photo post, using the text as its caption.

    Returns:
        bool: True if publication was successful, False otherwise.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        logger.error("Facebook credentials (ID or Access Token) are not configured.")
        return False

    # Photo posts use a different edge than text-only posts.
    if image_path:
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/photos"
        payload = {"caption": text, "access_token": FACEBOOK_ACCESS_TOKEN}
    else:
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed"
        payload = {"message": text, "access_token": FACEBOOK_ACCESS_TOKEN}

    try:
        if image_path:
            with open(image_path, "rb") as image_file:
                response = requests.post(
                    url,
                    data=payload,
                    files={"source": image_file},
                    timeout=60,
                )
        else:
            response = requests.post(url, data=payload, timeout=30)

        response_data = response.json()

        if "id" in response_data:
            logger.info("Successfully posted to Facebook. Post ID: %s", response_data["id"])
            return True

        logger.error("Failed to post to Facebook. Response: %s", response_data)
        return False

    except requests.exceptions.RequestException as e:
        logger.error("HTTP Request exception occurred while posting to Facebook: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error while posting to Facebook: %s", e)
        return False