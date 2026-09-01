# social/copywriter.py
# Generates and rewrites social media content through the local Ollama model.

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from config.settings import OLLAMA_MODEL, OLLAMA_URL


logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "it": "Italian",
    "en": "English",
}

EXPECTED_POSTS = {
    1: "practical_value",
    2: "data_insight",
    3: "engagement_question",
}

CONTENT_LIMIT = 2500
OLLAMA_GENERATE_URL = f"{OLLAMA_URL.rstrip('/')}/api/generate"


def _get_language_instruction(language: str) -> str:
    """Return the output-language instruction for the supplied language code."""
    try:
        language_name = LANGUAGE_NAMES[language.lower()]
    except KeyError as error:
        raise ValueError(f"Unsupported language: {language}") from error

    return f"Write all generated content strictly in {language_name}."


def _get_platform_instructions(platform: str) -> str:
    """Return style and length guidelines for the target platform."""
    platform = platform.lower()

    if platform == "facebook":
        return """
Target platform: Facebook.

Tone:
Competent, calm, clear, and approachable.
Write like an experienced developer who has discovered something genuinely
interesting and wants to share it with other curious people.
Be naturally positive and curious, but never exaggerated.
Avoid sounding like a marketer, influencer, or overexcited intern.

Voice:
Natural and human.
Prefer concrete observations over emotional reactions.
Avoid sensationalism and expressions such as "incredibile", "pazzesco",
"super interessante", "assolutamente da vedere", or "non ci crederai".

Content:
Communicate one useful idea from the article and explain why it matters.
Do not merely announce that an article has been published.
Do not summarize the entire article.
Leave implementation details and complete explanations to the linked article.

Opening:
Start directly with an observation, result, lesson, or problem.
Do not begin with greetings or expressions such as "Ragazzi", "Ciao a tutti",
"Ehi", or similar audience-addressing formulas.

Structure:
Use 2 or 3 short paragraphs separated by a blank line.

Length:
Between 580 and 900 characters.

Emojis:
Use at most 2 emojis and only when they improve readability.

Hashtags:
Use at most 3 relevant hashtags.
Do not use generic hashtags.
Omit hashtags when they add no value.

Call to action:
Do not ask readers to like, share, subscribe, or comment.
A final question is acceptable only when it follows naturally from the content.

Link:
Place the [LINK] placeholder on a new line at the end.
""".strip()

    if platform == "mastodon":
        return """
Target platform: Mastodon and technical communities.

Tone:
Clear, informed, direct, and concise.
Write for a technically curious audience without sounding promotional.

Content:
Focus on one concrete technical idea, result, or lesson from the article.
Avoid generic announcements and marketing language.

Structure:
Use one or two compact paragraphs.

Length:
Between 250 and 450 characters.

Hashtags:
Use 2 or 3 relevant technical hashtags.

Link:
Place the [LINK] placeholder on a new line at the end.
""".strip()

    raise ValueError(f"Unsupported platform: {platform}")


def _strip_html_tags(text: str | None) -> str:
    """Remove HTML tags, returning an empty string for missing content."""
    if not text:
        return ""

    return re.sub(r"<.*?>", "", text, flags=re.DOTALL).strip()


def _extract_json_array(raw_text: str) -> list[dict[str, Any]] | None:
    """Extract a JSON array even when the model wraps it in extra text."""
    try:
        parsed = json.loads(raw_text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
        if not match:
            return None

        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, list) else None


def _validate_generated_posts(posts: object) -> bool:
    """Validate the expected three-post response structure."""
    if not isinstance(posts, list) or len(posts) != 3:
        return False

    found_numbers: set[int] = set()

    for post in posts:
        if not isinstance(post, dict):
            return False

        number = post.get("variation_number")
        angle = post.get("angle")
        content = post.get("content", "").strip()

        if number not in EXPECTED_POSTS:
            return False

        if number in found_numbers:
            return False

        if angle != EXPECTED_POSTS[number]:
            return False

        if not content:
            return False

        found_numbers.add(number)

    return found_numbers == set(EXPECTED_POSTS)


def _request_ollama(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    timeout: int,
) -> str | None:
    """Send a generation request to Ollama and return its text response."""
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


def generate_social_posts(
    article_title: str,
    article_content: str,
    article_link: str,
    platform: str,
    language: str,
) -> list[dict[str, Any]]:
    """Generate three distinct social posts for an article and platform."""
    platform_rules = _get_platform_instructions(platform)
    language_rule = _get_language_instruction(language)
    cleaned_content = _strip_html_tags(article_content)[:CONTENT_LIMIT]

    system_prompt = f"""
You are the social media copywriter for SmartCartLab.

Read the supplied article and create exactly three distinct social media posts.

{platform_rules}

{language_rule}

The three posts must use these different angles:

1. Practical takeaway:
   Explain one practical lesson or useful consequence from the article.

2. Interesting technical insight:
   Focus on a technical detail, common mistake, data point, or relevant
   observation.

3. Discussion or reflection:
   Develop a thoughtful angle that may naturally encourage discussion.

Do not produce three paraphrases of the same post.

The article is already available online.
Do not claim that it was published today.

Return exclusively a valid JSON array containing exactly three objects.
Do not include Markdown fences, introductory text, or explanations.

Required JSON structure:

[
  {{
    "variation_number": 1,
    "angle": "practical_value",
    "content": "Post text with [LINK] placeholder"
  }},
  {{
    "variation_number": 2,
    "angle": "data_insight",
    "content": "Post text with [LINK] placeholder"
  }},
  {{
    "variation_number": 3,
    "angle": "engagement_question",
    "content": "Post text with [LINK] placeholder"
  }}
]
""".strip()

    user_prompt = f"""
Article title:
{article_title}

Article link:
{article_link}

Article content:
{cleaned_content}

Generate the three posts now.
""".strip()

    raw_response = _request_ollama(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
        timeout=180,
    )
    if not raw_response:
        return []

    posts_data = _extract_json_array(raw_response)
    if not _validate_generated_posts(posts_data):
        logger.error("[%s] Invalid response returned by Gemma.", platform)
        return []

    formatted_posts = []
    for item in posts_data:
        formatted_posts.append(
            {
                "variation_number": item["variation_number"],
                "angle": item["angle"],
                "content": item["content"].replace("[LINK]", article_link),
            }
        )

    logger.info(
        "Generated %s post variations for %s.",
        len(formatted_posts),
        platform,
    )
    return formatted_posts


def generate_custom_social_post(
    article_title: str,
    article_content: str,
    article_link: str,
    platform: str,
    user_prompt: str,
    language: str = "it",
) -> str | None:
    """Generate one custom social post from an article and user instruction."""
    platform_rules = _get_platform_instructions(platform)
    language_rule = _get_language_instruction(language)
    cleaned_content = _strip_html_tags(article_content)[:CONTENT_LIMIT]

    system_prompt = f"""
You are the social media copywriter for SmartCartLab.

Create exactly one social media post.

{platform_rules}

{language_rule}

Follow the user's custom instruction closely.
Keep the post consistent with the supplied article.
Return exclusively the final post text.
Do not return JSON.
Do not include labels, Markdown fences, quotation marks, or introductory text.
""".strip()

    user_message = f"""
Article title:
{article_title}

Article link:
{article_link}

Article content:
{cleaned_content}

Custom instruction:
{user_prompt}

Write exactly one final social media post now.
""".strip()

    generated_text = _request_ollama(
        system_prompt=system_prompt,
        user_prompt=user_message,
        temperature=0.6,
        timeout=180,
    )
    if not generated_text:
        return None

    cleaned_text = generated_text.strip('"').strip("'")
    return cleaned_text.replace("[LINK]", article_link) or None


def rewrite_social_post(
    current_content: str,
    platform: str = "mastodon",
    language: str = "it",
) -> str | None:
    """Rewrite one existing social post while preserving its meaning."""
    platform_rules = _get_platform_instructions(platform)
    language_rule = _get_language_instruction(language)

    system_prompt = f"""
You are the social media copywriter for SmartCartLab.

Rewrite exactly one existing social media post.

{platform_rules}

{language_rule}

Keep the original meaning, context, and links intact.
Improve clarity and naturalness without introducing unsupported information.
Return exclusively the rewritten post text.
Do not return JSON.
Do not include labels, Markdown fences, quotation marks, or introductory text.
""".strip()

    user_prompt = f"""
Original post:
{current_content}

Provide exactly one rewritten version.
""".strip()

    rewritten_text = _request_ollama(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
        timeout=120,
    )
    if not rewritten_text:
        return None

    return rewritten_text.strip('"').strip("'") or None
