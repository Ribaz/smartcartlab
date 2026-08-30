# core/publisher/telegram_publisher.py
# Publishes the daily SmartCartLab result to the Telegram channel.

from __future__ import annotations

import logging
from typing import Dict

import requests

from config.settings import (
    OLLAMA_MODEL,
    OLLAMA_URL,
    TELEGRAM_CHANNEL_ID,
)
from integrations.telegram import send_telegram_message

logger = logging.getLogger(__name__)


DISCLAIMER = (
    "\n\n⚠️ <i>Messaggio di test — Smart Cart Lab è in fase di sviluppo. "
    "I dati, i prezzi e i link sono fittizi e generati casualmente. "
    "Non effettuare acquisti basandoti su queste informazioni.</i>"
)


class TelegramPublisher:
    def publish(self, product: Dict | None) -> bool:
        """Build and publish the daily Telegram message."""
        if product is None:
            message = (
                "📭 <b>Smart Cart Lab</b>\n\n"
                "Nessuna offerta degna di nota oggi. "
                "Preferiamo non consigliare nulla piuttosto che segnalare "
                "qualcosa di mediocre."
            )
        else:
            message = self._generate_message(product)
            if not message:
                message = self._fallback_message(product)

        return send_telegram_message(
            message=message + DISCLAIMER,
            chat_id=TELEGRAM_CHANNEL_ID,
            parse_mode="HTML",
        )

    def _generate_message(self, product: Dict) -> str | None:
        """Ask Ollama to generate the daily deal message."""
        prompt = (
            "Scrivi un messaggio Telegram accattivante per annunciare "
            "un'offerta del giorno. "
            f"Il prodotto è: {product.get('title')}. "
            f"Costa {product.get('current_price')}€ invece di "
            f"{product.get('avg_price_90d')}€ "
            "(prezzo medio degli ultimi 90 giorni). "
            "Usa un tono entusiasta ma onesto. "
            "Aggiungi qualche emoji pertinente. "
            "Non aggiungere link. "
            "Rispondi solo con il testo del messaggio, nient'altro."
        )

        try:
            response = requests.post(
                f"{OLLAMA_URL.rstrip('/')}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip() or None

        except requests.RequestException:
            logger.exception(
                "Unable to generate the Telegram message with Ollama."
            )
            return None

    def _fallback_message(self, product: Dict) -> str:
        """Build a fallback message when Ollama is unavailable."""
        return (
            "🚀 <b>Smart Cart Lab: Offerta del Giorno!</b>\n\n"
            f"<b>Prodotto:</b> {product.get('title')}\n"
            f"💰 <b>Prezzo attuale:</b> {product.get('current_price')}€\n"
            f"📉 <b>Prezzo medio 90gg:</b> {product.get('avg_price_90d')}€"
        )
