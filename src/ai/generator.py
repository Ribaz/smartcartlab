# src/ai/generator.py
# Social media post generation using Gemma (via Ollama) with multi-platform support and 3 distinct angles.

import json
import logging
import re
import requests
from typing import Dict, List, Optional
from config.settings import OLLAMA_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt Engineering & System Directives
# ---------------------------------------------------------------------------

def _get_platform_instructions(platform: str) -> str:
    """
    Returns platform-specific guidelines and constraints for the LLM prompt.
    """
    platform = platform.lower()
    
    if platform == "facebook":
        return (
            "Target Platform: FACEBOOK\n"
            "- Tone: Engaging, conversational, and accessible to a broad audience.\n"
            "- Length: Between 300 and 600 characters. Encourage discussion or comments.\n"
            "- Style: Use clear spacing, friendly phrasing, and include 3-4 popular hashtags along with the [LINK] placeholder."
        )
    else:  # Default to mastodon / tech networks
        return (
            "Target Platform: MASTODON / TECH COMMUNITY\n"
            "- Tone: Clear, authoritative, tech-savvy, direct, and concise.\n"
            "- Length: Between 250 and 450 characters.\n"
            "- Style: Keep it focused on open-source/tech insights, include 2-3 relevant hashtags and the [LINK] placeholder."
        )


def _build_system_prompt(platform: str) -> str:
    """
    Constructs the dynamic system prompt injecting the correct platform rules.
    """
    platform_rules = _get_platform_instructions(platform)
    
    return f"""You are the social media copywriter for SmartCartLab, a platform that helps consumers make conscious online purchases by analyzing price history, anomalies, and real value.

Your task is to read the title and content of a blog article and produce exactly 3 distinct social media post variations tailored for the specified platform.

{platform_rules}

Core Constraints:
1. DO NOT write mere paraphrases of the same text: each post must have a distinct angle and objective:
   - Post 1 (Analytical / Practical Value): Explains the problem addressed by the article and the practical solution.
   - Post 2 (Data / Common Mistake): Highlights a technical detail, a frequent consumer mistake, or a price anomaly.
   - Post 3 (Conversational / Question): Closes with an open-ended question to stimulate community discussion.
2. Temporal Shift: The article is already public on the blog. Use phrases like "This week on the blog...", "In our latest deep dive...", "We analyzed...". NEVER say "Released today".
3. Strict requirement: Avoid salesperson hype or clickbait phrasing.
4. Response Format: Return EXCLUSIVELY a valid JSON array containing 3 objects, with no markdown code blocks, backticks, or introductory text.

Required JSON Structure:
[
  {{"variation_number": 1, "angle": "practical_value", "content": "Post text 1... [LINK] #hashtag"}},
  {{"variation_number": 2, "angle": "data_insight", "content": "Post text 2... [LINK] #hashtag"}},
  {{"variation_number": 3, "angle": "engagement_question", "content": "Post text 3... [LINK] #hashtag"}}
]"""


# ---------------------------------------------------------------------------
# Cleaners & Parsers
# ---------------------------------------------------------------------------

def _strip_html_tags(text: str) -> str:
    """Remove HTML tags from WordPress content to reduce prompt token footprint."""
    clean = re.compile(r"<.*?>")
    return re.sub(clean, "", text).strip()


def _extract_json_array(raw_text: str) -> Optional[List[Dict]]:
    """Robust parser to extract JSON array even if LLM wraps it in markdown fences."""
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        # Fallback regex to isolate the array block [...]
        match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Gemma Generation Interface
# ---------------------------------------------------------------------------

def generate_social_posts(article_title: str, article_content: str, article_link: str, platform: str = "mastodon") -> List[Dict]:
    """
    Generate 3 distinct social posts tailored for a specific platform using Gemma via Ollama API.
    Returns a list of dictionaries with 'variation_number' and 'content'.
    """
    cleaned_content = _strip_html_tags(article_content)[:2500]  # Limit content size to safeguard context window
    
    system_prompt = _build_system_prompt(platform)
    
    user_prompt = (
        f"Article Title: {article_title}\n"
        f"Article Link: {article_link}\n\n"
        f"Content Excerpt:\n{cleaned_content}\n\n"
        "Generate the 3 social posts now in the specified JSON format."
    )

    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        raw_response = response.json().get("response", "")

        posts_data = _extract_json_array(raw_response)
        if not posts_data or not isinstance(posts_data, list):
            logger.error(f"[{platform}] Failed to parse valid JSON from Gemma response: {raw_response[:200]}...")
            return []

        # Replace the [LINK] placeholder with the actual article link
        formatted_posts = []
        for item in posts_data:
            content = item.get("content", "").replace("[LINK]", article_link)
            var_num = item.get("variation_number", len(formatted_posts) + 1)
            formatted_posts.append({
                "variation_number": var_num,
                "content": content
            })

        logger.info(f"Successfully generated {len(formatted_posts)} distinct post variations for platform: {platform}.")
        return formatted_posts

    except Exception as e:
        logger.error(f"Error communicating with Ollama ({url}) for platform {platform}: {e}")
        return []