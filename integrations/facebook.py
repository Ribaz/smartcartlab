# src/integrations/facebook.py
# Facebook API client for publishing posts and uploading media.

import logging

import requests

from config.settings import FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID

logger = logging.getLogger(__name__)

def post_to_facebook(text: str) -> bool:
    """
    Publishes a text post to the configured Facebook Page using the Graph API.
    
    Args:
        text (str): The content of the post.
        
    Returns:
        bool: True if publication was successful, False otherwise.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        logger.error("Facebook credentials (ID or Access Token) are not configured.")
        return False

    # Facebook Graph API endpoint for page feed
    url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed"
    
    payload = {
        "message": text,
        "access_token": FACEBOOK_ACCESS_TOKEN
    }

    try:
        response = requests.post(url, data=payload, timeout=30)
        response_data = response.json()
        
        # Check if the post ID is returned in the response
        if "id" in response_data:
            logger.info(f"Successfully posted to Facebook. Post ID: {response_data['id']}")
            return True
        else:
            logger.error(f"Failed to post to Facebook. Response: {response_data}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request exception occurred while posting to Facebook: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while posting to Facebook: {e}")
        return False