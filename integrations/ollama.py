# integrations/ollama.py
# Provides access to the local Ollama generation API.

import logging

import requests

from config.settings import OLLAMA_MODEL, OLLAMA_URL

logger = logging.getLogger(__name__)

OLLAMA_GENERATE_URL = f"{OLLAMA_URL.rstrip('/')}/api/generate"


def generate_text(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    timeout: int,
) -> str | None:
    """Generate text using the configured local Ollama model."""
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
        },
    }

    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        return response.json().get("response", "").strip() or None

    except requests.RequestException:
        logger.exception(
            "Unable to communicate with Ollama (%s).",
            OLLAMA_GENERATE_URL,
        )
        return None