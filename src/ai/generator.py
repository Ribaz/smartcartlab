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

LANGUAGE_NAMES = {
    "it": "Italian",
    "en": "English",
}


def _get_language_instruction(language: str) -> str:
    try:
        language_name = LANGUAGE_NAMES[language.lower()]
    except KeyError:
        raise ValueError(f"Unsupported language: {language}")

    return f"Write ALL generated posts strictly in {language_name}."


def _get_platform_instructions(platform: str) -> str:
    """
    Returns platform-specific guidelines and constraints for the LLM prompt.
    """
    platform = platform.lower()
    
    if platform == "facebook":
        return (
            "Target Platform: FACEBOOK\n"
            "- Tone: Enthusiastic, spontaneous, conversational, and friendly. "
            "Sound like a nerdy programmer sharing something cool they just discovered or built "
            "with friends, not like a marketer or salesperson.\n"
            "- Voice: Write in a natural, human, slightly informal way. "
            "It is fine to show genuine excitement, curiosity, surprise, or satisfaction about the result. "
            "Use simple language and explain technical ideas in a way that a non-technical friend can understand.\n"
            "- Avoid: Do not sound promotional, corporate, polished, or sales-oriented. "
            "Do not use marketing language, calls to buy, exaggerated claims, or phrases that sound like an advertisement. "
            "Do not try to sell a product or service unless explicitly asked to do so.\n"
            "- Length: Between 500 and 800 characters. Encourage discussion or comments.\n"
            "- Structure: Write 3-4 short paragraphs separated by a blank line. "
            "Never write the entire post as one continuous block of text. "
            "Each paragraph should contain 1-2 sentences and focus on one idea.\n"
            "- Content: Start with an engaging observation, result, surprise, or small personal reaction. "
            "Then explain what happened in simple terms. "
            "If there is a technical aspect, focus on the interesting result or idea rather than showing code. "
            "The reader should feel like you are telling them about something cool you just experienced.\n"
            "- Conversation: End naturally with a question, a thought, or an invitation to share experiences. "
            "It should feel like starting a conversation with friends, not a call to action.\n"
            "- Hashtags: End with 3-4 relevant hashtags. Keep them natural and avoid generic marketing hashtags.\n"
            "- Link: Place the [LINK] placeholder on a new line after the hashtags.\n"
        )
    else:  # Default to mastodon / tech networks
        return (
            "Target Platform: MASTODON / TECH COMMUNITY\n"
            "- Tone: Clear, authoritative, tech-savvy, direct, and concise.\n"
            "- Length: Between 250 and 450 characters.\n"
            "- Style: Keep it focused on open-source/tech insights, include 2-3 relevant hashtags and the [LINK] placeholder."
        )


def _build_system_prompt(platform: str, language: str) -> str:
    """
    Constructs the dynamic system prompt injecting the correct platform rules.
    """
    platform_rules = _get_platform_instructions(platform)
    language_rule = _get_language_instruction(language)

    return f"""You are the social media copywriter for SmartCartLab, a platform that helps consumers make conscious online purchases by analyzing price history, anomalies, and real value.
Your task is to read the title and content of a blog article and produce exactly 3 distinct social media post variations tailored for the specified platform.

{platform_rules}
{language_rule}

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


EXPECTED_POSTS = {
    1: "practical_value",
    2: "data_insight",
    3: "engagement_question",
}

def _validate_generated_posts(posts: object) -> bool:

    if not isinstance(posts, list):
        return False

    if len(posts) != 3:
        return False

    found = set()

    for post in posts:

        if not isinstance(post, dict):
            return False

        number = post.get("variation_number")
        angle = post.get("angle")
        content = post.get("content", "").strip()

        if number not in EXPECTED_POSTS:
            return False

        if number in found:
            return False

        if angle != EXPECTED_POSTS[number]:
            return False

        if not content:
            return False

        found.add(number)

    return found == {1, 2, 3}


# ---------------------------------------------------------------------------
# Gemma Generation Interface
# ---------------------------------------------------------------------------

def generate_social_posts(article_title: str, article_content: str, article_link: str, platform: str, language: str ) -> List[Dict]:
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
        if not _validate_generated_posts(posts_data):
            logger.error(
                "[%s] Invalid response returned by Gemma.",
                platform,
            )
            return []

        # Replace the [LINK] placeholder with the actual article link
        formatted_posts = []
        for item in posts_data:
            content = item.get("content", "").replace("[LINK]", article_link)
            var_num = item.get("variation_number", len(formatted_posts) + 1)
            formatted_posts.append({
                "variation_number": var_num,
                "angle": item["angle"],
                "content": content
            })

        logger.info(f"Successfully generated {len(formatted_posts)} distinct post variations for platform: {platform}.")
        return formatted_posts

    except requests.RequestException:
        logger.exception(
            "Unable to communicate with Ollama (%s)",
            url,
        )
        return []

    except Exception:
        logger.exception(
            "Unexpected error while generating posts."
        )
        return []


def rewrite_social_post(current_content: str, platform: str = "mastodon") -> Optional[str]:
    """
    Rewrite a single social post variation using Gemma via Ollama API.
    """
    platform_rules = _get_platform_instructions(platform)
    
    system_prompt = f"""You are the social media copywriter for SmartCartLab.
Your task is to rewrite and improve the provided social media post for {platform}.
CRITICAL REQUIREMENT: Write the post STRICTLY IN ITALIAN.
Make it engaging, clear, and professional, adhering strictly to these platform rules:
{platform_rules}

Core Constraints:
1. Keep the core message, context, and any link/placeholder intact.
2. Make it sound fresh, engaging, and different from the original phrasing.
3. Response Format: Return EXCLUSIVELY the rewritten post text, with no markdown code blocks, backticks, quotation marks, or introductory text."""

    user_prompt = f"Original Post to Rewrite:\n{current_content}\n\nProvide the rewritten version:"

    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "top_p": 0.9
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        rewritten_text = response.json().get("response", "").strip()
        rewritten_text = rewritten_text.strip('"').strip("'")
        return rewritten_text if rewritten_text else None
    except Exception as e:
        logger.error(f"Error communicating with Ollama for post rewrite: {e}")
        return None