# social/copywriter.py
# Generates and rewrites social media content through the local Ollama model.

from __future__ import annotations

import logging
import re

from integrations.ollama import generate_text

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "it": "Italian",
    "en": "English",
}


CONTENT_LIMIT = 2500


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



def generate_social_post(
    *,
    article_title: str,
    article_content: str,
    article_link: str,
    topic: str,
    platform: str,
    language: str,
) -> dict[str, str]:
    """Generate one platform-specific social post focused on one article topic."""
    platform = platform.lower()
    platform_rules = _get_platform_instructions(platform)
    language_rule = _get_language_instruction(language)
    cleaned_content = _strip_html_tags(article_content)[:CONTENT_LIMIT]

    if not cleaned_content:
        raise ValueError("Article content is required for social post generation.")

    if not topic.strip():
        raise ValueError("Topic is required for social post generation.")

    system_prompt = f"""
You are the social media copywriter for SmartCartLab.

Create exactly one social media post.

The supplied topic defines the specific subject the post must focus on.
The supplied article provides the factual source and context used to develop
that topic.

Develop the topic using only information, observations, and reasoning supported
by the supplied article.

Do not summarize the entire article.
Do not introduce factual claims, examples, or details that are not supported
by the article.
Do not change the subject to another topic from the article.

{platform_rules}

{language_rule}

The article is already available online.
Do not claim that it was published today.

Return exclusively the final post text.
Do not return JSON.
Do not include labels, Markdown fences, quotation marks, or introductory text.
""".strip()

    user_prompt = f"""
Article title:
{article_title}

Topic:
{topic}

Article link:
{article_link}

Article content:
{cleaned_content}

Write exactly one final social media post focused on the supplied topic.
""".strip()

    generated_text = generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
        timeout=180,
    )

    if not generated_text:
        raise RuntimeError("Ollama did not generate a social post.")

    cleaned_text = generated_text.strip('"').strip("'")
    cleaned_text = cleaned_text.replace("[LINK]", article_link)

    if platform == "mastodon" and len(cleaned_text) > 500:
        raise ValueError(
            f"Generated Mastodon post exceeds 500 characters "
            f"({len(cleaned_text)} characters)."
        )

    return {
        "platform": platform,
        "content": cleaned_text,
    }   



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

    generated_text = generate_text(
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

    rewritten_text = generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
        timeout=120,
    )
    if not rewritten_text:
        return None

    return rewritten_text.strip('"').strip("'") or None
