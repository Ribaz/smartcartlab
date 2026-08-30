# src/integrations/wordpress.py
# WordPress content integration via native RSS feeds.

import html
import logging
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

from config.settings import WORDPRESS_URL

logger = logging.getLogger(__name__)

# XML Namespaces standard for WordPress RSS 2.0
NAMESPACES = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "slash": "http://purl.org/rss/1.0/modules/slash/",
    "media": "http://search.yahoo.com/mrss/"
}


# ---------------------------------------------------------------------------
# Feed URL Builder & Fetching
# ---------------------------------------------------------------------------

def _get_feed_url(lang: str = "it") -> str:
    """Build the proper Polylang RSS feed URL based on language."""
    base_url = (WORDPRESS_URL or "https://www.smartcartlab.com").rstrip("/")
    if lang == "en":
        return f"{base_url}/en/feed/"
    return f"{base_url}/feed/"


def get_latest_posts(limit: int = 5, lang: str = "it") -> List[Dict]:
    """
    Fetch and parse the most recent published articles from the WordPress RSS feed.
    Returns a list of structured article dictionaries.
    """
    feed_url = _get_feed_url(lang)

    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SmartCartBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall("./channel/item")

        posts = []
        for item in items[:limit]:
            title_el = item.find("title")
            link_el = item.find("link")
            guid_el = item.find("guid")
            pub_date_el = item.find("pubDate")
            content_el = item.find("content:encoded", NAMESPACES)
            description_el = item.find("description")

            title = html.unescape(title_el.text) if title_el is not None and title_el.text else ""
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            guid = guid_el.text.strip() if guid_el is not None and guid_el.text else link
            pub_date = (
                pub_date_el.text.strip()
                if pub_date_el is not None and pub_date_el.text
                else ""
            )

            # Prefer full HTML content; fallback to description snippet
            body = ""
            if content_el is not None and content_el.text:
                body = content_el.text
            elif description_el is not None and description_el.text:
                body = description_el.text

            # Extract featured media URL if present in enclosure
            media_url = None
            enclosure = item.find("enclosure")
            if enclosure is not None and "image" in enclosure.attrib.get("type", ""):
                media_url = enclosure.attrib.get("url")

            # Extract slug from clean link
            slug = link.rstrip("/").split("/")[-1]

            posts.append({
                "id": guid,
                "slug": slug,
                "title": title,
                "content": body,
                "link": link,
                "pub_date": pub_date,
                "media_url": media_url,
                "lang": lang
            })

        logger.info(f"Successfully fetched {len(posts)} articles from RSS ({lang}).")
        return posts

    except Exception as e:
        logger.error(f"Error fetching WordPress RSS feed ({feed_url}): {e}")
        return []