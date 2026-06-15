# publisher/telegram_publisher.py
# Publishes the daily pick to the Telegram channel via Bot API.

import requests
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from typing import Dict


class TelegramPublisher:

    def publish(self, product: Dict | None) -> bool:
        """
        Send the daily pick to the Telegram channel.
        If product is None, send a 'no deal today' message.
        """
        if product is None:
            return self._publish_no_deal()
        return self._publish_deal(product)

    def _publish_deal(self, product: Dict) -> bool:
        """Format and send the deal message."""
        message = (
            f"<b>🚀 Smart Cart Lab: Deal of the Day!</b>\n\n"
            f"<b>Product:</b> {product.get('title')}\n"
            f"💰 <b>Current Price:</b> {product.get('current_price')}€\n"
            f"📉 <b>Previous Price (90d avg):</b> {product.get('avg_price_90d')}€\n\n"
            f"<a href='{product.get('image_url', '')}'>&#8205;</a>"
            f"<a href='{product.get('product_link', '')}'>👉 Go to the offer</a>"
        )
        return self._send(message)

    def _publish_no_deal(self) -> bool:
        """Send a 'no deal worth it today' message."""
        message = (
            "📭 <b>Smart Cart Lab</b>\n\n"
            "No deal worth your money today. "
            "We'd rather tell you nothing than recommend something mediocre."
        )
        return self._send(message)

    def _send(self, message: str) -> bool:
        """Send a message to the Telegram channel."""
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending message to Telegram: {e}")
            return False
