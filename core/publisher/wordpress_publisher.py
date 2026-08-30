# publisher/wordpress_publisher.py
# Creates the daily report article on WordPress via REST API.

from typing import Dict

import requests
from requests.auth import HTTPBasicAuth

from config.settings import WORDPRESS_APP_PASSWORD, WORDPRESS_URL, WORDPRESS_USER


class WordPressPublisher:

    def publish(self, product: Dict | None) -> bool:
        """
        Create a daily report post on WordPress.
        If product is None, still publish a 'no deal today' report.
        """
        title = self._build_title(product)
        content = self._build_content(product)
        return self._send(title, content)

    def _build_title(self, product: Dict | None) -> str:
        """Build the post title."""
        if product is None:
            return "Deal of the Day: nothing worth it today"
        return f"Deal of the Day: {product.get('title')}"

    def _build_content(self, product: Dict | None) -> str:
        """Build the post content in HTML."""
        if product is None:
            return "<p>Today's analysis found no deal worth recommending.</p>"
        return (
            f"<p><b>Product:</b> {product.get('title')}</p>"
            f"<p>💰 <b>Current Price:</b> {product.get('current_price')}€</p>"
            f"<p>📉 <b>Previous Price (90d avg):</b> {product.get('avg_price_90d')}€</p>"
            f"<p><a href='{product.get('product_link', '')}'>👉 Go to the offer</a></p>"
        )

    def _send(self, title: str, content: str) -> bool:
        """Publish a post to WordPress via REST API."""
        endpoint = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
        payload = {
            "title": title,
            "content": content,
            "status": "publish",
        }
        try:
            response = requests.post(
                endpoint,
                auth=HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_APP_PASSWORD),
                json=payload
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error publishing to WordPress: {e}")
            return False
